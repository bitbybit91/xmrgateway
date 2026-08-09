<?php
/**
 * webapp/auth/register.php
 *
 * New user registration. Creates user + account rows in the DB.
 */
require_once dirname(__DIR__) . '/config/app.php';
require_once dirname(__DIR__) . '/config/db.php';
require_once dirname(__DIR__) . '/includes/header.php';

// Already logged in → dashboard
if (!empty($_SESSION['user_id'])) {
    header('Location: ' . SITE_URL . '/dashboard/index.php');
    exit;
}

$errors = [];
$values = ['email' => '', 'full_name' => ''];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // Basic CSRF
    $token = $_POST['csrf_token'] ?? '';
    if (empty($_SESSION['csrf_token']) || !hash_equals($_SESSION['csrf_token'], $token)) {
        $errors[] = 'Invalid form submission. Please try again.';
    }

    $values['email']     = trim($_POST['email']     ?? '');
    $values['full_name'] = trim($_POST['full_name'] ?? '');
    $password            = $_POST['password']        ?? '';
    $password2           = $_POST['password2']       ?? '';

    if (!filter_var($values['email'], FILTER_VALIDATE_EMAIL)) {
        $errors[] = 'Please enter a valid email address.';
    }
    if (strlen($values['full_name']) < 2) {
        $errors[] = 'Please enter your full name (at least 2 characters).';
    }
    if (strlen($password) < 8) {
        $errors[] = 'Password must be at least 8 characters.';
    }
    if ($password !== $password2) {
        $errors[] = 'Passwords do not match.';
    }

    if (empty($errors)) {
        try {
            $pdo = db();
            // Check email uniqueness
            $chk = $pdo->prepare('SELECT id FROM users WHERE email = ?');
            $chk->execute([$values['email']]);
            if ($chk->fetch()) {
                $errors[] = 'An account with this email already exists. <a href="' . SITE_URL . '/auth/login.php">Sign in?</a>';
            } else {
                $hash = password_hash($password, PASSWORD_BCRYPT, ['cost' => 12]);
                $pdo->beginTransaction();
                $ins = $pdo->prepare(
                    'INSERT INTO users (email, password_hash, full_name) VALUES (?, ?, ?)'
                );
                $ins->execute([$values['email'], $hash, $values['full_name']]);
                $userId = (int) $pdo->lastInsertId();

                // Create account row
                $pdo->prepare('INSERT INTO accounts (user_id) VALUES (?)')->execute([$userId]);
                $pdo->commit();

                // Log the user in
                session_regenerate_id(true);
                $_SESSION['user_id']   = $userId;
                $_SESSION['full_name'] = $values['full_name'];
                header('Location: ' . SITE_URL . '/dashboard/index.php');
                exit;
            }
        } catch (Exception $e) {
            if (isset($pdo) && $pdo->inTransaction()) {
                $pdo->rollBack();
            }
            $errors[] = 'Registration failed due to a server error. Please try again later.';
        }
    }
}

// Generate CSRF token for the form
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

include_header('Create Account');
?>

<div class="auth-wrapper">
  <div class="auth-card">
    <!-- Logo / brand -->
    <div class="text-center mb-4">
      <h1 class="h4 fw-bold"><span class="brand-accent">XMR</span> Gateway Capital</h1>
      <p class="text-muted small mt-1">Open a free account — no ID required</p>
    </div>

    <?php if (!empty($errors)): ?>
      <div class="alert-xmr-danger mb-4">
        <?php foreach ($errors as $e): ?>
          <div><i class="bi bi-x-circle me-1"></i> <?= $e ?></div>
        <?php endforeach; ?>
      </div>
    <?php endif; ?>

    <form method="post" action="">
      <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">

      <div class="mb-3">
        <label for="full_name" class="form-label">Full Name</label>
        <input type="text" class="form-control" id="full_name" name="full_name"
               value="<?= htmlspecialchars($values['full_name']) ?>"
               placeholder="Jane Doe" required autocomplete="name">
      </div>

      <div class="mb-3">
        <label for="email" class="form-label">Email Address</label>
        <input type="email" class="form-control" id="email" name="email"
               value="<?= htmlspecialchars($values['email']) ?>"
               placeholder="you@example.com" required autocomplete="email">
      </div>

      <div class="mb-3">
        <label for="password" class="form-label">Password</label>
        <input type="password" class="form-control" id="password" name="password"
               placeholder="Min. 8 characters" required autocomplete="new-password">
      </div>

      <div class="mb-4">
        <label for="password2" class="form-label">Confirm Password</label>
        <input type="password" class="form-control" id="password2" name="password2"
               placeholder="Repeat password" required autocomplete="new-password">
      </div>

      <button type="submit" class="btn btn-accent w-100 py-2">
        Create Account <i class="bi bi-arrow-right"></i>
      </button>
    </form>

    <p class="text-center text-muted small mt-4 mb-0">
      Already have an account?
      <a href="<?= SITE_URL ?>/auth/login.php" class="text-accent">Sign in</a>
    </p>
  </div>
</div>

<?php include_footer(); ?>
