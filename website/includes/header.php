<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/auth.php';

$page_title = $page_title ?? SITE_NAME;
$user = auth_check();
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?= htmlspecialchars($page_title, ENT_QUOTES, 'UTF-8') ?> — <?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></title>
    <link rel="stylesheet" href="/assets/css/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
<nav class="navbar">
    <div class="nav-container">
        <a href="/" class="nav-logo"><?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></a>
        <ul class="nav-links">
            <li><a href="/funds.php">Funds</a></li>
            <li><a href="/portfolio.php">Portfolio</a></li>
            <li><a href="/insights.php">Insights</a></li>
            <li><a href="/invest.php" class="btn-cta">Invest Now</a></li>
            <?php if ($user): ?>
                <li><a href="/dashboard.php">Dashboard</a></li>
                <li><a href="/logout.php">Logout</a></li>
            <?php else: ?>
                <li><a href="/login.php">Login</a></li>
                <li><a href="/register.php">Register</a></li>
            <?php endif; ?>
        </ul>
        <button class="nav-toggle" aria-label="Toggle navigation">&#9776;</button>
    </div>
</nav>
<main>
