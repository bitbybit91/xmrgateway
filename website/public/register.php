<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';
require_once dirname(__DIR__) . '/includes/csrf.php';

auth_start_session();

// Redirect already logged-in users
if (auth_check() !== null) {
    header('Location: /dashboard.php');
    exit;
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();

    $email            = trim($_POST['email'] ?? '');
    $password         = $_POST['password'] ?? '';
    $confirm_password = $_POST['confirm_password'] ?? '';
    $full_name        = trim($_POST['full_name'] ?? '');

    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'Please enter a valid email address.';
    } elseif (strlen($full_name) < 2) {
        $error = 'Please enter your full name (at least 2 characters).';
    } elseif (strlen($full_name) > 255) {
        $error = 'Full name is too long.';
    } elseif (strlen($password) < 12) {
        $error = 'Password must be at least 12 characters.';
    } elseif ($password !== $confirm_password) {
        $error = 'Passwords do not match.';
    } else {
        try {
            $pdo  = DB::get();
            $stmt = $pdo->prepare('SELECT id FROM users WHERE email = :email LIMIT 1');
            $stmt->execute([':email' => $email]);
            if ($stmt->fetch()) {
                $error = 'An account with that email address already exists.';
            } else {
                auth_register($pdo, $email, $password, $full_name);
                header('Location: /login.php?registered=1');
                exit;
            }
        } catch (PDOException $e) {
            $error = 'Registration failed due to a server error. Please try again.';
        }
    }
}

$page_title = 'Create Account';
require_once dirname(__DIR__) . '/includes/header.php';
?>

<section class="section-dark auth-section">
    <div class="container container-xs">
        <div class="auth-card card">
            <h1 class="auth-title">Create Account</h1>
            <p class="auth-subtitle">Join CryptoInvest to access our institutional-grade blockchain fund strategies.</p>

            <?php if ($error): ?>
                <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
            <?php endif; ?>

            <form method="POST" action="/register.php" class="auth-form">
                <?= csrf_field() ?>
                <div class="form-group">
                    <label for="full_name">Full Name</label>
                    <input type="text" id="full_name" name="full_name" autocomplete="name"
                           value="<?= htmlspecialchars($_POST['full_name'] ?? '', ENT_QUOTES, 'UTF-8') ?>"
                           required placeholder="Jane Smith" maxlength="255">
                </div>
                <div class="form-group">
                    <label for="email">Email Address</label>
                    <input type="email" id="email" name="email" autocomplete="email"
                           value="<?= htmlspecialchars($_POST['email'] ?? '', ENT_QUOTES, 'UTF-8') ?>"
                           required placeholder="you@example.com">
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" autocomplete="new-password" required placeholder="Minimum 12 characters">
                    <small>Must be at least 12 characters.</small>
                </div>
                <div class="form-group">
                    <label for="confirm_password">Confirm Password</label>
                    <input type="password" id="confirm_password" name="confirm_password" autocomplete="new-password" required placeholder="Repeat your password">
                </div>
                <div class="alert alert-warning">
                    <strong>Note:</strong> This platform is for demonstration purposes. Do not invest funds you cannot afford to lose. See footer disclaimer.
                </div>
                <button type="submit" class="btn-primary btn-block">Create Account</button>
            </form>

            <p class="auth-link">Already have an account? <a href="/login.php">Sign in</a></p>
        </div>
    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
