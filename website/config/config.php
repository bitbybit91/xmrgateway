<?php
/**
 * Application configuration.
 * Loads .env and defines all constants used throughout the app.
 */

defined('APP_CONFIGURED') && exit; // Guard against double-loading
define('APP_CONFIGURED', true);

define('BASE_PATH', defined('BASE_PATH') ? BASE_PATH : dirname(__DIR__));
define('PUBLIC_PATH', defined('PUBLIC_PATH') ? PUBLIC_PATH : BASE_PATH . '/public');

// Load .env
$dotenv = Dotenv\Dotenv::createImmutable(BASE_PATH);
$dotenv->safeLoad();

// ── Application ──────────────────────────────────────────────────────────────
define('APP_NAME',   $_ENV['APP_NAME']   ?? 'Pantera Capital Crypto');
define('APP_URL',    rtrim($_ENV['APP_URL']   ?? 'http://localhost', '/'));
define('APP_ENV',    $_ENV['APP_ENV']    ?? 'production');
define('APP_SECRET', $_ENV['APP_SECRET'] ?? 'changeme');

// ── Database ─────────────────────────────────────────────────────────────────
define('DB_HOST', $_ENV['DB_HOST'] ?? '127.0.0.1');
define('DB_PORT', $_ENV['DB_PORT'] ?? '3306');
define('DB_NAME', $_ENV['DB_NAME'] ?? 'cryptoinvest_db');
define('DB_USER', $_ENV['DB_USER'] ?? 'cryptoinvest_user');
define('DB_PASS', $_ENV['DB_PASS'] ?? '');

// ── AcceptXMR ─────────────────────────────────────────────────────────────────
define('ACCEPTXMR_INTERNAL_URL',   rtrim($_ENV['ACCEPTXMR_INTERNAL_URL']   ?? 'http://127.0.0.1:8081', '/'));
define('ACCEPTXMR_EXTERNAL_URL',   rtrim($_ENV['ACCEPTXMR_EXTERNAL_URL']   ?? 'http://127.0.0.1:8080', '/'));
define('ACCEPTXMR_INTERNAL_TOKEN', $_ENV['ACCEPTXMR_INTERNAL_TOKEN'] ?? '');
define('ACCEPTXMR_EXTERNAL_TOKEN', $_ENV['ACCEPTXMR_EXTERNAL_TOKEN'] ?? '');

// ── Mail ──────────────────────────────────────────────────────────────────────
define('MAIL_HOST',         $_ENV['MAIL_HOST']         ?? 'localhost');
define('MAIL_PORT',         (int)($_ENV['MAIL_PORT']   ?? 587));
define('MAIL_ENCRYPTION',   $_ENV['MAIL_ENCRYPTION']   ?? 'tls');
define('MAIL_USERNAME',     $_ENV['MAIL_USERNAME']     ?? '');
define('MAIL_PASSWORD',     $_ENV['MAIL_PASSWORD']     ?? '');
define('MAIL_FROM_ADDRESS', $_ENV['MAIL_FROM_ADDRESS'] ?? 'noreply@example.com');
define('MAIL_FROM_NAME',    $_ENV['MAIL_FROM_NAME']    ?? APP_NAME);

// ── External Services ─────────────────────────────────────────────────────────
define('COINGECKO_API_URL', $_ENV['COINGECKO_API_URL'] ?? 'https://api.coingecko.com/api/v3');

// ── Storage paths ─────────────────────────────────────────────────────────────
define('STORAGE_PATH', BASE_PATH . '/storage');
define('CACHE_PATH',   STORAGE_PATH . '/cache');
define('LOG_PATH',     STORAGE_PATH . '/logs');

// ── Error reporting ───────────────────────────────────────────────────────────
if (APP_ENV === 'production') {
    error_reporting(0);
    ini_set('display_errors', '0');
    ini_set('log_errors', '1');
    ini_set('error_log', LOG_PATH . '/php_errors.log');
} else {
    error_reporting(E_ALL);
    ini_set('display_errors', '1');
}

// ── Session configuration ─────────────────────────────────────────────────────
$sessionPath = STORAGE_PATH . '/sessions';
if (!is_dir($sessionPath)) {
    mkdir($sessionPath, 0700, true);
}
ini_set('session.save_path',        $sessionPath);
ini_set('session.gc_maxlifetime',   '86400');
ini_set('session.cookie_lifetime',  '0');
ini_set('session.cookie_secure',    APP_ENV === 'production' ? '1' : '0');
ini_set('session.cookie_httponly',  '1');
ini_set('session.cookie_samesite',  'Strict');
ini_set('session.use_strict_mode',  '1');

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Get an environment / .env value with optional default.
 */
function env(string $key, mixed $default = null): mixed
{
    return $_ENV[$key] ?? $default;
}

/**
 * Dump & die (development helper).
 * @return never
 */
function dd(mixed ...$vars): never
{
    foreach ($vars as $v) {
        echo '<pre>' . htmlspecialchars(print_r($v, true)) . '</pre>';
    }
    exit(1);
}

/**
 * Abort with an HTTP status code.
 * @return never
 */
function abort(int $code = 404, string $message = ''): never
{
    http_response_code($code);
    if ($message) {
        echo htmlspecialchars($message);
    }
    exit(1);
}
