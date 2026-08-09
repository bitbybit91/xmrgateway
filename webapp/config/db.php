<?php
/**
 * webapp/config/db.php
 *
 * Database connection settings.
 * Copy this file to db.local.php and fill in your real credentials.
 * db.local.php is listed in .gitignore.
 */

// Allow a local override without editing this file.
$local = __DIR__ . '/db.local.php';
if (file_exists($local)) {
    require $local;
    return;
}

// ── Default / example settings ─────────────────────────────────────────────
define('DB_HOST', getenv('DB_HOST') ?: '127.0.0.1');
define('DB_PORT', getenv('DB_PORT') ?: '3306');
define('DB_NAME', getenv('DB_NAME') ?: 'xmrgateway');
define('DB_USER', getenv('DB_USER') ?: 'xmr_app');
define('DB_PASS', getenv('DB_PASS') ?: 'REPLACE_WITH_STRONG_PASSWORD');
define('DB_CHARSET', 'utf8mb4');

/**
 * Returns a PDO connection. Throws PDOException on failure.
 */
function db(): PDO
{
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }

    $dsn = sprintf(
        'mysql:host=%s;port=%s;dbname=%s;charset=%s',
        DB_HOST, DB_PORT, DB_NAME, DB_CHARSET
    );

    $pdo = new PDO($dsn, DB_USER, DB_PASS, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,
    ]);

    return $pdo;
}
