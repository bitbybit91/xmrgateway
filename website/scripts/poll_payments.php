<?php
/**
 * poll_payments.php - CLI script to poll pending investments from AcceptXMR
 * Run via cron: * * * * * /usr/bin/php /var/www/cryptoinvest/scripts/poll_payments.php
 */
define('CLI_ONLY', true);

if (php_sapi_name() !== 'cli') {
    http_response_code(403);
    exit('CLI only.');
}

require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/acceptxmr_client.php';

function log_msg(string $msg): void {
    echo '[' . date('Y-m-d H:i:s') . '] ' . $msg . PHP_EOL;
}

log_msg('Poll started.');

try {
    $pdo = DB::get();
} catch (PDOException $e) {
    log_msg('ERROR: Cannot connect to DB: ' . $e->getMessage());
    exit(1);
}

// Fetch pending investments not older than 24 hours
$stmt = $pdo->prepare(
    "SELECT i.id, i.acceptxmr_invoice_id, i.amount_xmr, i.user_id, i.fund_id, i.confirmations
     FROM investments i
     WHERE i.status = 'pending'
       AND i.created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
     ORDER BY i.created_at ASC"
);
$stmt->execute();
$investments = $stmt->fetchAll(PDO::FETCH_ASSOC);

if (empty($investments)) {
    log_msg('No pending investments to poll.');
    exit(0);
}

log_msg('Found ' . count($investments) . ' pending investment(s).');

$client = new AcceptXmrClient(
    ACCEPTXMR_INTERNAL_URL,
    ACCEPTXMR_EXTERNAL_URL,
    ACCEPTXMR_TOKEN
);

foreach ($investments as $inv) {
    $invoice_id = $inv['acceptxmr_invoice_id'];
    log_msg('Checking invoice: ' . $invoice_id . ' (investment #' . $inv['id'] . ')');

    try {
        $invoice = $client->getInvoice($invoice_id);
    } catch (RuntimeException $e) {
        log_msg('  WARN: Failed to fetch invoice: ' . $e->getMessage());
        continue;
    }

    $api_confirmations  = (int)($invoice['confirmations'] ?? 0);
    $conf_required      = (int)($invoice['confirmations_required'] ?? XMR_CONFIRMATIONS_REQUIRED);
    $amount_paid        = (int)($invoice['amount_paid'] ?? 0);
    $amount_requested   = (int)($invoice['amount_requested'] ?? 0);
    $expiration_in      = isset($invoice['expiration_in']) ? (int)$invoice['expiration_in'] : null;
    $subaddress         = $invoice['address'] ?? null;

    $new_status = 'pending';
    if ($amount_requested > 0
        && $amount_paid >= $amount_requested
        && $api_confirmations >= $conf_required
    ) {
        $new_status = 'confirmed';
    } elseif ($expiration_in !== null && $expiration_in <= 0) {
        $new_status = 'expired';
    }

    // Update investment record
    if ($new_status === 'confirmed') {
        $pdo->prepare(
            "UPDATE investments
             SET status = 'confirmed', confirmations = :c, confirmed_at = NOW(), subaddress = COALESCE(:addr, subaddress)
             WHERE id = :id AND status = 'pending'"
        )->execute([
            ':c'    => $api_confirmations,
            ':addr' => $subaddress,
            ':id'   => $inv['id'],
        ]);
        log_msg('  -> CONFIRMED (confirmations: ' . $api_confirmations . ')');

        // Record transaction if txid is available
        $txid = $invoice['txid'] ?? null;
        if ($txid !== null && $txid !== '') {
            $amount_xmr_paid = bcdiv((string)$amount_paid, '1000000000000', 12);
            $block_height    = isset($invoice['current_height']) ? (int)$invoice['current_height'] : null;
            try {
                $pdo->prepare(
                    "INSERT IGNORE INTO transactions (investment_id, txid, amount_xmr, block_height)
                     VALUES (:inv_id, :txid, :amount, :height)"
                )->execute([
                    ':inv_id' => $inv['id'],
                    ':txid'   => $txid,
                    ':amount' => $amount_xmr_paid,
                    ':height' => $block_height,
                ]);
                log_msg('  -> Transaction recorded: ' . $txid);
            } catch (PDOException $e) {
                log_msg('  WARN: Could not record transaction: ' . $e->getMessage());
            }
        }

    } elseif ($new_status === 'expired') {
        $pdo->prepare(
            "UPDATE investments SET status = 'expired', confirmations = :c WHERE id = :id AND status = 'pending'"
        )->execute([':c' => $api_confirmations, ':id' => $inv['id']]);
        log_msg('  -> EXPIRED');

    } else {
        // Still pending: update confirmations and subaddress
        $pdo->prepare(
            "UPDATE investments SET confirmations = :c, subaddress = COALESCE(:addr, subaddress) WHERE id = :id"
        )->execute([
            ':c'    => $api_confirmations,
            ':addr' => $subaddress,
            ':id'   => $inv['id'],
        ]);
        log_msg('  -> Still pending (confirmations: ' . $api_confirmations . '/' . $conf_required . ', paid: ' . $amount_paid . '/' . $amount_requested . ')');
    }
}

log_msg('Poll complete.');
exit(0);
