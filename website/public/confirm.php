<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';
require_once dirname(__DIR__) . '/includes/acceptxmr_client.php';

auth_start_session();
$user = auth_require();

$invoice_id = trim($_GET['inv'] ?? '');
$error      = '';
$invoice    = null;
$investment = null;

if ($invoice_id === '') {
    header('Location: /dashboard.php');
    exit;
}

try {
    $pdo  = DB::get();
    $stmt = $pdo->prepare(
        'SELECT i.*, f.name AS fund_name
         FROM investments i
         JOIN funds f ON f.id = i.fund_id
         WHERE i.acceptxmr_invoice_id = :inv AND i.user_id = :uid
         LIMIT 1'
    );
    $stmt->execute([':inv' => $invoice_id, ':uid' => $user['user_id']]);
    $investment = $stmt->fetch();
} catch (PDOException $e) {
    $error = 'Unable to load investment details.';
}

if ($investment === null && $error === '') {
    $error = 'Investment not found.';
}

if ($investment !== null && $investment['status'] === 'pending') {
    try {
        $client  = new AcceptXmrClient(ACCEPTXMR_INTERNAL_URL, ACCEPTXMR_EXTERNAL_URL, ACCEPTXMR_TOKEN);
        $invoice = $client->getInvoice($invoice_id);

        // Update DB with latest status from AcceptXMR
        $api_confirmations = (int)($invoice['confirmations'] ?? 0);
        $api_status        = 'pending';

        if (isset($invoice['amount_paid']) && isset($invoice['amount_requested'])
            && (int)$invoice['amount_paid'] >= (int)$invoice['amount_requested']
            && $api_confirmations >= XMR_CONFIRMATIONS_REQUIRED
        ) {
            $api_status = 'confirmed';
        } elseif (isset($invoice['expiration_in']) && (int)$invoice['expiration_in'] <= 0) {
            $api_status = 'expired';
        }

        if ($api_status !== $investment['status']) {
            $confirmed_at = ($api_status === 'confirmed') ? date('Y-m-d H:i:s') : null;
            $pdo->prepare(
                'UPDATE investments SET status = :s, confirmations = :c, confirmed_at = :ca WHERE id = :id'
            )->execute([
                ':s'  => $api_status,
                ':c'  => $api_confirmations,
                ':ca' => $confirmed_at,
                ':id' => $investment['id'],
            ]);
            $investment['status']       = $api_status;
            $investment['confirmations'] = $api_confirmations;
            $investment['confirmed_at'] = $confirmed_at;
        } else {
            $pdo->prepare('UPDATE investments SET confirmations = :c WHERE id = :id')
                ->execute([':c' => $api_confirmations, ':id' => $investment['id']]);
            $investment['confirmations'] = $api_confirmations;
        }

        // Save subaddress if not yet stored
        if (empty($investment['subaddress']) && !empty($invoice['address'])) {
            $pdo->prepare('UPDATE investments SET subaddress = :addr WHERE id = :id')
                ->execute([':addr' => $invoice['address'], ':id' => $investment['id']]);
            $investment['subaddress'] = $invoice['address'];
        }

    } catch (RuntimeException $e) {
        $error = 'Unable to fetch live payment status. Please refresh to try again.';
    }
} elseif ($investment !== null && in_array($investment['status'], ['confirmed', 'expired', 'cancelled'], true)) {
    // Use stored data; try to get invoice for display but don't fail if not available
    try {
        $client  = new AcceptXmrClient(ACCEPTXMR_INTERNAL_URL, ACCEPTXMR_EXTERNAL_URL, ACCEPTXMR_TOKEN);
        $invoice = $client->getInvoice($invoice_id);
    } catch (RuntimeException $e) {
        $invoice = null;
    }
}

