<?php
/**
 * webapp/dashboard/index.php
 *
 * Main account dashboard: balance, active investments, recent transactions.
 */
require_once dirname(__DIR__) . '/includes/auth_guard.php';
require_once dirname(__DIR__) . '/includes/header.php';

$pdo = db();

// Account balance
$account = current_account();
$balance = number_format((float)($account['balance_usd'] ?? 0), 2);

// Active investments with fund names
$stmt = $pdo->prepare(
    'SELECT i.*, f.name AS fund_name, f.slug AS fund_slug, f.target_return
     FROM investments i
     JOIN funds f ON f.id = i.fund_id
     WHERE i.user_id = ?
     ORDER BY i.invested_at DESC'
);
$stmt->execute([$currentUserId]);
$investments = $stmt->fetchAll();

// Recent deposits (last 5)
$dStmt = $pdo->prepare(
    'SELECT * FROM deposits WHERE user_id = ? ORDER BY created_at DESC LIMIT 5'
);
$dStmt->execute([$currentUserId]);
$deposits = $dStmt->fetchAll();

// Recent withdrawals (last 5)
$wStmt = $pdo->prepare(
    'SELECT * FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC LIMIT 5'
);
$wStmt->execute([$currentUserId]);
$withdrawals = $wStmt->fetchAll();

include_header('Dashboard');
?>

