<?php
/**
 * webapp/dashboard/deposit.php
 *
 * User selects XMR or BTC, enters a USD amount, sees live CoinGecko conversion,
 * and submits to create a pending deposit record. The receiving address (from
 * config/crypto.config.json) is displayed for payment.
 */
require_once dirname(__DIR__) . '/includes/auth_guard.php';
require_once dirname(__DIR__) . '/includes/header.php';

$success = '';
$errors  = [];
$deposit = null;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();

    $coin   = in_array($_POST['coin'] ?? '', ['XMR', 'BTC']) ? $_POST['coin'] : '';
    $usdAmt = filter_var($_POST['usd_amount'] ?? '', FILTER_VALIDATE_FLOAT);

    if (!$coin)                              $errors[] = 'Please select a payment coin (XMR or BTC).';
    if ($usdAmt === false || $usdAmt <= 0)  $errors[] = 'Please enter a valid USD amount.';
    if ($usdAmt < 1)                         $errors[] = 'Minimum deposit is $1.00.';

    // Fetch live rate from local cache/CoinGecko
    if (empty($errors)) {
        $cacheFile = sys_get_temp_dir() . '/xmrgateway_prices.json';
        $priceData = file_exists($cacheFile) ? json_decode(file_get_contents($cacheFile), true) : null;
        $rate      = ($coin === 'BTC') ? ($priceData['btc'] ?? null) : ($priceData['xmr'] ?? null);

        if (!$rate) {
            $errors[] = 'Could not fetch live price. Please try again in a moment.';
        } else {
            $coinAmt = round($usdAmt / $rate, $coin === 'BTC' ? 8 : 6);
            $address = ($coin === 'BTC') ? BTC_ADDRESS : XMR_ADDRESS;

            if (empty($address)) {
                $errors[] = 'Receiving address not configured. Please contact support.';
            } else {
                // Insert pending deposit
                $stmt = db()->prepare(
                    'INSERT INTO deposits (user_id, coin, amount_coin, usd_rate, amount_usd, address)
                     VALUES (?, ?, ?, ?, ?, ?)'
                );
                $stmt->execute([$currentUserId, $coin, $coinAmt, $rate, $usdAmt, $address]);
                $depositId = (int) db()->lastInsertId();

                // Return the created row
                $dStmt = db()->prepare('SELECT * FROM deposits WHERE id = ?');
                $dStmt->execute([$depositId]);
                $deposit = $dStmt->fetch();
                $success = 'Your deposit has been created. Send the exact amount below to the address shown.';
            }
        }
    }
}

$account = current_account();
$balance = number_format((float)($account['balance_usd'] ?? 0), 2);

include_header('Deposit Funds');
?>

