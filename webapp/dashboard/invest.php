<?php
/**
 * webapp/dashboard/invest.php
 *
 * Invest USD balance into a fund. Min $250, max $1,000,000.
 */
require_once dirname(__DIR__) . '/includes/auth_guard.php';
require_once dirname(__DIR__) . '/includes/header.php';

$pdo     = db();
$account = current_account();
$balance = (float)($account['balance_usd'] ?? 0);

// Load all active funds
$funds     = $pdo->query('SELECT * FROM funds WHERE is_active = 1 ORDER BY id')->fetchAll();
$fundsById = array_column($funds, null, 'id');
$fundsBySlug = array_column($funds, null, 'slug');

$success = '';
$errors  = [];
$preSlug = $_GET['fund'] ?? '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();

    $fundId  = (int)($_POST['fund_id'] ?? 0);
    $usdAmt  = filter_var($_POST['invest_amount'] ?? '', FILTER_VALIDATE_FLOAT);
    $fund    = $fundsById[$fundId] ?? null;

    if (!$fund)                                             $errors[] = 'Please select a valid fund.';
    if ($usdAmt === false || $usdAmt <= 0)                 $errors[] = 'Please enter a valid investment amount.';
    if ($usdAmt < MIN_INVESTMENT)                          $errors[] = 'Minimum investment is $' . number_format(MIN_INVESTMENT, 2) . '.';
    if ($usdAmt > MAX_INVESTMENT)                          $errors[] = 'Maximum investment is $' . number_format(MAX_INVESTMENT, 0) . '.';
    if ($usdAmt > $balance)                                $errors[] = sprintf('Insufficient balance. Available: $%s.', number_format($balance, 2));

    if (empty($errors)) {
        try {
            $pdo->beginTransaction();

            // Deduct from balance
            $upd = $pdo->prepare(
                'UPDATE accounts SET balance_usd = balance_usd - ? WHERE user_id = ? AND balance_usd >= ?'
            );
            $upd->execute([$usdAmt, $currentUserId, $usdAmt]);
            if ($upd->rowCount() !== 1) {
                throw new RuntimeException('Balance changed. Please try again.');
            }

            // Create investment
            $ins = $pdo->prepare(
                'INSERT INTO investments (user_id, fund_id, amount_usd) VALUES (?, ?, ?)'
            );
            $ins->execute([$currentUserId, $fundId, $usdAmt]);
            $pdo->commit();

            $success = sprintf(
                'Successfully invested $%s in %s!',
                number_format($usdAmt, 2),
                htmlspecialchars($fund['name'])
            );
            $account = current_account();
            $balance = (float)($account['balance_usd'] ?? 0);
        } catch (Exception $e) {
            if ($pdo->inTransaction()) $pdo->rollBack();
            $errors[] = 'Error: ' . htmlspecialchars($e->getMessage());
        }
    }
}

$riskClass = ['Low'=>'risk-low','Medium'=>'risk-medium','High'=>'risk-high','Very High'=>'risk-very-high'];

include_header('Invest');
?>

