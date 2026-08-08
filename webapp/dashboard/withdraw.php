<?php
/**
 * webapp/dashboard/withdraw.php
 *
 * User requests a withdrawal. Balance is reserved; admin approves manually.
 */
require_once dirname(__DIR__) . '/includes/auth_guard.php';
require_once dirname(__DIR__) . '/includes/header.php';

$success = '';
$errors  = [];
$account = current_account();
$balance = (float)($account['balance_usd'] ?? 0);

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();

    $coin        = in_array($_POST['coin'] ?? '', ['XMR', 'BTC']) ? $_POST['coin'] : '';
    $usdAmt      = filter_var($_POST['usd_amount'] ?? '', FILTER_VALIDATE_FLOAT);
    $destination = trim($_POST['destination'] ?? '');

    if (!$coin)                                         $errors[] = 'Please select a coin.';
    if ($usdAmt === false || $usdAmt <= 0)             $errors[] = 'Please enter a valid amount.';
    if ($usdAmt > $balance)                             $errors[] = sprintf('Insufficient balance. Available: $%s.', number_format($balance, 2));
    if (strlen($destination) < 25)                     $errors[] = 'Please enter a valid wallet address.';

    if (empty($errors)) {
        // Fetch live rate
        $cacheFile = sys_get_temp_dir() . '/xmrgateway_prices.json';
        $priceData = file_exists($cacheFile) ? json_decode(file_get_contents($cacheFile), true) : null;
        $rate      = ($coin === 'BTC') ? ($priceData['btc'] ?? null) : ($priceData['xmr'] ?? null);

        if (!$rate) {
            $errors[] = 'Could not fetch live price. Please try again in a moment.';
        } else {
            $coinAmt = round($usdAmt / $rate, $coin === 'BTC' ? 8 : 6);

            try {
                $pdo = db();
                $pdo->beginTransaction();

                // Deduct balance
                $upd = $pdo->prepare(
                    'UPDATE accounts SET balance_usd = balance_usd - ? WHERE user_id = ? AND balance_usd >= ?'
                );
                $upd->execute([$usdAmt, $currentUserId, $usdAmt]);
                if ($upd->rowCount() !== 1) {
                    throw new RuntimeException('Balance changed during request. Please try again.');
                }

                // Create withdrawal record
                $ins = $pdo->prepare(
                    'INSERT INTO withdrawals (user_id, coin, amount_usd, usd_rate, amount_coin, destination)
                     VALUES (?, ?, ?, ?, ?, ?)'
                );
                $ins->execute([$currentUserId, $coin, $usdAmt, $rate, $coinAmt, $destination]);
                $pdo->commit();

                $success = sprintf(
                    'Withdrawal request submitted for %.6g %s (≈ $%s USD). Processing within 24 hours.',
                    $coinAmt, $coin, number_format($usdAmt, 2)
                );
                // Refresh balance
                $account = current_account();
                $balance = (float)($account['balance_usd'] ?? 0);
            } catch (Exception $e) {
                if (isset($pdo) && $pdo->inTransaction()) $pdo->rollBack();
                $errors[] = 'Error: ' . htmlspecialchars($e->getMessage());
            }
        }
    }
}

include_header('Withdraw Funds');
?>

