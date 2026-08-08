<?php
/**
 * webapp/index.php
 *
 * Landing page — hero, stats, fund grid, how-it-works section.
 */
require_once __DIR__ . '/config/app.php';
require_once __DIR__ . '/config/db.php';
require_once __DIR__ . '/includes/header.php';

// Load active funds
try {
    $stmt  = db()->query('SELECT * FROM funds WHERE is_active = 1 ORDER BY id');
    $funds = $stmt->fetchAll();
} catch (Exception $e) {
    $funds = [];
}

$loggedIn = !empty($_SESSION['user_id']);

include_header('Institutional Crypto Investment', 'has-hero');

$riskClass = ['Low' => 'risk-low', 'Medium' => 'risk-medium', 'High' => 'risk-high', 'Very High' => 'risk-very-high'];
$fundIcons = ['bitcoin-fund' => 'bi-currency-bitcoin', 'monero-fund' => 'bi-shield-lock', 'crypto-blend' => 'bi-pie-chart', 'defi-yield' => 'bi-graph-up-arrow'];
?>

<!-- ── Hero ─────────────────────────────────────────────────────────────────── -->
<section class="xmr-hero">
  <div class="container">
    <div class="row align-items-center g-5">
      <div class="col-lg-7">
        <div class="hero-eyebrow">Privacy-First · Non-Custodial · Crypto Native</div>
        <h1 class="hero-headline">
          Institutional-Grade<br>
          <span class="highlight">Crypto Investment</span><br>
          For Everyone
        </h1>
        <p class="hero-sub">
          Invest in professionally managed crypto funds — from Bitcoin to privacy-first Monero —
          starting from just $250. Pay securely with XMR or BTC. No banks, no middlemen.
        </p>
        <div class="d-flex flex-wrap gap-3 mt-4">
          <?php if ($loggedIn): ?>
            <a href="/dashboard/index.php" class="btn-accent btn btn-lg px-4">My Dashboard</a>
          <?php else: ?>
            <a href="/auth/register.php" class="btn-accent btn btn-lg px-4">Open Free Account</a>
            <a href="#funds" class="btn btn-outline-accent btn-lg px-4">View Funds</a>
          <?php endif; ?>
        </div>
        <!-- Live price ticker -->
        <div class="d-flex gap-4 mt-4 pt-2">
          <div class="small text-muted">
            <i class="bi bi-currency-bitcoin text-accent"></i>
            BTC <span id="ticker-btc" class="text-accent fw-semibold">—</span>
          </div>
          <div class="small text-muted">
            <i class="bi bi-shield-lock text-accent"></i>
            XMR <span id="ticker-xmr" class="text-accent fw-semibold">—</span>
          </div>
          <div class="small text-muted">via CoinGecko</div>
        </div>
      </div>
      <div class="col-lg-5 d-none d-lg-block text-center">
        <!-- Decorative stats panel -->
        <div class="xmr-card p-4" style="max-width:320px;margin:auto;">
          <div class="text-muted small mb-3 text-uppercase fw-semibold" style="letter-spacing:.1em;font-size:.72rem;">
            Platform Snapshot
          </div>
          <div class="d-flex flex-column gap-3">
            <div class="d-flex justify-content-between align-items-center">
              <span class="text-muted small">Investment Funds</span>
              <span class="fw-bold text-accent"><?= count($funds) ?></span>
            </div>
            <hr class="section-divider m-0">
            <div class="d-flex justify-content-between align-items-center">
              <span class="text-muted small">Min. Investment</span>
              <span class="fw-bold">$250</span>
            </div>
            <hr class="section-divider m-0">
            <div class="d-flex justify-content-between align-items-center">
              <span class="text-muted small">Max. Investment</span>
              <span class="fw-bold">$1,000,000</span>
            </div>
            <hr class="section-divider m-0">
            <div class="d-flex justify-content-between align-items-center">
              <span class="text-muted small">Payment Methods</span>
              <span class="fw-bold text-accent">XMR &amp; BTC</span>
            </div>
            <hr class="section-divider m-0">
            <div class="d-flex justify-content-between align-items-center">
              <span class="text-muted small">Price Source</span>
              <span class="fw-bold small">CoinGecko (live)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- ── Stats row ─────────────────────────────────────────────────────────────── -->
<section class="py-0 border-bottom" style="border-color:var(--xmr-border)!important;background:var(--xmr-surface);">
  <div class="container">
    <div class="row g-0">
      <div class="col-6 col-md-3"><div class="stat-box"><div class="stat-value"><?= count($funds) ?></div><div class="stat-label">Active Funds</div></div></div>
      <div class="col-6 col-md-3"><div class="stat-box"><div class="stat-value">$250</div><div class="stat-label">Minimum Investment</div></div></div>
      <div class="col-6 col-md-3"><div class="stat-box"><div class="stat-value">2</div><div class="stat-label">Crypto Payment Options</div></div></div>
      <div class="col-6 col-md-3"><div class="stat-box"><div class="stat-value">Live</div><div class="stat-label">CoinGecko Pricing</div></div></div>
    </div>
  </div>
</section>