<div class="container-fluid" style="max-width:1400px;">
  <div class="row min-vh-100">
    <nav class="col-lg-2 d-none d-lg-block p-0">
      <div class="dashboard-sidebar">
        <a href="/dashboard/index.php"   class="sidebar-link"><i class="bi bi-speedometer2"></i> Dashboard</a>
        <a href="/dashboard/deposit.php" class="sidebar-link"><i class="bi bi-arrow-down-circle"></i> Deposit</a>
        <a href="/dashboard/withdraw.php" class="sidebar-link"><i class="bi bi-arrow-up-circle"></i> Withdraw</a>
        <a href="/dashboard/invest.php"  class="sidebar-link active"><i class="bi bi-graph-up-arrow"></i> Invest</a>
        <hr style="border-color:var(--xmr-border);margin:.5rem 1.5rem;">
        <a href="/auth/logout.php" class="sidebar-link text-danger"><i class="bi bi-box-arrow-right"></i> Sign Out</a>
      </div>
    </nav>

    <main class="col-lg-10 py-4 px-4">
      <div class="mb-4">
        <h2 class="fw-bold mb-0">Invest in a Fund</h2>
        <div class="text-muted small mt-1">
          Available balance: <strong class="text-accent">$<?= number_format($balance, 2) ?></strong>
          &nbsp;·&nbsp; Min $<?= number_format(MIN_INVESTMENT, 0) ?> · Max $<?= number_format(MAX_INVESTMENT, 0) ?>
        </div>
      </div>

      <!-- Fund picker cards -->
      <div class="row g-3 mb-4" id="fund-picker">
        <?php foreach ($funds as $f):
          $rCls = $riskClass[$f['risk_level']] ?? 'risk-medium';
          $icons = ['bitcoin-fund'=>'bi-currency-bitcoin','monero-fund'=>'bi-shield-lock','crypto-blend'=>'bi-pie-chart','defi-yield'=>'bi-graph-up-arrow'];
          $icon = $icons[$f['slug']] ?? 'bi-bar-chart';
          $selected = ($preSlug === $f['slug']);
        ?>
          <div class="col-sm-6 col-xl-3">
            <label class="fund-card cursor-pointer <?= $selected ? 'selected-fund' : '' ?>"
                   style="<?= $selected ? 'border-color:var(--xmr-accent);' : '' ?>cursor:pointer;"
                   for="fund-<?= $f['id'] ?>">
              <div class="fund-card-header">
                <div class="d-flex align-items-center gap-2">
                  <input type="radio" name="fund_radio" id="fund-<?= $f['id'] ?>"
                         value="<?= $f['id'] ?>" class="fund-radio-input"
                         style="accent-color:var(--xmr-accent);"
                         <?= $selected ? 'checked' : '' ?>>
                  <div class="fund-icon" style="width:32px;height:32px;font-size:1rem;">
                    <i class="bi <?= $icon ?>"></i>
                  </div>
                  <div>
                    <div class="fund-name" style="font-size:.95rem;"><?= htmlspecialchars($f['name']) ?></div>
                    <span class="risk-badge <?= $rCls ?>"><?= htmlspecialchars($f['risk_level']) ?> Risk</span>
                  </div>
                </div>
              </div>
              <div class="fund-card-body" style="padding:1rem;">
                <div class="fund-return" style="font-size:1.3rem;"><?= htmlspecialchars($f['target_return']) ?></div>
                <div class="fund-return-label">Target annual return</div>
                <p class="text-muted small mt-2 mb-0"><?= htmlspecialchars($f['description']) ?></p>
              </div>
            </label>
          </div>
        <?php endforeach; ?>
      </div>

      <div class="row g-4">
        <div class="col-lg-6">
          <?php if ($success): ?>
            <div class="alert-xmr-success mb-4">
              <i class="bi bi-check-circle me-1"></i> <?= $success ?>
            </div>
            <a href="/dashboard/index.php" class="btn btn-outline-accent">View Dashboard</a>
          <?php else: ?>
            <?php if (!empty($errors)): ?>
              <div class="alert-xmr-danger mb-4">
                <?php foreach ($errors as $e): ?>
                  <div><i class="bi bi-x-circle me-1"></i> <?= $e ?></div>
                <?php endforeach; ?>
              </div>
            <?php endif; ?>

            <div class="xmr-card">
              <h5 class="fw-bold mb-3">Investment Details</h5>
              <form method="post" action="" id="invest-form">
                <input type="hidden" name="csrf_token" value="<?= csrf_token() ?>">
                <input type="hidden" name="fund_id"    id="hidden-fund-id"
                       value="<?= htmlspecialchars($_POST['fund_id'] ?? ($preSlug ? ($fundsBySlug[$preSlug]['id'] ?? '') : '')) ?>">

                <div class="mb-3">
                  <label class="form-label">Selected Fund</label>
                  <div class="conversion-box" id="selected-fund-display">
                    <span class="text-muted">Select a fund above</span>
                  </div>
                </div>

                <div class="mb-3">
                  <label for="invest-amount" class="form-label">Amount (USD)</label>
                  <div class="input-group">
                    <span class="input-group-text">$</span>
                    <input type="number" class="form-control" id="invest-amount" name="invest_amount"
                           min="<?= MIN_INVESTMENT ?>" max="<?= min(MAX_INVESTMENT, $balance) ?>"
                           step="0.01"
                           placeholder="min $<?= number_format(MIN_INVESTMENT, 0) ?>"
                           value="<?= htmlspecialchars($_POST['invest_amount'] ?? '') ?>">
                  </div>
                  <div class="form-text text-muted">
                    Min $<?= number_format(MIN_INVESTMENT, 0) ?> · Max $<?= number_format(MAX_INVESTMENT, 0) ?>
                    · Balance $<?= number_format($balance, 2) ?>
                  </div>
                </div>

                <button type="submit" class="btn btn-accent w-100 py-2" id="invest-btn" disabled>
                  Confirm Investment <i class="bi bi-arrow-right"></i>
                </button>
              </form>
            </div>
          <?php endif; ?>
        </div>

        <div class="col-lg-5 offset-lg-1">
          <div class="xmr-card">
            <h6 class="fw-bold mb-3 text-accent"><i class="bi bi-info-circle"></i> How Investing Works</h6>
            <ul class="text-muted small" style="padding-left:1.2rem;">
              <li class="mb-2">Select a fund and enter your USD investment amount.</li>
              <li class="mb-2">Minimum $<?= number_format(MIN_INVESTMENT, 0) ?> · Maximum $<?= number_format(MAX_INVESTMENT, 0) ?> per investment.</li>
              <li class="mb-2">The amount is deducted from your account balance immediately.</li>
              <li class="mb-2">You can hold multiple investments across different funds.</li>
              <li class="mb-2">To redeem, contact support or use the dashboard withdrawal flow.</li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  </div>
</div>

<script>
// Wire up fund radio selection to the hidden form field and display
const fundsData = <?= json_encode(array_values(array_map(fn($f) => [
    'id'   => $f['id'],
    'name' => $f['name'],
    'slug' => $f['slug'],
], $funds))) ?>;

const radios = document.querySelectorAll('.fund-radio-input');
const hiddenId = document.getElementById('hidden-fund-id');
const display  = document.getElementById('selected-fund-display');
const btn      = document.getElementById('invest-btn');

function updateFundSelection(radio) {
  const fund = fundsData.find(f => f.id == radio.value);
  if (fund) {
    hiddenId.value = fund.id;
    display.innerHTML = '<span class="fw-semibold text-accent">' + fund.name + '</span>';
    if (btn) btn.disabled = false;
  }
  // Remove highlight from all cards
  document.querySelectorAll('label.fund-card').forEach(l => l.style.borderColor = '');
  // Highlight selected
  radio.closest('label.fund-card').style.borderColor = 'var(--xmr-accent)';
}

radios.forEach(r => {
  r.addEventListener('change', () => updateFundSelection(r));
  if (r.checked) updateFundSelection(r);
});
</script>

<?php include_footer(); ?>
