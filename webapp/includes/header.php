<?php
/**
 * webapp/includes/header.php
 *
 * Call: include_header('Page Title');
 * Variables expected in scope:
 *   $pageTitle  — string
 *   $bodyClass  — optional string of extra <body> class names
 */
function include_header(string $pageTitle, string $bodyClass = ''): void
{
    $loggedIn = !empty($_SESSION['user_id']);
    $name     = $_SESSION['full_name'] ?? '';
    ?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title><?= htmlspecialchars($pageTitle) ?> — <?= SITE_NAME ?></title>

  <!-- Bootstrap 5 -->
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
        integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH"
        crossorigin="anonymous">

  <!-- Bootstrap Icons -->
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

  <!-- Google Fonts: Inter (clean finance look) -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
        rel="stylesheet">

  <!-- Site styles -->
  <link rel="stylesheet" href="<?= SITE_URL ?>/assets/css/style.css">
</head>
<body class="<?= htmlspecialchars($bodyClass) ?>">

<!-- ── Navigation ─────────────────────────────────────────────────────────── -->
<nav class="navbar navbar-expand-lg navbar-dark xmr-navbar fixed-top">
  <div class="container">
    <a class="navbar-brand fw-bold" href="<?= SITE_URL ?>/index.php">
      <span class="brand-accent">XMR</span> Gateway Capital
    </a>
    <button class="navbar-toggler" type="button"
            data-bs-toggle="collapse" data-bs-target="#mainNav">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse" id="mainNav">
      <ul class="navbar-nav me-auto mb-2 mb-lg-0">
        <li class="nav-item">
          <a class="nav-link" href="<?= SITE_URL ?>/index.php#funds">Funds</a>
        </li>
        <li class="nav-item">
          <a class="nav-link" href="<?= SITE_URL ?>/index.php#how-it-works">How It Works</a>
        </li>
      </ul>
      <ul class="navbar-nav ms-auto mb-2 mb-lg-0">
        <?php if ($loggedIn): ?>
          <li class="nav-item">
            <a class="nav-link" href="<?= SITE_URL ?>/dashboard/index.php">
              <i class="bi bi-speedometer2"></i> Dashboard
            </a>
          </li>
          <li class="nav-item dropdown">
            <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
              <i class="bi bi-person-circle"></i> <?= htmlspecialchars($name) ?>
            </a>
            <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
              <li><a class="dropdown-item" href="<?= SITE_URL ?>/dashboard/deposit.php">
                <i class="bi bi-arrow-down-circle"></i> Deposit
              </a></li>
              <li><a class="dropdown-item" href="<?= SITE_URL ?>/dashboard/withdraw.php">
                <i class="bi bi-arrow-up-circle"></i> Withdraw
              </a></li>
              <li><hr class="dropdown-divider"></li>
              <li><a class="dropdown-item text-danger" href="<?= SITE_URL ?>/auth/logout.php">
                <i class="bi bi-box-arrow-right"></i> Sign Out
              </a></li>
            </ul>
          </li>
        <?php else: ?>
          <li class="nav-item">
            <a class="nav-link" href="<?= SITE_URL ?>/auth/login.php">Sign In</a>
          </li>
          <li class="nav-item">
            <a class="btn btn-accent ms-2" href="<?= SITE_URL ?>/auth/register.php">Open Account</a>
          </li>
        <?php endif; ?>
      </ul>
    </div>
  </div>
</nav>

<!-- spacer below fixed nav -->
<div class="nav-spacer"></div>

    <?php
}
