<?php
require_once dirname(dirname(__DIR__)) . '/includes/config.php';
require_once dirname(dirname(__DIR__)) . '/includes/db.php';
require_once dirname(dirname(__DIR__)) . '/includes/auth.php';

auth_start_session();
$admin = auth_require_admin();

$users = [];
try {
    $pdo   = DB::get();
    $users = $pdo->query(
        'SELECT u.id, u.email, u.full_name, u.kyc_status, u.login_attempts, u.locked_until,
                u.created_at, u.last_login,
                COUNT(i.id) AS investment_count
         FROM users u
         LEFT JOIN investments i ON i.user_id = u.id
         GROUP BY u.id
         ORDER BY u.created_at DESC'
    )->fetchAll();
} catch (PDOException $e) {
    // empty
}

$page_title = 'Admin — Users';
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
        <h1>Users</h1>
        <p><?= number_format(count($users)) ?> registered user(s)</p>
    </div>
</section>

<section class="section-dark">
    <div class="container">
        <div class="table-wrap">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Email</th>
                        <th>Full Name</th>
                        <th>KYC</th>
                        <th>Investments</th>
                        <th>Login Attempts</th>
                        <th>Locked Until</th>
                        <th>Last Login</th>
                        <th>Registered</th>
                    </tr>
                </thead>
                <tbody>
                    <?php if (empty($users)): ?>
                        <tr><td colspan="9" class="text-center text-muted">No users found.</td></tr>
                    <?php else: ?>
                        <?php foreach ($users as $u): ?>
                            <tr>
                                <td><?= (int)$u['id'] ?></td>
                                <td><?= htmlspecialchars($u['email'], ENT_QUOTES, 'UTF-8') ?></td>
                                <td><?= htmlspecialchars($u['full_name'], ENT_QUOTES, 'UTF-8') ?></td>
                                <td><span class="badge badge-<?= htmlspecialchars($u['kyc_status'], ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(ucfirst($u['kyc_status']), ENT_QUOTES, 'UTF-8') ?></span></td>
                                <td><?= (int)$u['investment_count'] ?></td>
                                <td><?= (int)$u['login_attempts'] ?></td>
                                <td><?= $u['locked_until'] ? htmlspecialchars($u['locked_until'], ENT_QUOTES, 'UTF-8') : '—' ?></td>
                                <td><?= $u['last_login'] ? htmlspecialchars(date('M j, Y H:i', strtotime($u['last_login'])), ENT_QUOTES, 'UTF-8') : '—' ?></td>
                                <td><?= htmlspecialchars(date('M j, Y', strtotime($u['created_at'])), ENT_QUOTES, 'UTF-8') ?></td>
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