<!-- ── Funds ──────────────────────────────────────────────────────────────────── -->
<section class="py-6 py-md-7" id="funds" style="padding-top:5rem;padding-bottom:5rem;">
  <div class="container">
    <div class="row mb-5">
      <div class="col-lg-7">
        <div class="section-label">Our Funds</div>
        <h2 class="section-title">Choose Your Investment Strategy</h2>
        <p class="text-muted mt-2">
          Each fund is managed to a defined mandate. Minimum investment $250 · Maximum $1,000,000 per fund.
          Pay with Monero (XMR) or Bitcoin (BTC); we convert at live CoinGecko rates.
        </p>
      </div>
    </div>

    <?php if (empty($funds)): ?>
      <div class="alert-xmr-danger">
        <i class="bi bi-exclamation-triangle-fill me-2"></i>
        Could not load funds. Please ensure the database is configured and seeded.
      </div>
    <?php else: ?>
      <div class="row g-4">
        <?php foreach ($funds as $fund):
          $icon  = $fundIcons[$fund['slug']] ?? 'bi-bar-chart';
          $rCls  = $riskClass[$fund['risk_level']] ?? 'risk-medium';
          $desc  = htmlspecialchars($fund['description']);
          $name  = htmlspecialchars($fund['name']);
          $ret   = htmlspecialchars($fund['target_return']);
          $risk  = htmlspecialchars($fund['risk_level']);
          $slug  = htmlspecialchars($fund['slug']);
          $minI  = number_format((float)$fund['min_investment'], 0);
          $maxI  = number_format((float)$fund['max_investment'], 0);
        ?>
          <div class="col-md-6 col-xl-3">
            <div class="fund-card">
              <div class="fund-card-header">
                <div class="fund-icon"><i class="bi <?= $icon ?>"></i></div>
                <h3 class="fund-name"><?= $name ?></h3>
                <div class="d-flex align-items-center gap-2 mt-1">
                  <span class="risk-badge <?= $rCls ?>"><?= $risk ?> Risk</span>
                  <span class="fund-strategy"><?= htmlspecialchars($fund['strategy']) ?></span>
                </div>
              </div>
              <div class="fund-card-body">
                <p class="text-muted small mb-3"><?= $desc ?></p>
                <div class="fund-return"><?= $ret ?></div>
                <div class="fund-return-label">Target annual return</div>
                <div class="mt-3 small text-muted">
                  <i class="bi bi-arrow-down-right-circle text-accent"></i>
                  Min $<?= $minI ?> &nbsp;·&nbsp; Max $<?= $maxI ?>
                </div>
              </div>
              <div class="fund-card-footer">
                <?php if ($loggedIn): ?>
                  <a href="/dashboard/invest.php?fund=<?= $slug ?>"
                     class="btn btn-accent w-100">
                    Invest Now <i class="bi bi-arrow-right"></i>
                  </a>
                <?php else: ?>
                  <a href="/auth/register.php"
                     class="btn btn-outline-accent w-100">
                    Open Account to Invest
                  </a>
                <?php endif; ?>
              </div>
            </div>
          </div>
        <?php endforeach; ?>
      </div>
    <?php endif; ?>
  </div>
</section>

<!-- ── How It Works ───────────────────────────────────────────────────────────── -->
<section id="how-it-works" style="padding-top:5rem;padding-bottom:5rem;background:var(--xmr-surface);">
  <div class="container">
    <div class="row mb-5">
      <div class="col-lg-6">
        <div class="section-label">How It Works</div>
        <h2 class="section-title">Start Investing in 4 Steps</h2>
      </div>
    </div>
    <div class="row g-4">
      <?php
      $steps = [
        ['num'=>'1', 'title'=>'Create Your Account',
         'body'=>'Register with your email and a strong password. Takes under 60 seconds — no ID upload required.',
         'icon'=>'bi-person-plus'],
        ['num'=>'2', 'title'=>'Deposit Crypto',
         'body'=>'Fund your account with Monero (XMR) or Bitcoin (BTC). We convert your deposit to USD at live CoinGecko rates and credit your balance instantly on confirmation.',
         'icon'=>'bi-arrow-down-circle'],
        ['num'=>'3', 'title'=>'Choose a Fund',
         'body'=>'Browse our funds, review each strategy and risk level, then invest any amount between $250 and $1,000,000 from your account balance.',
         'icon'=>'bi-graph-up-arrow'],
        ['num'=>'4', 'title'=>'Withdraw Anytime',
         'body'=>'Request a withdrawal in XMR or BTC at any time. We process requests within 24 hours and pay out at the market rate.',
         'icon'=>'bi-arrow-up-circle'],
      ];
      foreach ($steps as $s): ?>
        <div class="col-sm-6 col-lg-3">
          <div class="xmr-card h-100">
            <div class="step-number mb-3"><?= $s['num'] ?></div>
            <div class="mb-2 fs-4 text-accent"><i class="bi <?= $s['icon'] ?>"></i></div>
            <h5 class="fw-bold mb-2"><?= $s['title'] ?></h5>
            <p class="text-muted small mb-0"><?= $s['body'] ?></p>
          </div>
        </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<!-- ── CTA ────────────────────────────────────────────────────────────────────── -->
<section style="padding-top:5rem;padding-bottom:5rem;background:var(--xmr-bg);">
  <div class="container text-center">
    <h2 class="section-title mb-3">Ready to Invest?</h2>
    <p class="text-muted mb-4" style="max-width:48ch;margin:auto;">
      Open a free account and start investing in crypto funds with as little as $250,
      payable in Monero or Bitcoin.
    </p>
    <?php if ($loggedIn): ?>
      <a href="/dashboard/index.php" class="btn btn-accent btn-lg px-5">Go to Dashboard</a>
    <?php else: ?>
      <a href="/auth/register.php" class="btn btn-accent btn-lg px-5">Open Free Account</a>
    <?php endif; ?>
  </div>
</section>

<?php include_footer(); ?>
