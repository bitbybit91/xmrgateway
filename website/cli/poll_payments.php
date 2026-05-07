#!/usr/bin/env php
<?php
/**
 * poll_payments.php
 * Runs every 1 minute via cron.
 * Polls AcceptXMR for pending transaction updates and activates investments.
 */

declare(strict_types=1);

define('BASE_PATH',   dirname(__DIR__));
define('PUBLIC_PATH', BASE_PATH . '/public');

require BASE_PATH . '/vendor/autoload.php';
require BASE_PATH . '/config/config.php';

use App\Core\Database;
use App\Models\{Transaction, Investment};
use App\Services\{AcceptXmrClient, Mailer};

$db     = Database::getInstance();
$client = new AcceptXmrClient();

// Find all pending deposit transactions that have an AcceptXMR invoice
$pending = Transaction::findPending();
$processed = 0;

foreach ($pending as $tx) {
    $invoiceId = $tx['acceptxmr_invoice_id'];
    $invoice   = $client->getInvoice($invoiceId);

    if (!$invoice) {
        // AcceptXMR doesn't know this invoice — possibly expired + removed
        if (strtotime($tx['created_at']) < time() - 7200) {
            Transaction::update((int)$tx['id'], ['status' => 'expired']);
            if ($tx['investment_id']) {
                Investment::update((int)$tx['investment_id'], ['status' => 'cancelled']);
            }
            echo "[poll_payments] Invoice $invoiceId expired (stale).\n";
        }
        continue;
    }

    $paid       = (int)($invoice['amount_paid']            ?? 0);
    $needed     = (int)($invoice['amount_requested']       ?? 0);
    $confs      = $invoice['confirmations']                ?? null;
    $confsReq   = (int)($invoice['confirmations_required'] ?? 2);
    $expiresIn  = (int)($invoice['expiration_in']          ?? 1);

    // Fully paid + confirmed
    if ($paid >= $needed && $confs !== null && (int)$confs >= $confsReq) {
        $db->beginTransaction();
        try {
            Transaction::update((int)$tx['id'], [
                'status'        => 'confirmed',
                'confirmations' => (int)$confs,
            ]);

            if ($tx['investment_id']) {
                Investment::activate((int)$tx['investment_id']);
                $investment = Investment::findById((int)$tx['investment_id']);
                if ($investment) {
                    $plan = $db->fetchOne('SELECT * FROM plans WHERE id = ?', [$investment['plan_id']]);
                    $user = $db->fetchOne('SELECT * FROM users WHERE id = ?', [$tx['user_id']]);
                    if ($user && $plan) {
                        (new Mailer())->sendInvestmentConfirmed($user['email'], $user['name'], $investment, $plan);
                    }
                }
            }

            $db->commit();
            $processed++;
            echo "[poll_payments] Invoice $invoiceId CONFIRMED.\n";
        } catch (\Throwable $e) {
            $db->rollback();
            error_log("[poll_payments] Error activating investment for $invoiceId: " . $e->getMessage());
        }
    } elseif ($expiresIn <= 0 && $paid < $needed) {
        Transaction::update((int)$tx['id'], ['status' => 'expired']);
        if ($tx['investment_id']) {
            Investment::update((int)$tx['investment_id'], ['status' => 'cancelled']);
        }
        echo "[poll_payments] Invoice $invoiceId EXPIRED.\n";
    }
}

echo "[poll_payments] Done. Processed $processed confirmations.\n";
