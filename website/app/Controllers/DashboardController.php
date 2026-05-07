<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Core\{View, Session, Csrf, Validator, Database};
use App\Models\{User, Plan, Investment, Transaction, Payout};
use App\Services\{AcceptXmrClient, PriceFeed, Mailer};

class DashboardController
{
    public function index(array $params = []): void
    {
        $userId      = Session::userId();
        $investments = Investment::findByUser($userId, 'active');
        $recent      = Transaction::findByUser($userId, 15);
        $balance     = User::getBalance($userId);
        $stats       = Investment::getStats();

        // User-specific stats
        $db           = Database::getInstance();
        $totalInvested = (float)($db->fetchOne(
            "SELECT COALESCE(SUM(amount_usd),0) as t FROM investments WHERE user_id = ? AND status != 'cancelled'",
            [$userId]
        )['t'] ?? 0);
        $totalRoi = (float)($db->fetchOne(
            "SELECT COALESCE(SUM(amount_usd),0) as t FROM transactions WHERE user_id = ? AND type='roi' AND status='confirmed'",
            [$userId]
        )['t'] ?? 0);

        (new View())->display('dashboard/index.twig', compact(
            'investments', 'recent', 'balance', 'totalInvested', 'totalRoi'
        ));
    }

    public function invest(array $params = []): void
    {
        $plans  = Plan::findAll(true);
        $prices = (new PriceFeed())->getPrices();
        $planId = (int)($_GET['plan'] ?? 0);
        (new View())->display('dashboard/invest.twig', compact('plans', 'prices', 'planId'));
    }

    public function investPost(array $params = []): void
    {
        Csrf::middleware();
        $userId    = Session::userId();
        $planId    = (int)($_POST['plan_id']   ?? 0);
        $amountUsd = (float)($_POST['amount_usd'] ?? 0);

        $plan = Plan::findById($planId);
        if (!$plan || !$plan['is_active']) {
            Session::flash('error', 'Invalid investment plan selected.');
            header('Location: ' . APP_URL . '/dashboard/invest'); exit;
        }

        if ($amountUsd < (float)$plan['min_amount_usd'] || $amountUsd > (float)$plan['max_amount_usd']) {
            Session::flash('error', "Amount must be between \${$plan['min_amount_usd']} and \${$plan['max_amount_usd']}.");
            header('Location: ' . APP_URL . '/dashboard/invest'); exit;
        }

        $feed       = new PriceFeed();
        $piconeros  = $feed->usdToXmrPiconeros($amountUsd);
        $callbackUrl = APP_URL . '/payment/callback';
        $order       = "user:{$userId} plan:{$planId} usd:{$amountUsd}";

        $client  = new AcceptXmrClient();
        $invoice = $client->createInvoice($piconeros, 2, 3600, $callbackUrl, $order);

        if (!$invoice || empty($invoice['invoice_id'])) {
            Session::flash('error', 'Payment gateway unavailable. Please try again later.');
            header('Location: ' . APP_URL . '/dashboard/invest'); exit;
        }

        $db = Database::getInstance();
        $db->beginTransaction();
        try {
            $investId = Investment::create([
                'user_id'    => $userId,
                'plan_id'    => $planId,
                'amount_usd' => $amountUsd,
                'amount_xmr' => $piconeros,
                'status'     => 'pending_payment',
            ]);

            Transaction::create([
                'user_id'                => $userId,
                'investment_id'          => $investId,
                'type'                   => 'deposit',
                'amount_usd'             => $amountUsd,
                'amount_xmr'             => $piconeros,
                'acceptxmr_invoice_id'   => $invoice['invoice_id'],
                'status'                 => 'pending',
                'confirmations_required' => 2,
            ]);

            $db->commit();
        } catch (\Throwable $e) {
            $db->rollback();
            error_log('[DashboardController] investPost error: ' . $e->getMessage());
            Session::flash('error', 'An error occurred. Please try again.');
            header('Location: ' . APP_URL . '/dashboard/invest'); exit;
        }

        header('Location: ' . APP_URL . '/dashboard/payment/' . urlencode($invoice['invoice_id']));
        exit;
    }

    public function payment(array $params = []): void
    {
        $invoiceId = $params['invoice_id'] ?? '';
        $client    = new AcceptXmrClient();
        $invoice   = $client->getInvoice($invoiceId);

        if (!$invoice) {
            Session::flash('error', 'Invoice not found or expired.');
            header('Location: ' . APP_URL . '/dashboard'); exit;
        }

        // Generate QR code
        $qrDataUri = '';
        $uri = $invoice['uri'] ?? ('monero:' . ($invoice['address'] ?? ''));
        try {
            $qrCode  = \Endroid\QrCode\QrCode::create($uri)
                ->setSize(250)
                ->setMargin(10);
            $writer  = new \Endroid\QrCode\Writer\PngWriter();
            $result  = $writer->write($qrCode);
            $qrDataUri = $result->getDataUri();
        } catch (\Throwable $e) {
            error_log('[DashboardController] QR generation failed: ' . $e->getMessage());
        }

        (new View())->display('dashboard/payment.twig', compact('invoice', 'invoiceId', 'qrDataUri'));
    }