<div class="container-fluid" style="max-width:1400px;">
  <div class="row min-vh-100">

    <!-- ── Sidebar ──────────────────────────────────────────────────────────── -->
    <nav class="col-lg-2 d-none d-lg-block p-0">
      <div class="dashboard-sidebar">
        <a href="/dashboard/index.php"  class="sidebar-link active"><i class="bi bi-speedometer2"></i> Dashboard</a>
        <a href="/dashboard/deposit.php" class="sidebar-link"><i class="bi bi-arrow-down-circle"></i> Deposit</a>
        <a href="/dashboard/withdraw.php" class="sidebar-link"><i class="bi bi-arrow-up-circle"></i> Withdraw</a>
        <a href="/dashboard/invest.php" class="sidebar-link"><i class="bi bi-graph-up-arrow"></i> Invest</a>
        <hr style="border-color:var(--xmr-border);margin:.5rem 1.5rem;">
        <a href="/index.php#funds" class="sidebar-link"><i class="bi bi-grid"></i> All Funds</a>
        <a href="/auth/logout.php" class="sidebar-link text-danger"><i class="bi bi-box-arrow-right"></i> Sign Out</a>
      </div>
    </nav>

    <!-- ── Main content ──────────────────────────────────────────────────────── -->
    <main class="col-lg-10 py-4 px-4">

      <div class="d-flex align-items-center justify-content-between mb-4">
        <div>
          <h2 class="fw-bold mb-0">Welcome back, <?= htmlspecialchars($_SESSION['full_name']) ?></h2>
          <div class="text-muted small mt-1">Your portfolio overview</div>
        </div>
        <div class="d-flex gap-2">
          <a href="/dashboard/deposit.php"  class="btn btn-accent btn-sm">+ Deposit</a>
          <a href="/dashboard/withdraw.php" class="btn btn-outline-accent btn-sm">Withdraw</a>
        </div>
      </div>

      <!-- Balance + quick actions -->
      <div class="row g-4 mb-4">
        <div class="col-md-4">
          <div class="balance-card">
            <div class="balance-label">Total Balance (USD)</div>
            <div class="balance-value mt-1">$<?= $balance ?></div>
            <div class="text-muted small mt-2">Available for investment</div>
            <div class="d-flex gap-2 mt-3">
              <a href="/dashboard/deposit.php"  class="btn btn-accent btn-sm">Deposit</a>
              <a href="/dashboard/withdraw.php" class="btn btn-outline-accent btn-sm">Withdraw</a>
            </div>
          </div>
        </div>
        <div class="col-md-4">
          <div class="xmr-card h-100 text-center">
            <div class="fs-1 text-accent mb-2"><i class="bi bi-graph-up-arrow"></i></div>
            <div class="fw-bold mb-1"><?= count(array_filter($investments, fn($i) => $i['status'] === 'active')) ?> Active Investment<?= count($investments) !== 1 ? 's' : '' ?></div>
            <p class="text-muted small mb-3">Across <?= count($investments) ?> fund<?= count($investments) !== 1 ? 's' : '' ?></p>
            <a href="/dashboard/invest.php" class="btn btn-outline-accent btn-sm">Invest More</a>
          </div>
        </div>
        <div class="col-md-4">
          <div class="xmr-card h-100 text-center">
            <div class="fs-1 text-accent mb-2"><i class="bi bi-shield-lock"></i></div>
            <div class="fw-bold mb-1">Privacy-First</div>
            <p class="text-muted small">Pay in XMR or BTC. No banks, no middlemen. Live CoinGecko rates.</p>
          </div>
        </div>
      </div>

      <!-- Active Investments -->
      <?php if (!empty($investments)): ?>
      <div class="xmr-card mb-4">
        <div class="d-flex justify-content-between align-items-center mb-3">
          <h5 class="fw-bold mb-0">Your Investments</h5>
          <a href="/dashboard/invest.php" class="btn btn-accent btn-sm">+ New Investment</a>
        </div>
        <div class="table-responsive">
          <table class="tx-table">
            <thead>
              <tr>
                <th>Fund</th><th>Amount (USD)</th><th>Status</th><th>Date</th>
              </tr>
            </thead>
            <tbody>
              <?php foreach ($investments as $inv): ?>
                <tr>
                  <td>
                    <span class="fw-semibold"><?= htmlspecialchars($inv['fund_name']) ?></span><br>
                    <span class="text-muted" style="font-size:.75rem;"><?= htmlspecialchars($inv['target_return']) ?> target</span>
                  </td>
                  <td>$<?= number_format((float)$inv['amount_usd'], 2) ?></td>
                  <td><span class="status-badge status-<?= htmlspecialchars($inv['status']) ?>"><?= htmlspecialchars($inv['status']) ?></span></td>
                  <td class="text-muted small"><?= date('d M Y', strtotime($inv['invested_at'])) ?></td>
                </tr>
              <?php endforeach; ?>
            </tbody>
          </table>
        </div>
      </div>
      <?php else: ?>
      <div class="xmr-card mb-4 text-center py-5">
        <div class="fs-1 text-muted mb-3"><i class="bi bi-graph-up"></i></div>
        <h5 class="fw-bold">No investments yet</h5>
        <p class="text-muted small">Explore our funds and invest from $250.</p>
        <a href="/dashboard/invest.php" class="btn btn-accent">Invest Now</a>
      </div>
      <?php endif; ?>

      <!-- Recent Deposits & Withdrawals side by side -->
      <div class="row g-4">
        <!-- Deposits -->
        <div class="col-md-6">
          <div class="xmr-card">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <h6 class="fw-bold mb-0">Recent Deposits</h6>
              <a href="/dashboard/deposit.php" class="btn btn-outline-accent btn-sm">+ Deposit</a>
            </div>
            <?php if (empty($deposits)): ?>
              <p class="text-muted small text-center py-3">No deposits yet.</p>
            <?php else: ?>
              <table class="tx-table">
                <thead><tr><th>Coin</th><th>Amount</th><th>USD</th><th>Status</th></tr></thead>
                <tbody>
                  <?php foreach ($deposits as $d): ?>
                    <tr>
                      <td class="fw-semibold"><?= htmlspecialchars($d['coin']) ?></td>
                      <td><?= rtrim(rtrim(number_format((float)$d['amount_coin'], 8), '0'), '.') ?></td>
                      <td>$<?= number_format((float)$d['amount_usd'], 2) ?></td>
                      <td><span class="status-badge status-<?= htmlspecialchars($d['status']) ?>"><?= $d['status'] ?></span></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            <?php endif; ?>
          </div>
        </div>

        <!-- Withdrawals -->
        <div class="col-md-6">
          <div class="xmr-card">
            <div class="d-flex justify-content-between align-items-center mb-3">
              <h6 class="fw-bold mb-0">Recent Withdrawals</h6>
              <a href="/dashboard/withdraw.php" class="btn btn-outline-accent btn-sm">Withdraw</a>
            </div>
            <?php if (empty($withdrawals)): ?>
              <p class="text-muted small text-center py-3">No withdrawals yet.</p>
            <?php else: ?>
              <table class="tx-table">
                <thead><tr><th>Coin</th><th>Amount</th><th>USD</th><th>Status</th></tr></thead>
                <tbody>
                  <?php foreach ($withdrawals as $w): ?>
                    <tr>
                      <td class="fw-semibold"><?= htmlspecialchars($w['coin']) ?></td>
                      <td><?= rtrim(rtrim(number_format((float)$w['amount_coin'], 8), '0'), '.') ?></td>
                      <td>$<?= number_format((float)$w['amount_usd'], 2) ?></td>
                      <td><span class="status-badge status-<?= htmlspecialchars($w['status']) ?>"><?= $w['status'] ?></span></td>
                    </tr>
                  <?php endforeach; ?>
                </tbody>
              </table>
            <?php endif; ?>
          </div>
        </div>
      </div>

    </main>
  </div>
</div>

<?php include_footer(); ?>