<div class="container-fluid" style="max-width:1400px;">
  <div class="row min-vh-100">
    <nav class="col-lg-2 d-none d-lg-block p-0">
      <div class="dashboard-sidebar">
        <a href="/dashboard/index.php"    class="sidebar-link"><i class="bi bi-speedometer2"></i> Dashboard</a>
        <a href="/dashboard/deposit.php"  class="sidebar-link"><i class="bi bi-arrow-down-circle"></i> Deposit</a>
        <a href="/dashboard/withdraw.php" class="sidebar-link active"><i class="bi bi-arrow-up-circle"></i> Withdraw</a>
        <a href="/dashboard/invest.php"   class="sidebar-link"><i class="bi bi-graph-up-arrow"></i> Invest</a>
        <hr style="border-color:var(--xmr-border);margin:.5rem 1.5rem;">
        <a href="/auth/logout.php" class="sidebar-link text-danger"><i class="bi bi-box-arrow-right"></i> Sign Out</a>
      </div>
    </nav>

    <main class="col-lg-10 py-4 px-4">
      <div class="mb-4">
        <h2 class="fw-bold mb-0">Withdraw Funds</h2>
        <div class="text-muted small mt-1">Available balance: <strong class="text-accent">$<?= number_format($balance, 2) ?></strong></div>
      </div>

      <div class="row g-4">
        <div class="col-lg-6">
          <?php if ($success): ?>
            <div class="alert-xmr-success mb-4">
              <i class="bi bi-check-circle me-1"></i> <?= htmlspecialchars($success) ?>
            </div>
            <a href="/dashboard/index.php" class="btn btn-outline-accent">Back to Dashboard</a>
          <?php else: ?>
            <?php if (!empty($errors)): ?>
              <div class="alert-xmr-danger mb-4">
                <?php foreach ($errors as $e): ?>
                  <div><i class="bi bi-x-circle me-1"></i> <?= htmlspecialchars($e) ?></div>
                <?php endforeach; ?>
              </div>
            <?php endif; ?>

            <div class="xmr-card">
              <h5 class="fw-bold mb-3">Request a Withdrawal</h5>
              <form method="post" action="">
                <input type="hidden" name="csrf_token" value="<?= csrf_token() ?>">

                <div class="mb-3">
                  <label for="coin-select" class="form-label">Receive in</label>
                  <select class="form-select" id="coin-select" name="coin">
                    <option value="XMR">Monero (XMR)</option>
                    <option value="BTC">Bitcoin (BTC)</option>
                  </select>
                </div>

                <div class="mb-3">
                  <label for="usd-amount" class="form-label">USD Amount to Withdraw</label>
                  <div class="input-group">
                    <span class="input-group-text">$</span>
                    <input type="number" class="form-control" id="usd-amount" name="usd_amount"
                           min="1" max="<?= $balance ?>" step="0.01"
                           placeholder="e.g. 200"
                           value="<?= htmlspecialchars($_POST['usd_amount'] ?? '') ?>">
                  </div>
                  <div class="form-text text-muted">Maximum: $<?= number_format($balance, 2) ?></div>
                </div>

                <!-- Live conversion -->
                <div class="conversion-box mb-3" id="conv-display">
                  <span class="text-muted">Enter an amount above</span>
                </div>

                <div class="mb-4">
                  <label for="destination" class="form-label">Your Wallet Address</label>
                  <input type="text" class="form-control" id="destination" name="destination"
                         placeholder="Your XMR or BTC wallet address"
                         value="<?= htmlspecialchars($_POST['destination'] ?? '') ?>" required>
                  <div class="form-text text-muted">Double-check this address — crypto transactions are irreversible.</div>
                </div>

                <button type="submit" class="btn btn-accent w-100 py-2">
                  Submit Withdrawal Request <i class="bi bi-arrow-right"></i>
                </button>
              </form>
            </div>
          <?php endif; ?>
        </div>

        <div class="col-lg-5 offset-lg-1">
          <div class="xmr-card">
            <h6 class="fw-bold mb-3 text-accent"><i class="bi bi-info-circle"></i> Withdrawal Policy</h6>
            <ul class="text-muted small" style="padding-left:1.2rem;">
              <li class="mb-2">Minimum withdrawal: $1.00 USD.</li>
              <li class="mb-2">Funds are deducted from your balance immediately upon request.</li>
              <li class="mb-2">Requests are processed manually within 24 hours on business days.</li>
              <li class="mb-2">You will receive the equivalent coin amount at the CoinGecko rate at time of request.</li>
              <li class="mb-2">Verify your wallet address carefully — crypto transfers are irreversible.</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>

<?php include_footer(); ?>