    public function history(array $params = []): void
    {
        $userId      = Session::userId();
        $investments = Investment::findByUser($userId);
        $transactions = Transaction::findByUser($userId, 50);
        $payouts     = Payout::findByUser($userId);
        (new View())->display('dashboard/history.twig', compact('investments', 'transactions', 'payouts'));
    }

    public function profile(array $params = []): void
    {
        $user = User::findById(Session::userId());
        (new View())->display('dashboard/profile.twig', compact('user'));
    }

    public function updateProfile(array $params = []): void
    {
        Csrf::middleware();
        $userId = Session::userId();
        $name   = htmlspecialchars(trim($_POST['name']  ?? ''), ENT_QUOTES);
        $phone  = htmlspecialchars(trim($_POST['phone'] ?? ''), ENT_QUOTES);

        if (strlen($name) < 2) {
            Session::flash('error', 'Name must be at least 2 characters.');
            header('Location: ' . APP_URL . '/dashboard/profile'); exit;
        }

        User::update($userId, ['name' => $name, 'phone' => $phone]);
        $user = User::findById($userId);
        Session::login($user); // Refresh session

        Session::flash('success', 'Profile updated successfully.');
        header('Location: ' . APP_URL . '/dashboard/profile'); exit;
    }

    public function changePassword(array $params = []): void
    {
        Csrf::middleware();
        $userId  = Session::userId();
        $user    = User::findById($userId);
        $current = $_POST['current_password'] ?? '';
        $new     = $_POST['new_password']     ?? '';
        $confirm = $_POST['new_password_confirmation'] ?? '';

        if (!password_verify($current, $user['password_hash'])) {
            Session::flash('error', 'Current password is incorrect.');
            header('Location: ' . APP_URL . '/dashboard/profile'); exit;
        }

        if ($new !== $confirm || strlen($new) < 8) {
            Session::flash('error', 'New passwords do not match or are too short.');
            header('Location: ' . APP_URL . '/dashboard/profile'); exit;
        }

        User::updatePassword($userId, $new);
        Session::flash('success', 'Password changed successfully.');
        header('Location: ' . APP_URL . '/dashboard/profile'); exit;
    }

    public function withdraw(array $params = []): void
    {
        Csrf::middleware();
        $userId  = Session::userId();
        $amount  = (float)($_POST['amount'] ?? 0);
        $address = trim($_POST['xmr_address'] ?? '');
        $balance = User::getBalance($userId);

        if ($amount <= 0 || $amount > $balance) {
            Session::flash('error', 'Invalid withdrawal amount.');
            header('Location: ' . APP_URL . '/dashboard'); exit;
        }

        if (strlen($address) < 90) {
            Session::flash('error', 'Invalid XMR address.');
            header('Location: ' . APP_URL . '/dashboard'); exit;
        }

        $feed      = new PriceFeed();
        $piconeros = $feed->usdToXmrPiconeros($amount);

        Payout::create([
            'user_id'             => $userId,
            'amount_usd'          => $amount,
            'amount_xmr'          => $piconeros,
            'destination_address' => $address,
            'status'              => 'pending',
        ]);

        Session::flash('success', 'Withdrawal request submitted. Admin will review it shortly.');
        header('Location: ' . APP_URL . '/dashboard'); exit;
    }

    public function cancelInvoice(array $params = []): void
    {
        Csrf::middleware();
        $invoiceId = trim($_POST['invoice_id'] ?? '');
        $userId    = Session::userId();

        $tx = Transaction::findByInvoiceId($invoiceId);
        if (!$tx || $tx['user_id'] != $userId) {
            Session::flash('error', 'Invoice not found.');
            header('Location: ' . APP_URL . '/dashboard'); exit;
        }

        $client = new AcceptXmrClient();
        $client->deleteInvoice($invoiceId);

        $db = Database::getInstance();
        $db->update('transactions', ['status' => 'expired', 'updated_at' => date('Y-m-d H:i:s')], 'id = ?', [$tx['id']]);
        if ($tx['investment_id']) {
            $db->update('investments', ['status' => 'cancelled', 'updated_at' => date('Y-m-d H:i:s')], 'id = ?', [$tx['investment_id']]);
        }

        Session::flash('info', 'Invoice cancelled.');
        header('Location: ' . APP_URL . '/dashboard'); exit;
    }
}
