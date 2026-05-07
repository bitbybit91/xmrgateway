<?php
require_once dirname(dirname(__DIR__)) . '/includes/config.php';
require_once dirname(dirname(__DIR__)) . '/includes/db.php';
require_once dirname(dirname(__DIR__)) . '/includes/auth.php';

auth_start_session();
$admin = auth_require_admin();

$investments = [];
try {
    $pdo = DB::get();
    $investments = $pdo->query(
        'SELECT i.id, i.amount_xmr, i.status, i.confirmations, i.created_at, i.confirmed_at,
                i.acceptxmr_invoice_id, i.subaddress,
                u.email AS user_email, u.full_name,
                f.name AS fund_name, f.apy_target
         FROM investments i
         JOIN users u ON u.id = i.user_id
         JOIN funds f ON f.id = i.fund_id
         ORDER BY i.created_at DESC'
    )->fetchAll();
} catch (PDOException $e) {
    // empty
}

$status_classes = [
    'pending'   => 'badge-pending',
    'confirmed' => 'badge-confirmed',
    'expired'   => 'badge-expired',
    'cancelled' => 'badge-cancelled',
];

$page_title = 'Admin — Investments';
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
        <h1>Investments</h1>
        <p><?= number_format(count($investments)) ?> total investment(s)</p>
    </div>
</section>

<section class="section-dark">
    <div class="container" style="overflow-x:auto">
        <div class="table-wrap">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>User</th>
                        <th>Fund</th>
                        <th>Amount (XMR)</th>
                        <th>Status</th>
                        <th>Confirmations</th>
                        <th>Invoice ID</th>
                        <th>Created</th>
                        <th>Confirmed</th>
                    </tr>
                </thead>
                <tbody>
                    <?php if (empty($investments)): ?>
                        <tr><td colspan="9" class="text-center text-muted">No investments found.</td></tr>
                    <?php else: ?>
                        <?php foreach ($investments as $inv): ?>
                            <tr>
                                <td><?= (int)$inv['id'] ?></td>
                                <td>
                                    <?= htmlspecialchars($inv['user_email'], ENT_QUOTES, 'UTF-8') ?>
                                    <small class="text-muted"><?= htmlspecialchars($inv['full_name'], ENT_QUOTES, 'UTF-8') ?></small>
                                </td>
                                <td>
                                    <?= htmlspecialchars($inv['fund_name'], ENT_QUOTES, 'UTF-8') ?>
                                    <small class="text-muted"><?= htmlspecialchars(number_format((float)$inv['apy_target'], 2), ENT_QUOTES, 'UTF-8') ?>%</small>
                                </td>
                                <td class="gold"><?= htmlspecialchars(rtrim(rtrim(number_format((float)$inv['amount_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><span class="badge <?= htmlspecialchars($status_classes[$inv['status']] ?? '', ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(ucfirst($inv['status']), ENT_QUOTES, 'UTF-8') ?></span></td>
                                <td><?= (int)$inv['confirmations'] ?> / <?= XMR_CONFIRMATIONS_REQUIRED ?></td>
                                <td><code style="font-size:0.7rem"><?= htmlspecialchars(substr($inv['acceptxmr_invoice_id'], 0, 16), ENT_QUOTES, 'UTF-8') ?>…</code></td>
                                <td><?= htmlspecialchars(date('M j, Y H:i', strtotime($inv['created_at'])), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= $inv['confirmed_at'] ? htmlspecialchars(date('M j, Y H:i', strtotime($inv['confirmed_at'])), ENT_QUOTES, 'UTF-8') : '—' ?></td>
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
