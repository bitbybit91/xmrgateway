<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';

$page_title = 'Our Funds';

try {
    $pdo = DB::get();
    $stmt = $pdo->prepare('SELECT * FROM funds WHERE active = 1 ORDER BY tier ASC');
    $stmt->execute();
    $funds = $stmt->fetchAll();
} catch (PDOException $e) {
    $funds = [];
}

$tier_labels = [1 => 'Tier I', 2 => 'Tier II', 3 => 'Tier III'];
$tier_names  = [1 => 'Venture', 2 => 'Token', 3 => 'Liquid'];

require_once dirname(__DIR__) . '/includes/header.php';
?>

<section class="page-hero page-hero-sm">
    <div class="container">
        <span class="section-label">Investment Vehicles</span>
        <h1>Our Funds</h1>
        <p>Three institutional-grade strategies covering the full spectrum of blockchain opportunities.</p>
    </div>
</section>

<section class="section-dark">
    <div class="container">
        <?php if (empty($funds)): ?>
            <p class="text-center text-muted">No active funds at this time. Please check back soon.</p>
        <?php else: ?>
            <div class="fund-cards funds-page">
                <?php foreach ($funds as $fund): ?>
                    <div class="fund-card">
                        <div class="fund-card-tier tier-<?= (int)$fund['tier'] ?>">
                            <?= htmlspecialchars($tier_labels[$fund['tier']] ?? 'Fund', ENT_QUOTES, 'UTF-8') ?>
                        </div>
                        <h3><?= htmlspecialchars($fund['name'], ENT_QUOTES, 'UTF-8') ?></h3>
                        <p><?= htmlspecialchars($fund['description'], ENT_QUOTES, 'UTF-8') ?></p>
                        <div class="fund-meta">
                            <div class="fund-meta-item">
                                <span class="fund-meta-label">Minimum Investment</span>
                                <span class="fund-meta-value gold"><?= htmlspecialchars(rtrim(rtrim(number_format((float)$fund['min_investment_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?> XMR</span>
                            </div>
                            <div class="fund-meta-item">
                                <span class="fund-meta-label">Target APY</span>
                                <span class="fund-meta-value gold"><?= htmlspecialchars(number_format((float)$fund['apy_target'], 2), ENT_QUOTES, 'UTF-8') ?>%</span>
                            </div>
                        </div>
                        <a href="/invest.php?fund=<?= urlencode($fund['slug']) ?>" class="btn-primary">Invest Now</a>
                    </div>
                <?php endforeach; ?>
            </div>
        <?php endif; ?>
    </div>
</section>

<section class="section-light">
    <div class="container text-center">
        <h2>Not sure which fund is right for you?</h2>
        <p class="section-subtitle">Our investment strategies are designed to fit different risk tolerances and time horizons. All funds accept XMR for maximum privacy and security.</p>
        <a href="/insights.php" class="btn-secondary">Read Our Research</a>
    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
