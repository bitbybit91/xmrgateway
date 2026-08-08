<?php
/**
 * webapp/config/app.php
 *
 * Global application settings. Adjust these to match your installation.
 */

// ── Site identity ────────────────────────────────────────────────────────────
define('SITE_NAME',  'XMR Gateway Capital');
define('SITE_URL',   getenv('SITE_URL') ?: 'http://localhost');
define('SITE_EMAIL', getenv('SITE_EMAIL') ?: 'info@example.com');

// ── Crypto receiving addresses ────────────────────────────────────────────────
// These are read from your crypto.config.json at runtime so you only have
// one place to configure them. If that file is absent we fall back to these
// environment variables.
$cryptoConfigFile = dirname(__DIR__, 1) . '/../config/crypto.config.json';
if (file_exists($cryptoConfigFile)) {
    $cryptoCfg = json_decode(file_get_contents($cryptoConfigFile), true);
    define('XMR_ADDRESS', $cryptoCfg['xmr']['primaryAddress']  ?? '');
    define('BTC_ADDRESS', $cryptoCfg['btc']['receivingAddress'] ?? '');
} else {
    define('XMR_ADDRESS', getenv('XMR_ADDRESS') ?: '');
    define('BTC_ADDRESS', getenv('BTC_ADDRESS') ?: '');
}

// ── CoinGecko ────────────────────────────────────────────────────────────────
// Free public API — no key required for basic price endpoints.
define('COINGECKO_API', 'https://api.coingecko.com/api/v3');

// ── Investment limits (USD) ───────────────────────────────────────────────────
define('MIN_INVESTMENT', 250.00);
define('MAX_INVESTMENT', 1_000_000.00);

// ── Session ───────────────────────────────────────────────────────────────────
define('SESSION_LIFETIME', 3600); // seconds

// ── Security ──────────────────────────────────────────────────────────────────
// Set a strong random string for CSRF tokens (at least 32 chars).
define('APP_SECRET', getenv('APP_SECRET') ?: 'REPLACE_WITH_STRONG_RANDOM_SECRET');

// Boot session
if (session_status() === PHP_SESSION_NONE) {
    session_set_cookie_params([
        'lifetime' => SESSION_LIFETIME,
        'path'     => '/',
        'secure'   => isset($_SERVER['HTTPS']),
        'httponly' => true,
        'samesite' => 'Strict',
    ]);
    session_start();
}
