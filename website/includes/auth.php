<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

function auth_start_session(): void {
    if (session_status() === PHP_SESSION_NONE) {
        $is_https = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off')
            || (isset($_SERVER['SERVER_PORT']) && (int)$_SERVER['SERVER_PORT'] === 443);
        session_set_cookie_params([
            'lifetime' => 3600,
            'path'     => '/',
            'secure'   => $is_https,
            'httponly' => true,
            'samesite' => 'Strict',
        ]);
        session_start();
        // Regenerate ID on first start to prevent fixation
        if (empty($_SESSION['_initiated'])) {
            session_regenerate_id(true);
            $_SESSION['_initiated'] = true;
        }
    }
}

function auth_check(): ?array {
    auth_start_session();
    if (empty($_SESSION['auth_token']) || empty($_SESSION['user_id'])) {
        return null;
    }
    try {
        $pdo = DB::get();
        $stmt = $pdo->prepare(
            'SELECT s.user_id, s.expires_at, u.email, u.full_name, u.kyc_status
             FROM sessions s
             JOIN users u ON u.id = s.user_id
             WHERE s.token = :token
               AND s.user_id = :user_id
               AND s.expires_at > NOW()'
        );
        $stmt->execute([
            ':token'   => $_SESSION['auth_token'],
            ':user_id' => $_SESSION['user_id'],
        ]);
        $row = $stmt->fetch();
        return $row ?: null;
    } catch (PDOException $e) {
        return null;
    }
}

function auth_require(): array {
    $user = auth_check();
    if ($user === null) {
        header('Location: /login.php');
        exit;
    }
    return $user;
}

function auth_require_admin(): array {
    auth_start_session();
    if (empty($_SESSION['admin_id']) || empty($_SESSION['admin_token'])) {
        header('Location: /admin/login.php');
        exit;
    }
    try {
        $pdo = DB::get();
        $stmt = $pdo->prepare(
            'SELECT id, username, role FROM admin_users WHERE id = :id'
        );
        $stmt->execute([':id' => $_SESSION['admin_id']]);
        $admin = $stmt->fetch();
        if (!$admin) {
            session_destroy();
            header('Location: /admin/login.php');
            exit;
        }
        return $admin;
    } catch (PDOException $e) {
        header('Location: /admin/login.php');
        exit;
    }
}

function auth_login(PDO $pdo, string $email, string $password): array|false {
    $stmt = $pdo->prepare(
        'SELECT id, email, password_hash, full_name, kyc_status, login_attempts, locked_until
         FROM users WHERE email = :email LIMIT 1'
    );
    $stmt->execute([':email' => $email]);
    $user = $stmt->fetch();

    if (!$user) {
        // Timing-safe: still run verify to prevent user enumeration timing attacks
        password_verify($password, '$argon2id$v=19$m=65536,t=4,p=1$c29tZXNhbHRzb21lc2FsdA$YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE');
        return false;
    }

    // Check lockout
    if ($user['locked_until'] !== null && strtotime($user['locked_until']) > time()) {
        return false;
    }

    if (!password_verify($password, $user['password_hash'])) {
        $attempts = (int)$user['login_attempts'] + 1;
        if ($attempts >= LOGIN_MAX_ATTEMPTS) {
            $locked = date('Y-m-d H:i:s', time() + LOGIN_LOCKOUT_MINUTES * 60);
            $pdo->prepare('UPDATE users SET login_attempts = :a, locked_until = :l WHERE id = :id')
                ->execute([':a' => $attempts, ':l' => $locked, ':id' => $user['id']]);
        } else {
            $pdo->prepare('UPDATE users SET login_attempts = :a WHERE id = :id')
                ->execute([':a' => $attempts, ':id' => $user['id']]);
        }
        return false;
    }

    // Successful login: reset attempts
    $pdo->prepare('UPDATE users SET login_attempts = 0, locked_until = NULL, last_login = NOW() WHERE id = :id')
        ->execute([':id' => $user['id']]);

    return $user;
}

function auth_logout(PDO $pdo): void {
    auth_start_session();
    if (!empty($_SESSION['auth_token'])) {
        try {
            $pdo->prepare('DELETE FROM sessions WHERE token = :token')
                ->execute([':token' => $_SESSION['auth_token']]);
        } catch (PDOException $e) {
            // ignore
        }
    }
    $_SESSION = [];
    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params();
        setcookie(session_name(), '', time() - 42000,
            $params['path'], $params['domain'],
            $params['secure'], $params['httponly']
        );
    }
    session_destroy();
}

function auth_register(PDO $pdo, string $email, string $password, string $full_name): int {
    $hash = password_hash($password, PASSWORD_ARGON2ID, ['memory_cost' => 65536, 'time_cost' => 4, 'threads' => 1]);
    $stmt = $pdo->prepare(
        'INSERT INTO users (email, password_hash, full_name) VALUES (:email, :hash, :name)'
    );
    $stmt->execute([':email' => $email, ':hash' => $hash, ':name' => $full_name]);
    return (int)$pdo->lastInsertId();
}