<div class="container-fluid" style="max-width:1400px;">
  <div class="row min-vh-100">
    <!-- Sidebar -->
    <nav class="col-lg-2 d-none d-lg-block p-0">
      <div class="dashboard-sidebar">
        <a href="/dashboard/index.php"   class="sidebar-link"><i class="bi bi-speedometer2"></i> Dashboard</a>
        <a href="/dashboard/deposit.php" class="sidebar-link active"><i class="bi bi-arrow-down-circle"></i> Deposit</a>
        <a href="/dashboard/withdraw.php" class="sidebar-link"><i class="bi bi-arrow-up-circle"></i> Withdraw</a>
        <a href="/dashboard/invest.php"  class="sidebar-link"><i class="bi bi-graph-up-arrow"></i> Invest</a>
        <hr style="border-color:var(--xmr-border);margin:.5rem 1.5rem;">
        <a href="/auth/logout.php" class="sidebar-link text-danger"><i class="bi bi-box-arrow-right"></i> Sign Out</a>
      </div>
    </nav>

    <main class="col-lg-10 py-4 px-4">
      <div class="mb-4">
        <h2 class="fw-bold mb-0">Deposit Funds</h2>
        <div class="text-muted small mt-1">Current balance: <strong class="text-accent">$<?= $balance ?></strong></div>
      </div>

      <div class="row g-4">
        <div class="col-lg-6">
          <?php if ($success && $deposit): ?>
            <!-- ── Payment instructions ───────────────────────────────────────── -->
            <div class="alert-xmr-success mb-4">
              <i class="bi bi-check-circle me-1"></i> <?= htmlspecialchars($success) ?>
            </div>
            <div class="xmr-card">
              <h5 class="fw-bold mb-3">Send Payment</h5>
              <div class="mb-3">
                <div class="form-label">Coin</div>
                <div class="fw-bold fs-5 text-accent"><?= htmlspecialchars($deposit['coin']) ?></div>
              </div>
              <div class="mb-3">
                <div class="form-label">Amount to Send</div>
                <div class="fw-bold fs-4 text-accent">
                  <?= rtrim(rtrim(number_format((float)$deposit['amount_coin'], 8), '0'), '.') ?>
                  <?= htmlspecialchars($deposit['coin']) ?>
                </div>
                <div class="text-muted small">≈ $<?= number_format((float)$deposit['amount_usd'], 2) ?> USD at $<?= number_format((float)$deposit['usd_rate'], 2) ?>/<?= $deposit['coin'] ?></div>
              </div>
              <div class="mb-3">
                <div class="form-label">Send to Address</div>
                <div class="conversion-box">
                  <code style="word-break:break-all;font-size:.85rem;"><?= htmlspecialchars($deposit['address']) ?></code>
                </div>
              </div>
              <p class="text-muted small mb-3">
                <i class="bi bi-info-circle"></i>
                Send the exact amount in one transaction. Your USD balance will be credited
                once the payment is confirmed on-chain (typically within 10–30 minutes).
              </p>
              <a href="/dashboard/index.php" class="btn btn-outline-accent btn-sm">Back to Dashboard</a>
            </div>
          <?php else: ?>
            <?php if (!empty($errors)): ?>
              <div class="alert-xmr-danger mb-4">
                <?php foreach ($errors as $e): ?>
                  <div><i class="bi bi-x-circle me-1"></i> <?= htmlspecialchars($e) ?></div>
                <?php endforeach; ?>
              </div>
            <?php endif; ?>

            <div class="xmr-card">
              <h5 class="fw-bold mb-3">Create a Deposit</h5>
              <form method="post" action="">
                <input type="hidden" name="csrf_token" value="<?= csrf_token() ?>">

                <div class="mb-3">
                  <label for="coin-select" class="form-label">Pay with</label>
                  <select class="form-select" id="coin-select" name="coin">
                    <option value="XMR" <?= (($_POST['coin'] ?? '') === 'XMR') ? 'selected' : '' ?>>
                      Monero (XMR)
                    </option>
                    <option value="BTC" <?= (($_POST['coin'] ?? '') === 'BTC') ? 'selected' : '' ?>>
                      Bitcoin (BTC)
                    </option>
                  </select>
                </div>

                <div class="mb-3">
                  <label for="usd-amount" class="form-label">Amount in USD</label>
                  <div class="input-group">
                    <span class="input-group-text">$</span>
                    <input type="number" class="form-control" id="usd-amount" name="usd_amount"
                           min="1" step="0.01" placeholder="e.g. 500"
                           value="<?= htmlspecialchars($_POST['usd_amount'] ?? '') ?>">
                  </div>
                  <div class="form-text text-muted">Minimum deposit: $1.00</div>
                </div>

                <!-- Live conversion display -->
                <div class="conversion-box mb-4" id="conv-display">
                  <span class="text-muted">Enter an amount above</span>
                </div>

                <button type="submit" class="btn btn-accent w-100 py-2">
                  Create Deposit <i class="bi bi-arrow-right"></i>
                </button>
              </form>
            </div>
          <?php endif; ?>
        </div>

        <!-- Info panel -->
        <div class="col-lg-5 offset-lg-1">
          <div class="xmr-card">
            <h6 class="fw-bold mb-3 text-accent"><i class="bi bi-info-circle"></i> How Deposits Work</h6>
            <ol class="text-muted small" style="padding-left:1.2rem;">
              <li class="mb-2">Choose XMR or BTC and enter the USD value you want to deposit.</li>
              <li class="mb-2">We show you the exact coin amount using CoinGecko's live price.</li>
              <li class="mb-2">Send that amount to the address shown — one transaction, exact amount.</li>
              <li class="mb-2">Once the network confirms your payment (usually under 30 min), your USD balance is updated.</li>
            </ol>
            <hr class="section-divider my-3">
            <div class="text-muted small">
              <i class="bi bi-shield-check text-accent"></i>
              Prices update every 60 seconds via the CoinGecko public API.
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>

<?php include_footer(); ?>
