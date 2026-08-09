<?php
/**
 * webapp/includes/auth_guard.php
 *
 * Include at the top of any page that requires a logged-in user.
 * Redirects to /auth/login.php if the session is not set.
 */
require_once dirname(__DIR__) . '/config/app.php';
require_once dirname(__DIR__) . '/config/db.php';

if (empty($_SESSION['user_id'])) {
    header('Location: ' . SITE_URL . '/auth/login.php?next=' . urlencode($_SERVER['REQUEST_URI']));
    exit;
}

$currentUserId = (int) $_SESSION['user_id'];

/**
 * Generate a CSRF token and store it in the session.
 * Embed the returned string in hidden form fields.
 */
function csrf_token(): string
{
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

/**
 * Verify that the submitted CSRF token matches the session token.
 * Call at the top of every POST handler.
 */
function csrf_verify(): void
{
    $submitted = $_POST['csrf_token'] ?? '';
    $stored    = $_SESSION['csrf_token'] ?? '';
    if (!$stored || !hash_equals($stored, $submitted)) {
        http_response_code(403);
        exit('Invalid CSRF token. Please go back and try again.');
    }
}

/**
 * Fetch the current user's account row (balance etc.).
 */
function current_account(): array
{
    global $currentUserId;
    $stmt = db()->prepare('SELECT * FROM accounts WHERE user_id = ?');
    $stmt->execute([$currentUserId]);
    return $stmt->fetch() ?: [];
}
