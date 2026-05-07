<?php
require_once dirname(dirname(__DIR__)) . '/includes/config.php';
require_once dirname(dirname(__DIR__)) . '/includes/db.php';
require_once dirname(dirname(__DIR__)) . '/includes/auth.php';

auth_start_session();
$admin = auth_require_admin();

$payouts = [];
$total_xmr = '0';
try {
    $pdo = DB::get();
    $payouts = $pdo->query(
        "SELECT i.id, i.amount_xmr, i.confirmed_at, i.subaddress, i.acceptxmr_invoice_id,
                u.email AS user_email, u.full_name,
                f.name AS fund_name
         FROM investments i
         JOIN users u ON u.id = i.user_id
         JOIN funds f ON f.id = i.fund_id
         WHERE i.status = 'confirmed'
         ORDER BY i.confirmed_at DESC"
    )->fetchAll();
    $total_xmr = $pdo->query("SELECT COALESCE(SUM(amount_xmr),0) FROM investments WHERE status='confirmed'")->fetchColumn();
} catch (PDOException $e) {
    // empty
}

$page_title = 'Admin — Payouts';
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
        <h1>Confirmed Payouts</h1>
        <p><?= number_format(count($payouts)) ?> confirmed investment(s) · Total: <strong class="gold"><?= htmlspecialchars(rtrim(rtrim(number_format((float)$total_xmr, 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?> XMR</strong></p>
    </div>
</section>

<section class="section-dark">
    <div class="container">
        <div class="table-wrap">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>User</th>
                        <th>Fund</th>
                        <th>Amount (XMR)</th>
                        <th>Subaddress</th>
                        <th>Confirmed At</th>
                    </tr>
                </thead>
                <tbody>
                    <?php if (empty($payouts)): ?>
                        <tr><td colspan="6" class="text-center text-muted">No confirmed payouts yet.</td></tr>
                    <?php else: ?>
                        <?php foreach ($payouts as $p): ?>
                            <tr>
                                <td><?= (int)$p['id'] ?></td>
                                <td>
                                    <?= htmlspecialchars($p['user_email'], ENT_QUOTES, 'UTF-8') ?>
                                    <small class="text-muted"><?= htmlspecialchars($p['full_name'], ENT_QUOTES, 'UTF-8') ?></small>
                                </td>
                                <td><?= htmlspecialchars($p['fund_name'], ENT_QUOTES, 'UTF-8') ?></td>
                                <td class="gold"><strong><?= htmlspecialchars(rtrim(rtrim(number_format((float)$p['amount_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?></strong></td>
                                <td>
                                    <?php if ($p['subaddress']): ?>
                                        <code style="font-size:0.7rem"><?= htmlspecialchars(substr($p['subaddress'], 0, 20), ENT_QUOTES, 'UTF-8') ?>…</code>
                                    <?php else: ?>
                                        <span class="text-muted">—</span>
                                    <?php endif; ?>
                                </td>
                                <td><?= $p['confirmed_at'] ? htmlspecialchars(date('M j, Y H:i', strtotime($p['confirmed_at'])), ENT_QUOTES, 'UTF-8') : '—' ?></td>
                            </tr>
                        <?php endforeach; ?>
                    <?php endif; ?>
                </tbody>
            </table>
        </div>
    </div>
</section>

</main>
</body>
</html>