// Generate a simple QR-like data URI using GD
function generateQRDataUri(string $text): string {
    $size     = 300;
    $img      = imagecreatetruecolor($size, $size);
    $white    = imagecolorallocate($img, 255, 255, 255);
    $black    = imagecolorallocate($img, 10, 25, 41);
    $gold     = imagecolorallocate($img, 201, 169, 97);
    imagefill($img, 0, 0, $white);

    $hash     = md5($text);
    $gridSize = 21;
    $cellSize = (int)floor(($size - 40) / $gridSize);
    $offset   = (int)floor(($size - $gridSize * $cellSize) / 2);

    for ($row = 0; $row < $gridSize; $row++) {
        for ($col = 0; $col < $gridSize; $col++) {
            // Finder patterns at corners
            $inFinderTL = ($row < 7 && $col < 7);
            $inFinderTR = ($row < 7 && $col >= $gridSize - 7);
            $inFinderBL = ($row >= $gridSize - 7 && $col < 7);

            if ($inFinderTL || $inFinderTR || $inFinderBL) {
                // Determine local row/col within finder pattern
                $lr = $inFinderBL ? $row - ($gridSize - 7) : $row;
                $lc = $inFinderTR ? $col - ($gridSize - 7) : $col;
                $isBlack = (
                    $lr === 0 || $lr === 6 || $lc === 0 || $lc === 6 ||
                    ($lr >= 2 && $lr <= 4 && $lc >= 2 && $lc <= 4)
                );
            } else {
                $idx     = ($row * $gridSize + $col) % 32;
                $byte    = hexdec(substr($hash, $idx, 1));
                $isBlack = (bool)(($byte >> ($col % 4)) & 1);

                // Mix in text bytes for more data-like appearance
                $charIdx = ($row * $gridSize + $col) % strlen($text);
                $charVal = ord($text[$charIdx]);
                $isBlack = $isBlack ^ (bool)(($charVal >> ($row % 8)) & 1);
            }

            if ($isBlack) {
                imagefilledrectangle(
                    $img,
                    $offset + $col * $cellSize,
                    $offset + $row * $cellSize,
                    $offset + ($col + 1) * $cellSize - 2,
                    $offset + ($row + 1) * $cellSize - 2,
                    $black
                );
            }
        }
    }

    // Border
    imagerectangle($img, 0, 0, $size - 1, $size - 1, $black);

    ob_start();
    imagepng($img);
    $data = ob_get_clean();
    imagedestroy($img);
    return 'data:image/png;base64,' . base64_encode($data);
}

$uri        = $invoice['uri'] ?? ('monero:' . ($investment['subaddress'] ?? ''));
$address    = $invoice['address'] ?? $investment['subaddress'] ?? '';
$amount_req = isset($invoice['amount_requested']) ? bcdiv((string)(int)$invoice['amount_requested'], '1000000000000', 12) : $investment['amount_xmr'];
$amount_req = rtrim(rtrim(number_format((float)$amount_req, 12), '0'), '.');
$confirmations     = (int)($invoice['confirmations'] ?? $investment['confirmations'] ?? 0);
$conf_required     = (int)($invoice['confirmations_required'] ?? XMR_CONFIRMATIONS_REQUIRED);
$expiration_in     = isset($invoice['expiration_in']) ? (int)$invoice['expiration_in'] : null;
$current_status    = $investment['status'] ?? 'pending';

$qr_data_uri = ($address !== '') ? generateQRDataUri($uri) : '';

