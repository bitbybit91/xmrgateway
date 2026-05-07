<?php
require_once dirname(dirname(__DIR__)) . '/includes/config.php';
require_once dirname(dirname(__DIR__)) . '/includes/db.php';
require_once dirname(dirname(__DIR__)) . '/includes/auth.php';

auth_start_session();
$admin = auth_require_admin();

$stats = [
    'total_users'        => 0,
    'total_investments'  => 0,
    'pending'            => 0,
    'confirmed'          => 0,
    'expired'            => 0,
    'total_xmr'          => '0',
];

try {
    $pdo = DB::get();
    $stats['total_users']       = (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn();
    $stats['total_investments'] = (int)$pdo->query('SELECT COUNT(*) FROM investments')->fetchColumn();
    $stats['pending']           = (int)$pdo->query("SELECT COUNT(*) FROM investments WHERE status='pending'")->fetchColumn();
    $stats['confirmed']         = (int)$pdo->query("SELECT COUNT(*) FROM investments WHERE status='confirmed'")->fetchColumn();
    $stats['expired']           = (int)$pdo->query("SELECT COUNT(*) FROM investments WHERE status='expired'")->fetchColumn();
    $stats['total_xmr']         = $pdo->query("SELECT COALESCE(SUM(amount_xmr),0) FROM investments WHERE status='confirmed'")->fetchColumn();
} catch (PDOException $e) {
    // stats remain at 0
}

$page_title = 'Admin Dashboard';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($page_title, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></title>
    <link rel="stylesheet" href="/assets/css/style.css">
</head>
<body>
<nav class="navbar admin-navbar">
    <div class="nav-container">
        <a href="/admin/" class="nav-logo"><?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?> <span class="admin-badge">Admin</span></a>
        <ul class="nav-links">
            <li><a href="/admin/">Dashboard</a></li>
            <li><a href="/admin/users.php">Users</a></li>
            <li><a href="/admin/investments.php">Investments</a></li>
            <li><a href="/admin/payouts.php">Payouts</a></li>
            <li><a href="/">Public Site</a></li>
            <li><a href="/logout.php">Logout</a></li>
        </ul>
    </div>
</nav>
<main>

<section class="page-hero page-hero-sm">
    <div class="container">
        <span class="section-label">Administration</span>
        <h1>Dashboard</h1>
        <p>Welcome, <?= htmlspecialchars($admin['username'], ENT_QUOTES, 'UTF-8') ?>. Role: <?= htmlspecialchars($admin['role'], ENT_QUOTES, 'UTF-8') ?></p>
    </div>
</section>

<section class="section-dark">
    <div class="container">
        <div class="stat-grid">
            <div class="stat-card">
                <span class="stat-number"><?= number_format($stats['total_users']) ?></span>
                <span class="stat-label">Total Users</span>
            </div>
            <div class="stat-card">
                <span class="stat-number"><?= number_format($stats['total_investments']) ?></span>
                <span class="stat-label">Total Investments</span>
            </div>
            <div class="stat-card">
                <span class="stat-number" style="color:var(--gold)"><?= number_format($stats['pending']) ?></span>
                <span class="stat-label">Pending</span>
            </div>
            <div class="stat-card">
                <span class="stat-number" style="color:#4caf50"><?= number_format($stats['confirmed']) ?></span>
                <span class="stat-label">Confirmed</span>
            </div>
            <div class="stat-card">
                <span class="stat-number" style="color:#f44336"><?= number_format($stats['expired']) ?></span>
                <span class="stat-label">Expired</span>
            </div>
            <div class="stat-card">
                <span class="stat-number"><?= htmlspecialchars(rtrim(rtrim(number_format((float)$stats['total_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?></span>
                <span class="stat-label">XMR Confirmed</span>
            </div>
        </div>

        <div class="admin-quick-links" style="margin-top:2rem; display:flex; gap:1rem; flex-wrap:wrap;">
            <a href="/admin/users.php" class="btn-secondary">Manage Users</a>
            <a href="/admin/investments.php" class="btn-secondary">View Investments</a>
            <a href="/admin/payouts.php" class="btn-secondary">View Payouts</a>
        </div>
    </div>
</section>

</main>
</body>
</html>
