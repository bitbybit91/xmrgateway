<?php
// Database credentials - installer will replace these placeholders
define('DB_HOST', getenv('DB_HOST') ?: '127.0.0.1');
define('DB_NAME', getenv('DB_NAME') ?: 'cryptoinvest');
define('DB_USER', getenv('DB_USER') ?: 'cryptoinvest');
define('DB_PASS', getenv('DB_PASS') ?: '__DB_PASS__');

// AcceptXMR endpoints
define('ACCEPTXMR_INTERNAL_URL', getenv('ACCEPTXMR_INTERNAL_URL') ?: 'http://127.0.0.1:8081');
define('ACCEPTXMR_EXTERNAL_URL', getenv('ACCEPTXMR_EXTERNAL_URL') ?: 'http://127.0.0.1:8080');
define('ACCEPTXMR_TOKEN', getenv('INTERNAL_API_TOKEN') ?: '');

// Site config
define('SITE_NAME', 'CryptoInvest');
define('SITE_URL', getenv('SITE_URL') ?: 'https://invest.example.com');
define('APP_ROOT', dirname(__DIR__));
define('XMR_CONFIRMATIONS_REQUIRED', 10);
define('INVOICE_EXPIRY_MINUTES', 60);
define('LOGIN_MAX_ATTEMPTS', 5);
define('LOGIN_LOCKOUT_MINUTES', 15);

// Session cookie settings
// Note: session.cookie_secure=1 requires HTTPS. Set to 0 during initial HTTP-only setup,
// then re-enable after running: certbot --apache -d yourdomain.com
ini_set('session.cookie_httponly', 1);
ini_set('session.cookie_secure', getenv('HTTPS_ENABLED') ? 1 : ((!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 1 : 0));
ini_set('session.cookie_samesite', 'Strict');
ini_set('session.use_strict_mode', 1);
ini_set('session.gc_maxlifetime', 3600);