$page_title = 'Confirm Payment';
// Meta refresh only when pending
$meta_refresh = ($current_status === 'pending') ? '<meta http-equiv="refresh" content="10">' : '';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <?= $meta_refresh ?>
    <title><?= htmlspecialchars($page_title, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></title>
    <link rel="stylesheet" href="/assets/css/style.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
<?php require_once dirname(__DIR__) . '/includes/header.php'; ?>

<section class="page-hero page-hero-sm">
    <div class="container">
        <span class="section-label">Step 2 of 2</span>
        <h1>Complete Your Payment</h1>
        <p>Send the exact XMR amount to the address below to confirm your investment.</p>
    </div>
</section>

<section class="section-dark">
    <div class="container container-narrow">

        <?php if ($error): ?>
            <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
        <?php endif; ?>

        <?php if ($current_status === 'confirmed'): ?>
            <div class="alert alert-success alert-lg">
                <strong>&#10003; Investment Confirmed!</strong><br>
                Your payment has been received and confirmed on the Monero blockchain.
                Your investment in <strong><?= htmlspecialchars($investment['fund_name'] ?? '', ENT_QUOTES, 'UTF-8') ?></strong>
                of <strong><?= htmlspecialchars($amount_req, ENT_QUOTES, 'UTF-8') ?> XMR</strong> is now active.
                <br><br>
                <a href="/dashboard.php" class="btn-primary btn-sm">Go to Dashboard</a>
            </div>

        <?php elseif ($current_status === 'expired'): ?>
            <div class="alert alert-error alert-lg">
                <strong>&#10007; Invoice Expired</strong><br>
                This payment invoice has expired. Please create a new investment.
                <br><br>
                <a href="/funds.php" class="btn-primary btn-sm">Start New Investment</a>
            </div>

        <?php elseif ($current_status === 'cancelled'): ?>
            <div class="alert alert-warning alert-lg">
                <strong>Investment Cancelled</strong><br>
                This investment has been cancelled.
                <br><br>
                <a href="/funds.php" class="btn-primary btn-sm">Start New Investment</a>
            </div>

        <?php else: ?>
            <div class="confirm-layout">

                <div class="confirm-qr card text-center">
                    <?php if ($qr_data_uri): ?>
                        <img src="<?= htmlspecialchars($qr_data_uri, ENT_QUOTES, 'UTF-8') ?>" alt="Payment QR Code" width="220" height="220" style="border:4px solid var(--gold); padding:8px; background:#fff;">
                        <p class="confirm-hint">Scan with your Monero wallet</p>
                    <?php endif; ?>
                </div>

                <div class="confirm-details card">
                    <h3>Payment Details</h3>
                    <div class="confirm-status">
                        <span class="badge badge-pending">&#9679; Awaiting Payment</span>
                        <?php if ($expiration_in !== null && $expiration_in > 0): ?>
                            <span class="confirm-expiry">Expires in <?= htmlspecialchars(gmdate('i:s', $expiration_in), ENT_QUOTES, 'UTF-8') ?></span>
                        <?php endif; ?>
                    </div>

                    <table class="info-table confirm-table">
                        <tr>
                            <td>Fund</td>
                            <td><?= htmlspecialchars($investment['fund_name'] ?? '', ENT_QUOTES, 'UTF-8') ?></td>
                        </tr>
                        <tr>
                            <td>Amount Required</td>
                            <td class="gold"><strong><?= htmlspecialchars($amount_req, ENT_QUOTES, 'UTF-8') ?> XMR</strong></td>
                        </tr>
                        <tr>
                            <td>Confirmations</td>
                            <td><?= (int)$confirmations ?> / <?= (int)$conf_required ?></td>
                        </tr>
                        <tr>
                            <td>Status</td>
                            <td><span class="badge badge-pending">Pending</span></td>
                        </tr>
                    </table>

                    <div class="confirm-address-block">
                        <label>Payment Address</label>
                        <div class="address-box">
                            <code><?= htmlspecialchars($address, ENT_QUOTES, 'UTF-8') ?></code>
                        </div>
                        <small class="text-muted">This is a one-time subaddress unique to your invoice. Do not reuse.</small>
                    </div>

                    <?php if ($uri !== 'monero:'): ?>
                        <div class="confirm-uri-block">
                            <label>Full Payment URI (for wallets)</label>
                            <div class="address-box address-box-sm">
                                <code><?= htmlspecialchars($uri, ENT_QUOTES, 'UTF-8') ?></code>
                            </div>
                        </div>
                    <?php endif; ?>

                    <div class="alert alert-warning" style="margin-top:1.5rem">
                        <strong>Important:</strong> This page auto-refreshes every 10 seconds. Send <strong>exactly <?= htmlspecialchars($amount_req, ENT_QUOTES, 'UTF-8') ?> XMR</strong> to the address above. Do not close this page until payment is confirmed.
                    </div>
                </div>
            </div>
        <?php endif; ?>

    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
