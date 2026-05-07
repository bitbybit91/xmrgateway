<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Core\{Session, Database};
use App\Models\{Transaction, Investment};
use App\Services\{AcceptXmrClient, Mailer};

class InvestController
{
    public function paymentStatus(array $params = []): void
    {
        header('Content-Type: application/json');
        $invoiceId = $params['invoice_id'] ?? '';

        $client  = new AcceptXmrClient();
        $invoice = $client->getInvoice($invoiceId);

        // Also check local DB status (poll_payments.php may have already confirmed it)
        $tx = Transaction::findByInvoiceId($invoiceId);

        echo json_encode([
            'invoice'    => $invoice,
            'db_status'  => $tx['status'] ?? null,
            'confirmed'  => ($tx['status'] ?? '') === 'confirmed',
        ]);
    }

    public function callback(array $params = []): void
    {
        // Read raw POST body from AcceptXMR webhook
        $raw     = file_get_contents('php://input');
        $payload = json_decode($raw, true);

        if (!$payload || !isset($payload['id'])) {
            http_response_code(400);
            echo 'Bad Request';
            exit;
        }

        $invoiceId     = $payload['id'];
        $amountPaid    = (int)($payload['amount_paid']            ?? 0);
        $amountNeeded  = (int)($payload['amount_requested']       ?? 0);
        $confirmations = $payload['confirmations']                ?? null;
        $confsRequired = (int)($payload['confirmations_required'] ?? 2);
        $expiresIn     = (int)($payload['expiration_in']          ?? 1);

        $tx = Transaction::findByInvoiceId($invoiceId);
        if (!$tx) {
            http_response_code(200); // Accept but ignore unknown invoices
            echo 'OK';
            exit;
        }

        $db = Database::getInstance();

        // Store raw callback payload
        $db->update('transactions', [
            'callback_payload' => json_encode($payload),
            'updated_at'       => date('Y-m-d H:i:s'),
        ], 'id = ?', [$tx['id']]);

        // Fully paid and confirmed
        if ($amountPaid >= $amountNeeded
            && $confirmations !== null
            && (int)$confirmations >= $confsRequired
            && $tx['status'] !== 'confirmed'
        ) {
            $db->beginTransaction();
            try {
                $db->update('transactions', [
                    'status'        => 'confirmed',
                    'confirmations' => (int)$confirmations,
                    'updated_at'    => date('Y-m-d H:i:s'),
                ], 'id = ?', [$tx['id']]);

                if ($tx['investment_id']) {
                    Investment::activate($tx['investment_id']);

                    $investment = Investment::findById($tx['investment_id']);
                    $plan = $db->fetchOne('SELECT * FROM plans WHERE id = ?', [$investment['plan_id'] ?? 0]);
                    $user = $db->fetchOne('SELECT * FROM users WHERE id = ?', [$tx['user_id']]);

                    if ($user && $investment && $plan) {
                        (new Mailer())->sendInvestmentConfirmed($user['email'], $user['name'], $investment, $plan);
                    }
                }

                $db->commit();
            } catch (\Throwable $e) {
                $db->rollback();
                error_log('[InvestController::callback] Error: ' . $e->getMessage());
                http_response_code(500);
                echo 'Error';
                exit;
            }
        } elseif ($expiresIn <= 0 && $amountPaid < $amountNeeded && $tx['status'] === 'pending') {
            // Expired
            $db->update('transactions', [
                'status'     => 'expired',
                'updated_at' => date('Y-m-d H:i:s'),
            ], 'id = ?', [$tx['id']]);

            if ($tx['investment_id']) {
                $db->update('investments', [
                    'status'     => 'cancelled',
                    'updated_at' => date('Y-m-d H:i:s'),
                ], 'id = ?', [$tx['investment_id']]);
            }
        }

        http_response_code(200);
        echo 'OK';
    }
}
