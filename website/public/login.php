<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';
require_once dirname(__DIR__) . '/includes/csrf.php';

auth_start_session();

$error   = '';
$success = $_GET['registered'] ?? false;

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();

    $email    = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';

    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'Please enter a valid email address.';
    } elseif (strlen($password) < 1) {
        $error = 'Password is required.';
    } else {
        try {
            $pdo  = DB::get();
            $user = auth_login($pdo, $email, $password);

            if ($user === false) {
                // Check if locked
                $stmt = $pdo->prepare(
                    'SELECT login_attempts, locked_until FROM users WHERE email = :email LIMIT 1'
                );
                $stmt->execute([':email' => $email]);
                $row = $stmt->fetch();
                if ($row && $row['locked_until'] !== null && strtotime($row['locked_until']) > time()) {
                    $remaining = ceil((strtotime($row['locked_until']) - time()) / 60);
                    $error = 'Account temporarily locked due to too many failed attempts. Try again in ' . $remaining . ' minute(s).';
                } else {
                    $error = 'Invalid email or password.';
                }
            } else {
                // Create session record
                $token      = bin2hex(random_bytes(64)); // 128 hex chars
                $expires_at = date('Y-m-d H:i:s', time() + 3600);
                $ip         = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
                $ua         = substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 512);

                $pdo->prepare(
                    'INSERT INTO sessions (user_id, token, ip, user_agent, expires_at)
                     VALUES (:uid, :token, :ip, :ua, :exp)'
                )->execute([
                    ':uid'   => $user['id'],
                    ':token' => $token,
                    ':ip'    => $ip,
                    ':ua'    => $ua,
                    ':exp'   => $expires_at,
                ]);

                session_regenerate_id(true);
                $_SESSION['auth_token'] = $token;
                $_SESSION['user_id']    = $user['id'];

                header('Location: /dashboard.php');
                exit;
            }
        } catch (PDOException $e) {
            $error = 'Login failed due to a server error. Please try again.';
        }
    }
}

$page_title = 'Login';
require_once dirname(__DIR__) . '/includes/header.php';
?>

<section class="section-dark auth-section">
    <div class="container container-xs">
        <div class="auth-card card">
            <h1 class="auth-title">Sign In</h1>
            <p class="auth-subtitle">Welcome back. Sign in to access your investment dashboard.</p>

            <?php if ($success): ?>
                <div class="alert alert-success">Registration successful! Please sign in.</div>
            <?php endif; ?>

            <?php if ($error): ?>
                <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
            <?php endif; ?>

            <form method="POST" action="/login.php" class="auth-form">
                <?= csrf_field() ?>
                <div class="form-group">
                    <label for="email">Email Address</label>
                    <input type="email" id="email" name="email" autocomplete="email"
                           value="<?= htmlspecialchars($_POST['email'] ?? '', ENT_QUOTES, 'UTF-8') ?>"
                           required placeholder="you@example.com">
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" autocomplete="current-password" required placeholder="••••••••••••">
                </div>
                <button type="submit" class="btn-primary btn-block">Sign In</button>
            </form>

            <p class="auth-link">Don't have an account? <a href="/register.php">Create one</a></p>
            <p class="auth-note">After <?= LOGIN_MAX_ATTEMPTS ?> failed attempts, your account will be locked for <?= LOGIN_LOCKOUT_MINUTES ?> minutes.</p>
        </div>
    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
