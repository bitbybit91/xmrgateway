<?php
/**
 * webapp/auth/login.php
 */
require_once dirname(__DIR__) . '/config/app.php';
require_once dirname(__DIR__) . '/config/db.php';
require_once dirname(__DIR__) . '/includes/header.php';

if (!empty($_SESSION['user_id'])) {
    header('Location: ' . SITE_URL . '/dashboard/index.php');
    exit;
}

$error = '';
$email = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $token = $_POST['csrf_token'] ?? '';
    if (empty($_SESSION['csrf_token']) || !hash_equals($_SESSION['csrf_token'], $token)) {
        $error = 'Invalid form submission. Please try again.';
    } else {
        $email    = trim($_POST['email']    ?? '');
        $password = $_POST['password'] ?? '';

        try {
            $stmt = db()->prepare('SELECT id, password_hash, full_name, is_active FROM users WHERE email = ?');
            $stmt->execute([$email]);
            $user = $stmt->fetch();

            if ($user && $user['is_active'] && password_verify($password, $user['password_hash'])) {
                session_regenerate_id(true);
                $_SESSION['user_id']   = (int) $user['id'];
                $_SESSION['full_name'] = $user['full_name'];

                $next = filter_var($_GET['next'] ?? '', FILTER_SANITIZE_URL);
                $next = (str_starts_with($next, '/')) ? $next : '/dashboard/index.php';
                header('Location: ' . SITE_URL . $next);
                exit;
            } else {
                // Use a generic message to avoid user enumeration
                $error = 'Invalid email or password.';
            }
        } catch (Exception $e) {
            $error = 'Login failed due to a server error. Please try again.';
        }
    }
}

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

include_header('Sign In');
?>

<div class="auth-wrapper">
  <div class="auth-card">
    <div class="text-center mb-4">
      <h1 class="h4 fw-bold"><span class="brand-accent">XMR</span> Gateway Capital</h1>
      <p class="text-muted small mt-1">Sign in to your account</p>
    </div>

    <?php if ($error): ?>
      <div class="alert-xmr-danger mb-4">
        <i class="bi bi-x-circle me-1"></i> <?= htmlspecialchars($error) ?>
      </div>
    <?php endif; ?>

    <form method="post" action="">
      <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">

      <div class="mb-3">
        <label for="email" class="form-label">Email Address</label>
        <input type="email" class="form-control" id="email" name="email"
               value="<?= htmlspecialchars($email) ?>"
               placeholder="you@example.com" required autocomplete="email">
      </div>

      <div class="mb-4">
        <label for="password" class="form-label">Password</label>
        <input type="password" class="form-control" id="password" name="password"
               placeholder="Your password" required autocomplete="current-password">
      </div>

      <button type="submit" class="btn btn-accent w-100 py-2">
        Sign In <i class="bi bi-arrow-right"></i>
      </button>
    </form>

    <p class="text-center text-muted small mt-4 mb-0">
      No account yet?
      <a href="<?= SITE_URL ?>/auth/register.php" class="text-accent">Open one free</a>
    </p>
  </div>
</div>

<?php include_footer(); ?>
