#!/usr/bin/env python3
"""
win_site_cloner.py — Windows-friendly offline site cloner with PHP/MySQL backend generation
and Tor hidden-service scraping support.

Modes:
  static  (default) — JS-free static mirror of any website.
  dynamic           — PHP + MySQL backend on top of the cloned site, including a Monero
                      wallet system (deposit/withdrawal) wired to monero-wallet-rpc.
  onion             — Route all requests through a Tor SOCKS5 proxy; accept .onion URLs;
                      optionally preserve JavaScript with --keep-js.

Usage examples:
  python win_site_cloner.py --url https://example.com --output ./mirror
  python win_site_cloner.py --url https://example.com --output ./shop --mode dynamic
  python win_site_cloner.py --url http://someonion.onion --output ./onion --mode onion --keep-js
  python win_site_cloner.py --url https://example.com --output ./mirror --zip
"""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.parse
import zipfile
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Dependency bootstrap
# ---------------------------------------------------------------------------
PIP_PACKAGES_CORE = ["requests", "beautifulsoup4", "lxml"]
PIP_PACKAGES_SOCKS = ["requests[socks]"]  # added for onion mode

log = logging.getLogger("win_site_cloner")


def _ensure_packages(packages: list[str]) -> None:
    for pkg in packages:
        # Strip extras like [socks] for the import name check
        import_name = re.split(r"[\[><=!]", pkg)[0].replace("-", "_")
        try:
            importlib.import_module(import_name)
        except ImportError:
            log.info("Auto-installing %s …", pkg)
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet", pkg],
                stdout=subprocess.DEVNULL,
            )


# ---------------------------------------------------------------------------
# PHP / SQL template strings
# ---------------------------------------------------------------------------

CONFIG_PHP = r"""<?php
// config.php — DB + XMR RPC credentials loaded from environment (no hardcoded secrets)
define('DB_HOST',     getenv('DB_HOST')     ?: 'localhost');
define('DB_NAME',     getenv('DB_NAME')     ?: 'xmrshop');
define('DB_USER',     getenv('DB_USER')     ?: 'root');
define('DB_PASS',     getenv('DB_PASS')     ?: '');
define('DB_CHARSET',  'utf8mb4');

define('XMR_RPC_URL',  getenv('XMR_RPC_URL')  ?: 'http://127.0.0.1:18082/json_rpc');
define('XMR_RPC_USER', getenv('XMR_RPC_USER') ?: '');
define('XMR_RPC_PASS', getenv('XMR_RPC_PASS') ?: '');

define('XMR_ACCOUNT_INDEX',    0);
define('XMR_MIN_CONFIRMATIONS', 10);
define('PICONERO',              1e12); // 1 XMR = 1e12 piconero

define('SITE_NAME',  'XMR Shop');
define('BASE_URL',   (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on' ? 'https' : 'http')
                     . '://' . ($_SERVER['HTTP_HOST'] ?? 'localhost'));

define('SESSION_NAME',    'xmrshop_sess');
define('SESSION_TIMEOUT', 3600);

// Cookie security flags
define('COOKIE_SECURE', isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on');
"""

DB_PHP = r"""<?php
// db.php — PDO connection helper (prepared statements only, never string-concatenated SQL)
require_once __DIR__ . '/config.php';

function db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $dsn = 'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=' . DB_CHARSET;
        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ];
        try {
            $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        } catch (PDOException $e) {
            http_response_code(500);
            error_log('DB connection failed: ' . $e->getMessage());
            die('Database connection error. Please check configuration.');
        }
    }
    return $pdo;
}
"""

SCHEMA_SQL = r"""-- schema.sql — XMR Shop database schema
CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(64) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    xmr_address   VARCHAR(128) DEFAULT NULL,
    balance       DECIMAL(20,12) NOT NULL DEFAULT 0.000000000000,
    login_attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
    locked_until  DATETIME DEFAULT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sessions (
    id         VARCHAR(128) PRIMARY KEY,
    user_id    INT UNSIGNED NOT NULL,
    ip         VARCHAR(45) DEFAULT NULL,
    user_agent VARCHAR(512) DEFAULT NULL,
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS products (
    id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    price_xmr   DECIMAL(20,12) NOT NULL,
    image_url   VARCHAR(512) DEFAULT NULL,
    stock       INT NOT NULL DEFAULT 0,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id    INT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    qty        INT UNSIGNED NOT NULL DEFAULT 1,
    total_xmr  DECIMAL(20,12) NOT NULL,
    status     ENUM('pending','paid','shipped','cancelled') NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS deposits (
    id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id       INT UNSIGNED NOT NULL,
    tx_hash       VARCHAR(128) NOT NULL UNIQUE,
    amount_xmr    DECIMAL(20,12) NOT NULL,
    confirmations INT UNSIGNED NOT NULL DEFAULT 0,
    status        ENUM('pending','confirmed','credited') NOT NULL DEFAULT 'pending',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS withdrawals (
    id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id    INT UNSIGNED NOT NULL,
    to_address VARCHAR(128) NOT NULL,
    amount_xmr DECIMAL(20,12) NOT NULL,
    tx_hash    VARCHAR(128) DEFAULT NULL,
    status     ENUM('pending','processing','sent','failed') NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
    user_id INT UNSIGNED NOT NULL,
    `key`   VARCHAR(64) NOT NULL,
    value   TEXT,
    PRIMARY KEY (user_id, `key`),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Default demo product
INSERT IGNORE INTO products (id, name, description, price_xmr, stock)
VALUES (1, 'Demo Product', 'A sample product to demonstrate the shop.', 0.010000000000, 100);
"""

INSTALL_PHP = r"""<?php
// install.php — one-shot installer. Creates schema and admin user, then self-disables.
// DELETE this file after running it!
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';

// Prevent re-run if lock file exists
$lock = __DIR__ . '/.installed';
if (file_exists($lock)) {
    die('<p>Already installed. Delete <code>.installed</code> to reinstall.</p>');
}

$errors = [];
$adminUser = getenv('ADMIN_USER') ?: 'admin';
$adminPass = getenv('ADMIN_PASS') ?: 'changeme_NOW';
$adminEmail = getenv('ADMIN_EMAIL') ?: 'admin@example.com';

if (isset($_POST['run'])) {
    try {
        $pdo = db();
        // Run schema
        $sql = file_get_contents(__DIR__ . '/schema.sql');
        // Split on semicolons (simple), execute each statement
        foreach (array_filter(array_map('trim', explode(';', $sql))) as $stmt) {
            if ($stmt !== '') {
                $pdo->exec($stmt);
            }
        }
        // Create admin
        $hash = password_hash($adminPass, PASSWORD_BCRYPT, ['cost' => 12]);
        $stmt = $pdo->prepare(
            'INSERT INTO users (username, password_hash, email, xmr_address) VALUES (?,?,?,?) '
          . 'ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash)'
        );
        $stmt->execute([$adminUser, $hash, $adminEmail, null]);

        // Write lock file
        file_put_contents($lock, date('c'));
        echo '<h2>Installation complete!</h2>';
        echo '<p>Admin username: <strong>' . htmlspecialchars($adminUser, ENT_QUOTES, 'UTF-8') . '</strong></p>';
        echo '<p style="color:red">Delete this file (<code>install.php</code>) now.</p>';
        exit;
    } catch (Throwable $e) {
        $errors[] = 'Installation failed: ' . $e->getMessage();
    }
}
?>
<!DOCTYPE html><html><head><title>Install</title></head><body>
<h2>XMR Shop Installer</h2>
<?php foreach ($errors as $e): ?>
  <p style="color:red"><?= htmlspecialchars($e, ENT_QUOTES, 'UTF-8') ?></p>
<?php endforeach; ?>
<form method="post">
  <p>This will create the database schema and an admin user.</p>
  <p>Set <code>ADMIN_USER</code>, <code>ADMIN_PASS</code>, <code>ADMIN_EMAIL</code> env vars before running.</p>
  <button name="run" value="1">Run Installation</button>
</form>
</body></html>
"""

XMR_GATEWAY_CLIENT_PHP = r"""<?php
// xmrgateway_client.php — monero-wallet-rpc JSON-RPC client with digest auth
// Mirrors the monero-wallet-rpc JSON-RPC surface used by the xmrgateway project.
// RPC reference: https://www.getmonero.org/resources/developer-guides/wallet-rpc.html
require_once __DIR__ . '/config.php';

class XmrGatewayClient {
    private string $url;
    private string $user;
    private string $pass;
    private int $id = 0;

    public function __construct(
        string $url  = XMR_RPC_URL,
        string $user = XMR_RPC_USER,
        string $pass = XMR_RPC_PASS
    ) {
        $this->url  = $url;
        $this->user = $user;
        $this->pass = $pass;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /** Return the primary address for an account */
    public function getAddress(int $accountIndex = 0): array {
        return $this->call('get_address', ['account_index' => $accountIndex]);
    }

    /** Create a new subaddress in the given account and return it */
    public function getNewSubaddress(int $accountIndex = 0): array {
        return $this->call('create_address', [
            'account_index' => $accountIndex,
            'label'         => 'user_deposit_' . time(),
        ]);
    }

    /** Return balance (total and unlocked) for an account in atomic units */
    public function getBalance(int $accountIndex = 0): array {
        return $this->call('get_balance', ['account_index' => $accountIndex]);
    }

    /**
     * Return transfers for an account.
     * $direction: 'in', 'out', 'all', 'pending', 'pool'
     */
    public function getTransfers(int $accountIndex = 0, string $direction = 'all'): array {
        $params = ['account_index' => $accountIndex];
        if ($direction === 'all') {
            $params['in']      = true;
            $params['out']     = true;
            $params['pending'] = true;
            $params['pool']    = true;
        } else {
            $params[$direction] = true;
        }
        return $this->call('get_transfers', $params);
    }

    /**
     * Send XMR to a destination address.
     * $atomicAmount — amount in piconero (1 XMR = 1e12)
     * $priority     — 0=default,1=unimportant,2=normal,3=elevated,4=priority
     */
    public function transfer(string $toAddress, int $atomicAmount, int $priority = 1): array {
        return $this->call('transfer', [
            'destinations' => [['amount' => $atomicAmount, 'address' => $toAddress]],
            'priority'     => $priority,
            'ring_size'    => 16,
            'get_tx_key'   => true,
        ]);
    }

    // -----------------------------------------------------------------------
    // Internal JSON-RPC call with digest auth
    // -----------------------------------------------------------------------

    private function call(string $method, array $params = []): array {
        $body = json_encode([
            'jsonrpc' => '2.0',
            'id'      => (string)($this->id++),
            'method'  => $method,
            'params'  => $params,
        ]);

        $ch = curl_init($this->url);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => $body,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
            CURLOPT_TIMEOUT        => 30,
        ]);

        // Digest authentication (same as monero-wallet-rpc default)
        if ($this->user !== '' || $this->pass !== '') {
            curl_setopt($ch, CURLOPT_HTTPAUTH,  CURLAUTH_DIGEST);
            curl_setopt($ch, CURLOPT_USERPWD,   $this->user . ':' . $this->pass);
        }

        $raw = curl_exec($ch);
        $err = curl_error($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($raw === false) {
            throw new RuntimeException('XMR RPC cURL error: ' . $err);
        }
        if ($httpCode !== 200) {
            throw new RuntimeException('XMR RPC HTTP ' . $httpCode);
        }

        $json = json_decode($raw, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new RuntimeException('XMR RPC invalid JSON: ' . json_last_error_msg());
        }
        if (isset($json['error'])) {
            throw new RuntimeException('XMR RPC error: ' . ($json['error']['message'] ?? 'unknown'));
        }
        return $json['result'] ?? [];
    }
}
"""

CRON_POLL_DEPOSITS_PHP = r"""<?php
// cron_poll_deposits.php — run via cron/task scheduler, e.g. every 2 minutes.
// Scans incoming transfers and credits confirmed deposits to user balances.
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/xmrgateway_client.php';

$xmr = new XmrGatewayClient();
$pdo = db();

try {
    $result = $xmr->getTransfers(XMR_ACCOUNT_INDEX, 'in');
    $transfers = $result['in'] ?? [];
} catch (Throwable $e) {
    error_log('[cron_poll_deposits] getTransfers failed: ' . $e->getMessage());
    exit(1);
}

foreach ($transfers as $tx) {
    $txHash       = $tx['txid']          ?? '';
    $confirmations = (int)($tx['confirmations'] ?? 0);
    $atomicAmount  = (int)($tx['amount']  ?? 0);
    $subaddrIndex  = $tx['subaddr_index']['minor'] ?? null;

    if ($txHash === '' || $subaddrIndex === null) {
        continue;
    }

    $amountXmr = $atomicAmount / PICONERO;

    // Upsert deposit record
    $stmt = $pdo->prepare(
        'INSERT INTO deposits (user_id, tx_hash, amount_xmr, confirmations, status)
         SELECT u.id, :tx_hash, :amount_xmr, :confs, :status
           FROM users u
          WHERE u.xmr_address IS NOT NULL
            AND u.id = :subaddr_index
         ON DUPLICATE KEY UPDATE
           confirmations = :confs2,
           status = IF(confirmations >= :min_confs AND status = \'pending\', \'confirmed\', status)'
    );

    // Map subaddress minor index to user — simplified: store subaddr index in user table
    // Look up user by subaddress minor index (stored as the minor index in xmr_address field)
    $userStmt = $pdo->prepare('SELECT id FROM users WHERE xmr_address = :addr LIMIT 1');
    $userStmt->execute([':addr' => (string)$subaddrIndex]);
    $user = $userStmt->fetch();
    if (!$user) {
        // Try matching by exact subaddress stored in users.xmr_address
        $addrStmt = $pdo->prepare('SELECT id FROM users WHERE xmr_address = :txaddr LIMIT 1');
        $addrStmt->execute([':txaddr' => $tx['address'] ?? '']);
        $user = $addrStmt->fetch();
    }
    if (!$user) {
        continue;
    }
    $userId = (int)$user['id'];

    // Check if already credited
    $existsStmt = $pdo->prepare(
        'SELECT id, status FROM deposits WHERE tx_hash = :hash LIMIT 1'
    );
    $existsStmt->execute([':hash' => $txHash]);
    $existing = $existsStmt->fetch();

    if (!$existing) {
        $status = $confirmations >= XMR_MIN_CONFIRMATIONS ? 'confirmed' : 'pending';
        $ins = $pdo->prepare(
            'INSERT INTO deposits (user_id, tx_hash, amount_xmr, confirmations, status)
             VALUES (:uid, :hash, :amt, :confs, :status)'
        );
        $ins->execute([
            ':uid'    => $userId,
            ':hash'   => $txHash,
            ':amt'    => $amountXmr,
            ':confs'  => $confirmations,
            ':status' => $status,
        ]);
    } else {
        $upd = $pdo->prepare(
            'UPDATE deposits SET confirmations = :confs,
             status = IF(:confs2 >= :min_confs AND status = \'pending\', \'confirmed\', status)
             WHERE tx_hash = :hash'
        );
        $upd->execute([
            ':confs'     => $confirmations,
            ':confs2'    => $confirmations,
            ':min_confs' => XMR_MIN_CONFIRMATIONS,
            ':hash'      => $txHash,
        ]);
        // Re-fetch
        $existsStmt->execute([':hash' => $txHash]);
        $existing = $existsStmt->fetch();
    }

    // Credit user balance for newly confirmed deposits
    if (($existing['status'] ?? '') === 'confirmed') {
        $pdo->beginTransaction();
        try {
            // Only credit if not already credited
            $creditStmt = $pdo->prepare(
                'UPDATE deposits SET status = \'credited\'
                  WHERE tx_hash = :hash AND status = \'confirmed\''
            );
            $creditStmt->execute([':hash' => $txHash]);
            if ($creditStmt->rowCount() === 1) {
                $balStmt = $pdo->prepare(
                    'UPDATE users SET balance = balance + :amt WHERE id = :uid'
                );
                $balStmt->execute([':amt' => $amountXmr, ':uid' => $userId]);
                echo "Credited {$amountXmr} XMR to user {$userId} (tx: {$txHash})\n";
            }
            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            error_log('[cron_poll_deposits] credit error: ' . $e->getMessage());
        }
    }
}
echo "Done.\n";
"""

CSRF_PHP = r"""<?php
// includes/csrf.php — CSRF token helpers
function csrf_token(): string {
    if (empty($_SESSION['csrf_token'])) {
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
    }
    return $_SESSION['csrf_token'];
}

function csrf_field(): string {
    return '<input type="hidden" name="csrf_token" value="'
         . htmlspecialchars(csrf_token(), ENT_QUOTES, 'UTF-8') . '">';
}

function csrf_verify(): void {
    $token = $_POST['csrf_token'] ?? '';
    if (!hash_equals(csrf_token(), $token)) {
        http_response_code(403);
        die('CSRF token mismatch. Please go back and try again.');
    }
}
"""

AUTH_PHP = r"""<?php
// includes/auth.php — session guard, must be included after session_start()
require_once __DIR__ . '/../config.php';

function require_auth(): void {
    if (empty($_SESSION['user_id'])) {
        header('Location: /login.php');
        exit;
    }
    // Session timeout check
    if (isset($_SESSION['last_active']) && (time() - $_SESSION['last_active']) > SESSION_TIMEOUT) {
        session_unset();
        session_destroy();
        header('Location: /login.php?timeout=1');
        exit;
    }
    $_SESSION['last_active'] = time();
}

function current_user(): ?array {
    if (empty($_SESSION['user_id'])) return null;
    static $user = null;
    if ($user === null) {
        require_once __DIR__ . '/../db.php';
        $stmt = db()->prepare('SELECT * FROM users WHERE id = ? LIMIT 1');
        $stmt->execute([$_SESSION['user_id']]);
        $user = $stmt->fetch() ?: null;
    }
    return $user;
}
"""

# Header template — placeholders replaced by Python at generation time
HEADER_PHP_TEMPLATE = r"""<?php
// includes/header.php — shared page header
require_once __DIR__ . '/../config.php';
require_once __DIR__ . '/../db.php';
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/csrf.php';

$cookieParams = [
    'lifetime' => SESSION_TIMEOUT,
    'path'     => '/',
    'secure'   => COOKIE_SECURE,
    'httponly' => true,
    'samesite' => 'Lax',
];
session_name(SESSION_NAME);
session_set_cookie_params($cookieParams);
if (session_status() === PHP_SESSION_NONE) session_start();

$currentUser = current_user();
$siteName    = SITE_NAME;
?>
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= htmlspecialchars($siteName, ENT_QUOTES, 'UTF-8') ?></title>
{CSS_LINK}
<style>
  body { font-family: sans-serif; margin: 0; background: #1a1a2e; color: #eee; }
  .navbar { background: #16213e; padding: .8rem 1.5rem; display:flex; align-items:center; gap:1rem; }
  .navbar a { color: #e94560; text-decoration:none; font-weight:600; }
  .navbar a:hover { text-decoration:underline; }
  .navbar .logo { height:36px; margin-right:.5rem; }
  .navbar .spacer { flex:1; }
  .container { max-width:1100px; margin:2rem auto; padding:0 1rem; }
  .card { background:#16213e; border-radius:8px; padding:1.5rem; margin-bottom:1rem; }
  .btn { display:inline-block; padding:.5rem 1.2rem; border-radius:4px; cursor:pointer;
         border:none; font-size:1rem; text-decoration:none; }
  .btn-primary { background:#e94560; color:#fff; }
  .btn-secondary { background:#0f3460; color:#eee; }
  .btn:hover { opacity:.85; }
  table { width:100%; border-collapse:collapse; }
  th, td { padding:.6rem .9rem; border-bottom:1px solid #0f3460; text-align:left; }
  th { background:#0f3460; }
  input, select, textarea { width:100%; padding:.5rem; border-radius:4px;
    border:1px solid #0f3460; background:#1a1a2e; color:#eee; font-size:1rem; box-sizing:border-box; }
  label { display:block; margin:.6rem 0 .2rem; }
  .alert { padding:.7rem 1rem; border-radius:4px; margin:.5rem 0; }
  .alert-success { background:#1d6a3a; }
  .alert-error   { background:#6a1d1d; }
  .alert-info    { background:#1d3f6a; }
</style>
</head>
<body>
<nav class="navbar">
  {LOGO_IMG}
  <a href="/"><?= htmlspecialchars($siteName, ENT_QUOTES, 'UTF-8') ?></a>
  <div class="spacer"></div>
  <?php if ($currentUser): ?>
    <a href="/wallet.php">Wallet</a>
    <a href="/orders.php">Orders</a>
    <a href="/products.php">Shop</a>
    <a href="/dashboard.php">Dashboard</a>
    <a href="/settings.php">Settings</a>
    <a href="/logout.php">Logout (<?= htmlspecialchars($currentUser['username'], ENT_QUOTES, 'UTF-8') ?>)</a>
  <?php else: ?>
    <a href="/login.php">Login</a>
    <a href="/register.php">Register</a>
  <?php endif; ?>
</nav>
<div class="container">
"""

FOOTER_PHP = r"""<?php
// includes/footer.php
?>
</div><!-- /.container -->
<footer style="text-align:center;padding:1.5rem;background:#16213e;color:#888;margin-top:2rem;">
  &copy; <?= date('Y') ?> XMR Shop — Powered by Monero
</footer>
</body>
</html>
"""

LOGIN_PHP = r"""<?php
// login.php
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/includes/csrf.php';

if ($currentUser) { header('Location: /dashboard.php'); exit; }

$error = '';
$timeout = isset($_GET['timeout']) ? 'Session timed out. Please log in again.' : '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';

    if ($username === '' || $password === '') {
        $error = 'Username and password are required.';
    } else {
        $pdo = db();
        $stmt = $pdo->prepare('SELECT * FROM users WHERE username = ? LIMIT 1');
        $stmt->execute([$username]);
        $user = $stmt->fetch();

        // Rate-limit: max 5 attempts, lock 15 min
        if ($user && $user['locked_until'] && new DateTime() < new DateTime($user['locked_until'])) {
            $error = 'Account locked. Try again later.';
        } elseif ($user && password_verify($password, $user['password_hash'])) {
            // Success — reset attempts, regenerate session
            $pdo->prepare('UPDATE users SET login_attempts=0, locked_until=NULL WHERE id=?')
                ->execute([$user['id']]);
            session_regenerate_id(true);
            $_SESSION['user_id'] = $user['id'];
            $_SESSION['last_active'] = time();
            header('Location: /dashboard.php');
            exit;
        } else {
            if ($user) {
                $attempts = $user['login_attempts'] + 1;
                $lock = $attempts >= 5
                    ? (new DateTime('+15 minutes'))->format('Y-m-d H:i:s')
                    : null;
                $pdo->prepare('UPDATE users SET login_attempts=?, locked_until=? WHERE id=?')
                    ->execute([$attempts, $lock, $user['id']]);
            }
            $error = 'Invalid username or password.';
        }
    }
}
?>
<div class="card" style="max-width:420px;margin:2rem auto">
  <h2>Login</h2>
  <?php if ($timeout): ?>
    <div class="alert alert-info"><?= htmlspecialchars($timeout, ENT_QUOTES, 'UTF-8') ?></div>
  <?php endif; ?>
  <?php if ($error): ?>
    <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
  <?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <label>Username</label>
    <input type="text" name="username" required autocomplete="username">
    <label>Password</label>
    <input type="password" name="password" required autocomplete="current-password">
    <br><br>
    <button class="btn btn-primary" type="submit" style="width:100%">Login</button>
  </form>
  <p><a href="/register.php">Create account</a></p>
</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

REGISTER_PHP = r"""<?php
// register.php
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/includes/csrf.php';
require_once __DIR__ . '/xmrgateway_client.php';

if ($currentUser) { header('Location: /dashboard.php'); exit; }

$error = ''; $success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $username = trim($_POST['username'] ?? '');
    $email    = trim($_POST['email']    ?? '');
    $password = $_POST['password'] ?? '';
    $confirm  = $_POST['confirm']  ?? '';

    if ($username === '' || $email === '' || $password === '') {
        $error = 'All fields are required.';
    } elseif (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'Invalid email address.';
    } elseif (strlen($password) < 8) {
        $error = 'Password must be at least 8 characters.';
    } elseif ($password !== $confirm) {
        $error = 'Passwords do not match.';
    } else {
        $pdo = db();
        $check = $pdo->prepare('SELECT id FROM users WHERE username=? OR email=? LIMIT 1');
        $check->execute([$username, $email]);
        if ($check->fetch()) {
            $error = 'Username or email already in use.';
        } else {
            // Assign a new XMR subaddress
            $xmrAddress = null;
            try {
                $xmr    = new XmrGatewayClient();
                $result = $xmr->getNewSubaddress(XMR_ACCOUNT_INDEX);
                $xmrAddress = $result['address'] ?? null;
            } catch (Throwable $e) {
                error_log('XMR subaddress creation failed: ' . $e->getMessage());
                // Proceed without XMR address; user can generate later from wallet.php
            }
            $hash = password_hash($password, PASSWORD_BCRYPT, ['cost' => 12]);
            $ins  = $pdo->prepare(
                'INSERT INTO users (username, password_hash, email, xmr_address) VALUES (?,?,?,?)'
            );
            $ins->execute([$username, $hash, $email, $xmrAddress]);
            $success = 'Account created! <a href="/login.php">Login now</a>.';
        }
    }
}
?>
<div class="card" style="max-width:420px;margin:2rem auto">
  <h2>Register</h2>
  <?php if ($error): ?>
    <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
  <?php endif; ?>
  <?php if ($success): ?>
    <div class="alert alert-success"><?= $success ?></div>
  <?php endif; ?>
  <form method="post">
    <?= csrf_field() ?>
    <label>Username</label>
    <input type="text" name="username" required>
    <label>Email</label>
    <input type="email" name="email" required>
    <label>Password</label>
    <input type="password" name="password" required minlength="8">
    <label>Confirm Password</label>
    <input type="password" name="confirm" required>
    <br><br>
    <button class="btn btn-primary" type="submit" style="width:100%">Register</button>
  </form>
</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

LOGOUT_PHP = r"""<?php
// logout.php
require_once __DIR__ . '/config.php';

$cookieParams = [
    'lifetime' => SESSION_TIMEOUT,
    'path'     => '/',
    'secure'   => COOKIE_SECURE,
    'httponly' => true,
    'samesite' => 'Lax',
];
session_name(SESSION_NAME);
session_set_cookie_params($cookieParams);
session_start();
session_unset();
session_destroy();
setcookie(SESSION_NAME, '', time() - 3600, '/', '', COOKIE_SECURE, true);
header('Location: /login.php');
exit;
"""

DASHBOARD_PHP = r"""<?php
// dashboard.php
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_auth();

$pdo = db();
$uid = (int)$_SESSION['user_id'];

$balStmt = $pdo->prepare('SELECT balance FROM users WHERE id=? LIMIT 1');
$balStmt->execute([$uid]);
$balance = $balStmt->fetchColumn();

$ordStmt = $pdo->prepare(
    'SELECT o.*, p.name AS product_name FROM orders o
     JOIN products p ON p.id = o.product_id
     WHERE o.user_id = ? ORDER BY o.created_at DESC LIMIT 5'
);
$ordStmt->execute([$uid]);
$recentOrders = $ordStmt->fetchAll();

$depStmt = $pdo->prepare(
    'SELECT * FROM deposits WHERE user_id = ? ORDER BY created_at DESC LIMIT 5'
);
$depStmt->execute([$uid]);
$recentDeposits = $depStmt->fetchAll();

$witStmt = $pdo->prepare(
    'SELECT * FROM withdrawals WHERE user_id = ? ORDER BY created_at DESC LIMIT 5'
);
$witStmt->execute([$uid]);
$recentWithdrawals = $witStmt->fetchAll();
?>
<h2>Dashboard</h2>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem">
  <div class="card">
    <h3>XMR Balance</h3>
    <p style="font-size:1.8rem;color:#e94560"><?= number_format((float)$balance, 12) ?> XMR</p>
    <a href="/wallet.php" class="btn btn-primary">Wallet</a>
  </div>
  <div class="card">
    <h3>Recent Orders</h3>
    <?php if (empty($recentOrders)): ?>
      <p>No orders yet. <a href="/products.php">Browse the shop</a>.</p>
    <?php else: ?>
      <table><tr><th>Product</th><th>Amount</th><th>Status</th></tr>
      <?php foreach ($recentOrders as $o): ?>
        <tr>
          <td><?= htmlspecialchars($o['product_name'], ENT_QUOTES, 'UTF-8') ?></td>
          <td><?= number_format((float)$o['total_xmr'], 8) ?></td>
          <td><?= htmlspecialchars($o['status'], ENT_QUOTES, 'UTF-8') ?></td>
        </tr>
      <?php endforeach; ?>
      </table>
    <?php endif; ?>
  </div>
</div>

<div class="card">
  <h3>Recent Deposits</h3>
  <?php if (empty($recentDeposits)): ?>
    <p>No deposits yet.</p>
  <?php else: ?>
    <table><tr><th>TX Hash</th><th>Amount</th><th>Confs</th><th>Status</th><th>Date</th></tr>
    <?php foreach ($recentDeposits as $d): ?>
      <tr>
        <td style="font-family:monospace;font-size:.8rem"><?= htmlspecialchars(substr($d['tx_hash'],0,16), ENT_QUOTES, 'UTF-8') ?>…</td>
        <td><?= number_format((float)$d['amount_xmr'], 8) ?></td>
        <td><?= (int)$d['confirmations'] ?></td>
        <td><?= htmlspecialchars($d['status'], ENT_QUOTES, 'UTF-8') ?></td>
        <td><?= htmlspecialchars($d['created_at'], ENT_QUOTES, 'UTF-8') ?></td>
      </tr>
    <?php endforeach; ?>
    </table>
  <?php endif; ?>
</div>

<div class="card">
  <h3>Recent Withdrawals</h3>
  <?php if (empty($recentWithdrawals)): ?>
    <p>No withdrawals yet.</p>
  <?php else: ?>
    <table><tr><th>To Address</th><th>Amount</th><th>Status</th><th>Date</th></tr>
    <?php foreach ($recentWithdrawals as $w): ?>
      <tr>
        <td style="font-family:monospace;font-size:.8rem"><?= htmlspecialchars(substr($w['to_address'],0,20), ENT_QUOTES, 'UTF-8') ?>…</td>
        <td><?= number_format((float)$w['amount_xmr'], 8) ?></td>
        <td><?= htmlspecialchars($w['status'], ENT_QUOTES, 'UTF-8') ?></td>
        <td><?= htmlspecialchars($w['created_at'], ENT_QUOTES, 'UTF-8') ?></td>
      </tr>
    <?php endforeach; ?>
    </table>
  <?php endif; ?>
</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

WALLET_PHP = r"""<?php
// wallet.php — deposit and withdrawal interface
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/includes/csrf.php';
require_once __DIR__ . '/xmrgateway_client.php';
require_auth();

$pdo = db();
$uid = (int)$_SESSION['user_id'];
$user = current_user();

$xmrAddress = $user['xmr_address'] ?? '';
$balance    = (float)($user['balance'] ?? 0);

$msg = ''; $msgType = 'info';

// ── Assign subaddress if user doesn't have one ──────────────────────────────
if ($xmrAddress === '') {
    try {
        $xmr    = new XmrGatewayClient();
        $result = $xmr->getNewSubaddress(XMR_ACCOUNT_INDEX);
        $xmrAddress = $result['address'] ?? '';
        if ($xmrAddress !== '') {
            $pdo->prepare('UPDATE users SET xmr_address=? WHERE id=?')
                ->execute([$xmrAddress, $uid]);
        }
    } catch (Throwable $e) {
        $msg = 'Could not assign XMR address: ' . htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8');
        $msgType = 'error';
    }
}

// ── Handle withdrawal ───────────────────────────────────────────────────────
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'withdraw') {
    csrf_verify();
    $toAddress = trim($_POST['to_address'] ?? '');
    $amountXmr = trim($_POST['amount'] ?? '');

    // Validate XMR address: starts with 4 or 8, length 95 or 106
    $validAddr = (bool)preg_match('/^[48][0-9A-Za-z]{94}$|^[48][0-9A-Za-z]{105}$/', $toAddress);

    if (!$validAddr) {
        $msg = 'Invalid Monero address. Must start with 4 or 8 and be 95 or 106 characters.';
        $msgType = 'error';
    } elseif (!is_numeric($amountXmr) || (float)$amountXmr <= 0) {
        $msg = 'Invalid amount.';
        $msgType = 'error';
    } elseif ((float)$amountXmr > $balance) {
        $msg = 'Insufficient balance.';
        $msgType = 'error';
    } else {
        $atomicAmount = (int)round((float)$amountXmr * PICONERO);
        $pdo->beginTransaction();
        try {
            // Deduct balance with row-lock
            $lockStmt = $pdo->prepare('SELECT balance FROM users WHERE id=? FOR UPDATE');
            $lockStmt->execute([$uid]);
            $currentBal = (float)$lockStmt->fetchColumn();

            if ((float)$amountXmr > $currentBal) {
                $pdo->rollBack();
                $msg = 'Insufficient balance (concurrent check).';
                $msgType = 'error';
            } else {
                $pdo->prepare('UPDATE users SET balance = balance - ? WHERE id = ?')
                    ->execute([$amountXmr, $uid]);

                // Record pending withdrawal
                $wStmt = $pdo->prepare(
                    'INSERT INTO withdrawals (user_id, to_address, amount_xmr, status)
                     VALUES (?,?,?,\'pending\')'
                );
                $wStmt->execute([$uid, $toAddress, $amountXmr]);
                $withdrawalId = (int)$pdo->lastInsertId();

                // Send via monero-wallet-rpc
                try {
                    $xmr    = new XmrGatewayClient();
                    $result = $xmr->transfer($toAddress, $atomicAmount);
                    $txHash = $result['tx_hash'] ?? null;
                    $pdo->prepare(
                        'UPDATE withdrawals SET tx_hash=?, status=\'sent\' WHERE id=?'
                    )->execute([$txHash, $withdrawalId]);
                    $msg = 'Withdrawal submitted! TX: ' . htmlspecialchars((string)$txHash, ENT_QUOTES, 'UTF-8');
                    $msgType = 'success';
                } catch (Throwable $e) {
                    // Revert balance, mark failed
                    $pdo->prepare('UPDATE users SET balance = balance + ? WHERE id = ?')
                        ->execute([$amountXmr, $uid]);
                    $pdo->prepare('UPDATE withdrawals SET status=\'failed\' WHERE id=?')
                        ->execute([$withdrawalId]);
                    $msg = 'Withdrawal failed: ' . htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8');
                    $msgType = 'error';
                }
                $pdo->commit();
                // Refresh balance
                $balStmt = $pdo->prepare('SELECT balance FROM users WHERE id=? LIMIT 1');
                $balStmt->execute([$uid]);
                $balance = (float)$balStmt->fetchColumn();
            }
        } catch (Throwable $e) {
            if ($pdo->inTransaction()) $pdo->rollBack();
            $msg = 'Error: ' . htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8');
            $msgType = 'error';
        }
    }
}

// ── Fetch deposit history ───────────────────────────────────────────────────
$depStmt = $pdo->prepare(
    'SELECT * FROM deposits WHERE user_id=? ORDER BY created_at DESC LIMIT 20'
);
$depStmt->execute([$uid]);
$deposits = $depStmt->fetchAll();

$witStmt = $pdo->prepare(
    'SELECT * FROM withdrawals WHERE user_id=? ORDER BY created_at DESC LIMIT 20'
);
$witStmt->execute([$uid]);
$withdrawals = $witStmt->fetchAll();

// QR code URL (uses public API as fallback; replace with local lib for production)
$qrUrl = 'https://api.qrserver.com/v1/create-qr-code/?size=200x200&data='
       . urlencode('monero:' . $xmrAddress);
?>
<h2>Wallet</h2>

<?php if ($msg): ?>
  <div class="alert alert-<?= htmlspecialchars($msgType, ENT_QUOTES, 'UTF-8') ?>">
    <?= $msg ?>
  </div>
<?php endif; ?>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">

<!-- DEPOSIT -->
<div class="card">
  <h3>Deposit XMR</h3>
  <p>Balance: <strong style="color:#e94560"><?= number_format($balance, 12) ?> XMR</strong></p>
  <?php if ($xmrAddress !== ''): ?>
    <p>Send XMR to your deposit address:</p>
    <code style="word-break:break-all;font-size:.8rem"><?= htmlspecialchars($xmrAddress, ENT_QUOTES, 'UTF-8') ?></code>
    <br><br>
    <img src="<?= htmlspecialchars($qrUrl, ENT_QUOTES, 'UTF-8') ?>"
         alt="QMR QR Code" style="border:4px solid #fff;border-radius:4px"
         title="Note: replace with local QR generator in production">
    <p style="font-size:.8rem;color:#aaa">
      Note: QR code uses api.qrserver.com. In production, replace with a local PHP QR library.
    </p>
    <p>Deposits are credited after <strong><?= XMR_MIN_CONFIRMATIONS ?> confirmations</strong>
       (run <code>cron_poll_deposits.php</code> on a schedule).</p>
  <?php else: ?>
    <p style="color:#e94560">No deposit address assigned. Please contact support or re-register.</p>
  <?php endif; ?>

  <h4>Deposit History</h4>
  <?php if (empty($deposits)): ?>
    <p>No deposits yet.</p>
  <?php else: ?>
    <table><tr><th>TX Hash</th><th>Amount</th><th>Confs</th><th>Status</th></tr>
    <?php foreach ($deposits as $d): ?>
      <tr>
        <td style="font-family:monospace;font-size:.75rem"><?= htmlspecialchars(substr($d['tx_hash'],0,12), ENT_QUOTES, 'UTF-8') ?>…</td>
        <td><?= number_format((float)$d['amount_xmr'],8) ?></td>
        <td><?= (int)$d['confirmations'] ?></td>
        <td><?= htmlspecialchars($d['status'], ENT_QUOTES, 'UTF-8') ?></td>
      </tr>
    <?php endforeach; ?>
    </table>
  <?php endif; ?>
</div>

<!-- WITHDRAWAL -->
<div class="card">
  <h3>Withdraw XMR</h3>
  <p>Balance: <strong style="color:#e94560"><?= number_format($balance, 12) ?> XMR</strong></p>
  <form method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="withdraw">
    <label>Recipient Monero Address</label>
    <input type="text" name="to_address" required placeholder="4... or 8... (95 or 106 chars)"
           autocomplete="off">
    <label>Amount (XMR)</label>
    <input type="number" name="amount" required step="0.000000000001" min="0.000001"
           placeholder="0.010000000000">
    <br><br>
    <button class="btn btn-primary" type="submit">Submit Withdrawal</button>
  </form>

  <h4>Withdrawal History</h4>
  <?php if (empty($withdrawals)): ?>
    <p>No withdrawals yet.</p>
  <?php else: ?>
    <table><tr><th>To</th><th>Amount</th><th>Status</th><th>TX</th></tr>
    <?php foreach ($withdrawals as $w): ?>
      <tr>
        <td style="font-family:monospace;font-size:.75rem"><?= htmlspecialchars(substr($w['to_address'],0,12), ENT_QUOTES, 'UTF-8') ?>…</td>
        <td><?= number_format((float)$w['amount_xmr'],8) ?></td>
        <td><?= htmlspecialchars($w['status'], ENT_QUOTES, 'UTF-8') ?></td>
        <td style="font-family:monospace;font-size:.75rem"><?= htmlspecialchars(substr((string)$w['tx_hash'],0,12), ENT_QUOTES, 'UTF-8') ?></td>
      </tr>
    <?php endforeach; ?>
    </table>
  <?php endif; ?>
</div>

</div><!-- /grid -->
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

ORDERS_PHP = r"""<?php
// orders.php
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_auth();

$pdo = db();
$uid = (int)$_SESSION['user_id'];

$stmt = $pdo->prepare(
    'SELECT o.*, p.name AS product_name, p.image_url
     FROM orders o JOIN products p ON p.id = o.product_id
     WHERE o.user_id = ? ORDER BY o.created_at DESC'
);
$stmt->execute([$uid]);
$orders = $stmt->fetchAll();
?>
<h2>My Orders</h2>
<div class="card">
<?php if (empty($orders)): ?>
  <p>No orders yet. <a href="/products.php">Browse the shop</a>.</p>
<?php else: ?>
  <table>
    <tr><th>#</th><th>Product</th><th>Qty</th><th>Total (XMR)</th><th>Status</th><th>Date</th></tr>
    <?php foreach ($orders as $o): ?>
      <tr>
        <td><?= (int)$o['id'] ?></td>
        <td><?= htmlspecialchars($o['product_name'], ENT_QUOTES, 'UTF-8') ?></td>
        <td><?= (int)$o['qty'] ?></td>
        <td><?= number_format((float)$o['total_xmr'], 8) ?></td>
        <td><?= htmlspecialchars($o['status'], ENT_QUOTES, 'UTF-8') ?></td>
        <td><?= htmlspecialchars($o['created_at'], ENT_QUOTES, 'UTF-8') ?></td>
      </tr>
    <?php endforeach; ?>
  </table>
<?php endif; ?>
</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

PRODUCTS_PHP = r"""<?php
// products.php — product catalog with atomic purchase
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/includes/csrf.php';
require_auth();

$pdo = db();
$uid = (int)$_SESSION['user_id'];
$msg = ''; $msgType = 'info';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'buy') {
    csrf_verify();
    $productId = (int)($_POST['product_id'] ?? 0);
    $qty       = max(1, (int)($_POST['qty'] ?? 1));

    $pdo->beginTransaction();
    try {
        // Lock product row and user balance
        $prodStmt = $pdo->prepare(
            'SELECT * FROM products WHERE id=? AND stock >= ? FOR UPDATE'
        );
        $prodStmt->execute([$productId, $qty]);
        $product = $prodStmt->fetch();

        $userStmt = $pdo->prepare('SELECT balance FROM users WHERE id=? FOR UPDATE');
        $userStmt->execute([$uid]);
        $balance = (float)$userStmt->fetchColumn();

        if (!$product) {
            $pdo->rollBack();
            $msg = 'Product not available or insufficient stock.';
            $msgType = 'error';
        } else {
            $total = (float)$product['price_xmr'] * $qty;
            if ($balance < $total) {
                $pdo->rollBack();
                $msg = 'Insufficient balance. <a href="/wallet.php">Deposit XMR</a>.';
                $msgType = 'error';
            } else {
                $pdo->prepare('UPDATE users SET balance = balance - ? WHERE id=?')
                    ->execute([$total, $uid]);
                $pdo->prepare('UPDATE products SET stock = stock - ? WHERE id=?')
                    ->execute([$qty, $productId]);
                $pdo->prepare(
                    'INSERT INTO orders (user_id, product_id, qty, total_xmr, status)
                     VALUES (?,?,?,?,\'paid\')'
                )->execute([$uid, $productId, $qty, $total]);
                $pdo->commit();
                $msg = 'Order placed! View in <a href="/orders.php">My Orders</a>.';
                $msgType = 'success';
            }
        }
    } catch (Throwable $e) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        $msg = 'Purchase error: ' . htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8');
        $msgType = 'error';
    }
}

$products = $pdo->query(
    'SELECT * FROM products WHERE stock > 0 ORDER BY created_at DESC'
)->fetchAll();
?>
<h2>Shop</h2>
<?php if ($msg): ?>
  <div class="alert alert-<?= htmlspecialchars($msgType, ENT_QUOTES, 'UTF-8') ?>"><?= $msg ?></div>
<?php endif; ?>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1.2rem">
<?php foreach ($products as $p): ?>
  <div class="card">
    <?php if ($p['image_url']): ?>
      <img src="<?= htmlspecialchars($p['image_url'], ENT_QUOTES, 'UTF-8') ?>"
           alt="" style="width:100%;border-radius:4px;margin-bottom:.8rem">
    <?php endif; ?>
    <h3><?= htmlspecialchars($p['name'], ENT_QUOTES, 'UTF-8') ?></h3>
    <p><?= htmlspecialchars($p['description'] ?? '', ENT_QUOTES, 'UTF-8') ?></p>
    <p style="color:#e94560;font-size:1.2rem">
      <?= number_format((float)$p['price_xmr'], 8) ?> XMR
    </p>
    <p>Stock: <?= (int)$p['stock'] ?></p>
    <form method="post">
      <?= csrf_field() ?>
      <input type="hidden" name="action" value="buy">
      <input type="hidden" name="product_id" value="<?= (int)$p['id'] ?>">
      <label>Qty: <input type="number" name="qty" value="1" min="1"
                         max="<?= (int)$p['stock'] ?>" style="width:80px"></label>
      <br><br>
      <button class="btn btn-primary" type="submit">Buy Now</button>
    </form>
  </div>
<?php endforeach; ?>
<?php if (empty($products)): ?>
  <p>No products available.</p>
<?php endif; ?>
</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

SETTINGS_PHP = r"""<?php
// settings.php
require_once __DIR__ . '/includes/header.php';
require_once __DIR__ . '/db.php';
require_once __DIR__ . '/includes/csrf.php';
require_auth();

$pdo = db();
$uid = (int)$_SESSION['user_id'];
$msg = ''; $msgType = 'info';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    csrf_verify();
    $action = $_POST['action'] ?? '';

    if ($action === 'change_password') {
        $current = $_POST['current_password'] ?? '';
        $new     = $_POST['new_password']     ?? '';
        $confirm = $_POST['confirm_password'] ?? '';
        $user    = current_user();
        if (!password_verify($current, $user['password_hash'])) {
            $msg = 'Current password is incorrect.'; $msgType = 'error';
        } elseif (strlen($new) < 8) {
            $msg = 'New password must be at least 8 characters.'; $msgType = 'error';
        } elseif ($new !== $confirm) {
            $msg = 'New passwords do not match.'; $msgType = 'error';
        } else {
            $hash = password_hash($new, PASSWORD_BCRYPT, ['cost' => 12]);
            $pdo->prepare('UPDATE users SET password_hash=? WHERE id=?')->execute([$hash, $uid]);
            $msg = 'Password updated.'; $msgType = 'success';
        }
    } elseif ($action === 'change_email') {
        $email = trim($_POST['email'] ?? '');
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            $msg = 'Invalid email.'; $msgType = 'error';
        } else {
            $pdo->prepare('UPDATE users SET email=? WHERE id=?')->execute([$email, $uid]);
            $msg = 'Email updated.'; $msgType = 'success';
        }
    } elseif ($action === 'set_pin') {
        $pin = $_POST['pin'] ?? '';
        if (!preg_match('/^\d{4,8}$/', $pin)) {
            $msg = 'PIN must be 4–8 digits.'; $msgType = 'error';
        } else {
            $pinHash = password_hash($pin, PASSWORD_BCRYPT);
            $stm = $pdo->prepare(
                'INSERT INTO settings (user_id, `key`, value) VALUES (?,\'withdrawal_pin\',?) '
              . 'ON DUPLICATE KEY UPDATE value=?'
            );
            $stm->execute([$uid, $pinHash, $pinHash]);
            $msg = 'Withdrawal PIN updated.'; $msgType = 'success';
        }
    }
    // Refresh user cache
    $_SESSION['user_cache'] = null;
}

$user = current_user();
?>
<h2>Settings</h2>
<?php if ($msg): ?>
  <div class="alert alert-<?= htmlspecialchars($msgType, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($msg, ENT_QUOTES, 'UTF-8') ?></div>
<?php endif; ?>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">

<div class="card">
  <h3>Change Password</h3>
  <form method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="change_password">
    <label>Current Password</label>
    <input type="password" name="current_password" required autocomplete="current-password">
    <label>New Password</label>
    <input type="password" name="new_password" required minlength="8" autocomplete="new-password">
    <label>Confirm New Password</label>
    <input type="password" name="confirm_password" required autocomplete="new-password">
    <br><br>
    <button class="btn btn-primary" type="submit">Update Password</button>
  </form>
</div>

<div class="card">
  <h3>Change Email</h3>
  <form method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="change_email">
    <label>New Email</label>
    <input type="email" name="email" required value="<?= htmlspecialchars($user['email'] ?? '', ENT_QUOTES, 'UTF-8') ?>">
    <br><br>
    <button class="btn btn-primary" type="submit">Update Email</button>
  </form>
</div>

<div class="card">
  <h3>Withdrawal PIN</h3>
  <p>Set a 4–8 digit numeric PIN required to confirm withdrawals.</p>
  <form method="post">
    <?= csrf_field() ?>
    <input type="hidden" name="action" value="set_pin">
    <label>PIN (4–8 digits)</label>
    <input type="password" name="pin" pattern="\d{4,8}" required inputmode="numeric">
    <br><br>
    <button class="btn btn-primary" type="submit">Set PIN</button>
  </form>
</div>

<div class="card">
  <h3>Two-Factor Authentication</h3>
  <p>2FA support is planned for a future update.</p>
  <button class="btn btn-secondary" disabled>Enable 2FA (Coming Soon)</button>
</div>

</div>
<?php require_once __DIR__ . '/includes/footer.php'; ?>
"""

README_BACKEND_TEMPLATE = """\
# README_BACKEND.md — XMR Shop PHP/MySQL Backend

Generated by `win_site_cloner.py` in `--mode dynamic`.

## Prerequisites

- PHP 8.0+ with extensions: `pdo_mysql`, `curl`, `json`, `session`
- MySQL 5.7+ or MariaDB 10.3+
- `monero-wallet-rpc` running and accessible (for deposit/withdrawal)

## Quick Start

### 1. Import the database schema

```bash
mysql -u root -p -e "CREATE DATABASE xmrshop CHARACTER SET utf8mb4;"
mysql -u root -p xmrshop < schema.sql
```

### 2. Set environment variables

```bash
export DB_HOST=localhost
export DB_NAME=xmrshop
export DB_USER=root
export DB_PASS=your_password

export XMR_RPC_URL=http://127.0.0.1:18082/json_rpc
export XMR_RPC_USER=walletrpc_user      # optional
export XMR_RPC_PASS=walletrpc_password  # optional

export ADMIN_USER=admin
export ADMIN_PASS=a_strong_password_here
export ADMIN_EMAIL=admin@example.com
```

### 3. Run the installer

Navigate to `http://localhost:8000/install.php` and click **Run Installation**.
**Delete `install.php` immediately after.**

### 4. Start the development server

```bash
cd {output_dir}
php -S localhost:8000
```

Then visit `http://localhost:8000`.

## File Structure

```
{output_dir}/
├── config.php                  # DB + XMR RPC credentials (reads env vars)
├── db.php                      # PDO helper
├── schema.sql                  # Database schema
├── install.php                 # One-shot installer (delete after use)
├── xmrgateway_client.php       # monero-wallet-rpc JSON-RPC client
├── cron_poll_deposits.php      # Cron job: poll & credit deposits
├── login.php / register.php / logout.php
├── dashboard.php
├── wallet.php                  # Deposit & withdrawal UI
├── orders.php
├── products.php
├── settings.php
└── includes/
    ├── header.php
    ├── footer.php
    ├── auth.php
    └── csrf.php
```

## Cron / Scheduled Task

Run deposit polling every 2 minutes:

```cron
*/2 * * * * php /path/to/{output_dir}/cron_poll_deposits.php >> /var/log/xmr_deposits.log 2>&1
```

On Windows (Task Scheduler):
```
php C:\\path\\to\\{output_dir}\\cron_poll_deposits.php
```

## monero-wallet-rpc

This backend connects to `monero-wallet-rpc` via JSON-RPC (see `xmrgateway_client.php`).
Start it with:

```bash
monero-wallet-rpc --wallet-file my_wallet --rpc-bind-port 18082 \\
  --rpc-login walletrpc_user:walletrpc_password --daemon-address node.moneroworld.com:18089
```

The `XmrGatewayClient` class mirrors the RPC surface of the
[bitbybit91/xmrgateway](https://github.com/bitbybit91/xmrgateway) project
and uses digest authentication matching the `monero-wallet-rpc` default.

## Security Notes

- All SQL uses prepared statements (PDO).
- All output is escaped with `htmlspecialchars`.
- CSRF tokens protect every POST form.
- Passwords use bcrypt (`PASSWORD_BCRYPT`, cost 12).
- Sessions use `HttpOnly`, `SameSite=Lax`, and `Secure` (when HTTPS).
- Login is rate-limited: 5 attempts → 15-minute lockout.
- Delete `install.php` after setup!
"""

README_OFFLINE_TEMPLATE = """\
README_OFFLINE.txt — Offline Site Mirror
=========================================
Generated by win_site_cloner.py

Source URL : {url}
Mode       : {mode}
Output dir : {output}
JS stripped: {js_stripped}
Date       : {date}

{mode_instructions}
"""

README_OFFLINE_STATIC_INSTRUCTIONS = """\
VIEWING THE SITE
----------------
Open index.html (or any .html file) directly in your browser.
No server required.
"""

README_OFFLINE_DYNAMIC_INSTRUCTIONS = """\
RUNNING THE PHP/MYSQL BACKEND
------------------------------
1. Import the schema:
   mysql -u root -p -e "CREATE DATABASE xmrshop CHARACTER SET utf8mb4;"
   mysql -u root -p xmrshop < schema.sql

2. Set environment variables (DB_HOST, DB_NAME, DB_USER, DB_PASS,
   XMR_RPC_URL, ADMIN_USER, ADMIN_PASS — see README_BACKEND.md).

3. Start PHP built-in server:
   php -S localhost:8000

4. Visit http://localhost:8000/install.php and click Run Installation.
   DELETE install.php immediately after!

5. Visit http://localhost:8000

See README_BACKEND.md for full instructions including cron setup
and monero-wallet-rpc configuration.
"""

README_OFFLINE_ONION_INSTRUCTIONS = """\
VIEWING THE ONION MIRROR
-------------------------
Open index.html (or any .html file) directly in your browser.
JavaScript was {js_status}.

If --keep-js was used, you may need a local server to serve .js files:
  python -m http.server 8080
  Then open http://localhost:8080/
"""


# ---------------------------------------------------------------------------
# Crawler / scraper
# ---------------------------------------------------------------------------

class SiteCrawler:
    def __init__(
        self,
        start_url: str,
        output_dir: Path,
        max_depth: int = 3,
        max_pages: int = 200,
        mode: str = "static",
        keep_js: bool = False,
        tor_proxy: str = "socks5h://127.0.0.1:9050",
    ) -> None:
        self.start_url   = start_url.rstrip("/")
        self.output_dir  = output_dir
        self.max_depth   = max_depth
        self.max_pages   = max_pages
        self.mode        = mode
        self.keep_js     = keep_js
        self.tor_proxy   = tor_proxy

        parsed = urllib.parse.urlparse(start_url)
        self.base_scheme = parsed.scheme
        self.base_host   = parsed.netloc  # includes port if present

        self._visited: Set[str]  = set()
        self._queue: list        = []   # (url, depth)
        self._asset_queue: list  = []   # (url, local_path)

        import requests as _req
        from bs4 import BeautifulSoup as _BS  # noqa: F401

        self.requests  = _req
        self.BeautifulSoup = _BS

        self.session = self.requests.Session()
        timeout_val = 60 if mode == "onion" else 15
        self.timeout = timeout_val

        if mode == "onion":
            self.session.proxies = {
                "http":  tor_proxy,
                "https": tor_proxy,
            }

        self.session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; win_site_cloner/2.0)"})

        # Track first CSS link and logo for PHP header injection
        self.first_css:  Optional[str] = None
        self.first_logo: Optional[str] = None

    # ------------------------------------------------------------------
    def _is_same_origin(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https", ""):
            return False
        host = parsed.netloc or self.base_host
        # For onion mode allow .onion hosts from the same base
        return host == self.base_host

    def _normalize(self, url: str, base: str) -> str:
        url = url.strip()
        if url.startswith("//"):
            url = self.base_scheme + ":" + url
        joined = urllib.parse.urljoin(base, url)
        # Strip fragment
        joined = urllib.parse.urldefrag(joined)[0]
        return joined

    def _url_to_local_path(self, url: str) -> Path:
        parsed = urllib.parse.urlparse(url)
        path   = parsed.path.lstrip("/") or "index"
        path   = urllib.parse.unquote(path)
        # Sanitize path components
        parts  = [re.sub(r'[<>:"|?*\\]', "_", p) for p in Path(path).parts]
        if not parts:
            parts = ["index.html"]
        # Ensure .html extension for pages
        local  = self.output_dir.joinpath(*parts)
        if not local.suffix:
            local = local / "index.html"
        elif local.suffix.lower() not in (
            ".html", ".htm", ".css", ".js", ".png", ".jpg", ".jpeg",
            ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot",
            ".pdf", ".xml", ".json", ".webp",
        ):
            local = local.with_suffix(local.suffix + ".html")
        return local

    def _fetch(self, url: str) -> Optional[requests.Response]:  # type: ignore[name-defined]
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            log.warning("Failed to fetch %s: %s", url, exc)
            return None

    def _save(self, local_path: Path, content: bytes) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            local_path.write_bytes(content)
        except OSError as exc:
            log.warning("Could not write %s: %s", local_path, exc)

    def _strip_js(self, soup) -> None:
        """Remove all script tags, on* handlers, and javascript: links."""
        for tag in soup.find_all("script"):
            tag.decompose()
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if attr.lower().startswith("on"):
                    del tag[attr]
        for a in soup.find_all("a", href=True):
            if a["href"].strip().lower().startswith("javascript:"):
                a["href"] = "#"

    def _rewrite_links(self, soup, page_url: str, local_path: Path) -> None:
        """Rewrite all asset/link URLs to relative local paths."""
        def rel(target_local: Path) -> str:
            try:
                return str(os.path.relpath(target_local, local_path.parent)).replace("\\", "/")
            except ValueError:
                return target_local.as_posix()

        # CSS links
        for tag in soup.find_all("link", href=True):
            href = self._normalize(tag["href"], page_url)
            if self._is_same_origin(href):
                tlp = self._url_to_local_path(href)
                tag["href"] = rel(tlp)
                if tag.get("rel") == ["stylesheet"] and self.first_css is None:
                    self.first_css = tag["href"]
                self._asset_queue.append((href, tlp))

        # Images
        for tag in soup.find_all("img", src=True):
            src = self._normalize(tag["src"], page_url)
            if self._is_same_origin(src):
                tlp = self._url_to_local_path(src)
                if self.first_logo is None:
                    self.first_logo = rel(tlp)
                tag["src"] = rel(tlp)
                self._asset_queue.append((src, tlp))

        # Anchor hrefs → local .html
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("#") or href.lower().startswith("mailto:"):
                continue
            abs_href = self._normalize(href, page_url)
            if self._is_same_origin(abs_href):
                tlp = self._url_to_local_path(abs_href)
                a["href"] = rel(tlp)

        # JS assets (only when keep_js)
        if self.keep_js:
            for tag in soup.find_all("script", src=True):
                src = self._normalize(tag["src"], page_url)
                if self._is_same_origin(src):
                    tlp = self._url_to_local_path(src)
                    tag["src"] = rel(tlp)
                    self._asset_queue.append((src, tlp))

    def _process_html(self, url: str, content: bytes, local_path: Path) -> bytes:
        try:
            soup = self.BeautifulSoup(content, "lxml")
        except Exception:
            soup = self.BeautifulSoup(content, "html.parser")

        if not self.keep_js:
            self._strip_js(soup)

        self._rewrite_links(soup, url, local_path)

        # Inject banner comment
        js_note = "JavaScript preserved." if self.keep_js else "JavaScript stripped."
        banner  = (
            f"<!-- Archived by win_site_cloner.py | source: {url} | {js_note} -->\n"
        )
        return (banner + str(soup)).encode("utf-8", errors="replace")

    def _discover_links(self, url: str, soup) -> list[str]:
        links = []
        for a in soup.find_all("a", href=True):
            href = self._normalize(a["href"], url)
            if self._is_same_origin(href) and href not in self._visited:
                links.append(href)
        return links

    # ------------------------------------------------------------------
    def crawl(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Crawl the site.  Returns (first_css_local, first_logo_local) for PHP
        header injection.
        """
        self._queue = [(self.start_url, 0)]
        pages_fetched = 0

        while self._queue and pages_fetched < self.max_pages:
            url, depth = self._queue.pop(0)
            if url in self._visited:
                continue
            self._visited.add(url)

            log.info("[%d/%d] Fetching %s", pages_fetched + 1, self.max_pages, url)
            resp = self._fetch(url)
            if resp is None:
                continue

            ct = resp.headers.get("Content-Type", "")
            local_path = self._url_to_local_path(url)

            if "text/html" in ct:
                processed = self._process_html(url, resp.content, local_path)
                self._save(local_path, processed)

                # Discover child links
                if depth < self.max_depth:
                    try:
                        soup = self.BeautifulSoup(resp.content, "lxml")
                    except Exception:
                        soup = self.BeautifulSoup(resp.content, "html.parser")
                    for link in self._discover_links(url, soup):
                        if link not in self._visited:
                            self._queue.append((link, depth + 1))
            else:
                self._save(local_path, resp.content)

            pages_fetched += 1
            time.sleep(0.1)

        # Download assets
        log.info("Downloading %d assets…", len(self._asset_queue))
        seen_assets: Set[str] = set()
        for asset_url, asset_path in self._asset_queue:
            if asset_url in seen_assets:
                continue
            seen_assets.add(asset_url)
            if asset_path.exists():
                continue
            log.debug("Asset: %s", asset_url)
            resp = self._fetch(asset_url)
            if resp:
                self._save(asset_path, resp.content)
            time.sleep(0.05)

        return self.first_css, self.first_logo

    # ------------------------------------------------------------------
    def verify_tor(self) -> None:
        """Probe Tor connectivity and log a helpful error if it's not running."""
        check_url = "https://check.torproject.org/api/ip"
        log.info("Verifying Tor connectivity via %s …", self.tor_proxy)
        try:
            resp = self.session.get(check_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("IsTor"):
                log.info("Tor proxy OK — IP: %s", data.get("IP", "?"))
            else:
                log.warning(
                    "Connected via proxy but Tor is NOT detected (IP: %s). "
                    "Ensure you are routing through a Tor exit node.",
                    data.get("IP", "?"),
                )
        except Exception as exc:
            log.error(
                "Tor proxy check FAILED: %s\n"
                "Remediation:\n"
                "  • Install and start Tor Browser or the 'tor' service.\n"
                "  • On Windows: download Tor Expert Bundle from https://www.torproject.org/download/tor/\n"
                "    and run: tor.exe\n"
                "  • Default SOCKS5 port is 9050; pass --tor-proxy socks5h://HOST:PORT if different.",
                exc,
            )
            raise SystemExit(1) from exc


# ---------------------------------------------------------------------------
# PHP backend generation
# ---------------------------------------------------------------------------

class PhpBackendGenerator:
    def __init__(
        self,
        output_dir: Path,
        first_css: Optional[str],
        first_logo: Optional[str],
        db_host: str = "localhost",
        db_name: str = "xmrshop",
        db_user: str = "root",
        db_pass: str = "",
        admin_user: str = "admin",
        admin_pass: str = "changeme_NOW",
    ) -> None:
        self.out       = output_dir
        self.first_css = first_css
        self.first_logo = first_logo
        self.db_host   = db_host
        self.db_name   = db_name
        self.db_user   = db_user
        self.db_pass   = db_pass
        self.admin_user = admin_user
        self.admin_pass = admin_pass

    def _w(self, rel_path: str, content: str) -> None:
        p = self.out / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        log.debug("Generated %s", p)

    def _build_header(self) -> str:
        css_link = ""
        if self.first_css:
            css_link = f'<link rel="stylesheet" href="{self.first_css}">'
        logo_img = ""
        if self.first_logo:
            logo_img = f'<img src="{self.first_logo}" alt="Logo" class="logo">'
        return HEADER_PHP_TEMPLATE.replace("{CSS_LINK}", css_link).replace("{LOGO_IMG}", logo_img)

    def generate(self) -> None:
        log.info("Generating PHP backend in %s …", self.out)

        # Config / DB helpers
        self._w("config.php",              CONFIG_PHP)
        self._w("db.php",                  DB_PHP)
        self._w("schema.sql",              SCHEMA_SQL)
        self._w("install.php",             INSTALL_PHP)
        self._w("xmrgateway_client.php",   XMR_GATEWAY_CLIENT_PHP)
        self._w("cron_poll_deposits.php",  CRON_POLL_DEPOSITS_PHP)

        # Includes
        self._w("includes/csrf.php",   CSRF_PHP)
        self._w("includes/auth.php",   AUTH_PHP)
        self._w("includes/header.php", self._build_header())
        self._w("includes/footer.php", FOOTER_PHP)

        # Pages
        self._w("login.php",    LOGIN_PHP)
        self._w("register.php", REGISTER_PHP)
        self._w("logout.php",   LOGOUT_PHP)
        self._w("dashboard.php", DASHBOARD_PHP)
        self._w("wallet.php",   WALLET_PHP)
        self._w("orders.php",   ORDERS_PHP)
        self._w("products.php", PRODUCTS_PHP)
        self._w("settings.php", SETTINGS_PHP)

        log.info("PHP backend generation complete.")


# ---------------------------------------------------------------------------
# README writers
# ---------------------------------------------------------------------------

def write_readme_offline(
    output_dir: Path,
    url: str,
    mode: str,
    keep_js: bool,
) -> None:
    import datetime

    if mode == "dynamic":
        mode_instructions = README_OFFLINE_DYNAMIC_INSTRUCTIONS
    elif mode == "onion":
        js_status = "preserved" if keep_js else "stripped"
        mode_instructions = README_OFFLINE_ONION_INSTRUCTIONS.format(js_status=js_status)
    else:
        mode_instructions = README_OFFLINE_STATIC_INSTRUCTIONS

    content = README_OFFLINE_TEMPLATE.format(
        url=url,
        mode=mode,
        output=str(output_dir),
        js_stripped=str(not keep_js),
        date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        mode_instructions=mode_instructions,
    )
    (output_dir / "README_OFFLINE.txt").write_text(content, encoding="utf-8")


def write_readme_backend(output_dir: Path) -> None:
    content = README_BACKEND_TEMPLATE.format(output_dir=str(output_dir))
    (output_dir / "README_BACKEND.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Zip packaging
# ---------------------------------------------------------------------------

def zip_output(output_dir: Path) -> Path:
    zip_path = output_dir.with_suffix(".zip")
    log.info("Creating archive %s …", zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in output_dir.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(output_dir.parent))
    log.info("Archive created: %s", zip_path)
    return zip_path


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="win_site_cloner.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--url",       required=True, help="Target URL to clone.")
    p.add_argument("--output",    default="./site_mirror",
                   help="Output directory (default: ./site_mirror).")
    p.add_argument("--mode",      choices=["static", "dynamic", "onion"], default="static",
                   help="Cloning mode: static (default), dynamic (PHP+MySQL), onion (Tor).")
    p.add_argument("--max-depth", type=int, default=3,
                   help="Maximum crawl depth (default: 3).")
    p.add_argument("--max-pages", type=int, default=200,
                   help="Maximum pages to fetch (default: 200).")
    p.add_argument("--zip",       action="store_true",
                   help="Package output into a .zip archive after cloning.")
    p.add_argument("--skip-deps", action="store_true",
                   help="Skip auto-installing Python dependencies.")
    p.add_argument("--keep-js",   action="store_true",
                   help="Preserve JavaScript (script tags, on* handlers, .js assets).")
    p.add_argument("--tor-proxy", default="socks5h://127.0.0.1:9050",
                   help="Tor SOCKS5 proxy URL (default: socks5h://127.0.0.1:9050). "
                        "Only used in --mode onion.")
    # DB seeding flags for dynamic mode
    p.add_argument("--db-host",   default="localhost", help="MySQL host (seeds config.php default).")
    p.add_argument("--db-name",   default="xmrshop",  help="MySQL database name.")
    p.add_argument("--db-user",   default="root",      help="MySQL username.")
    p.add_argument("--db-pass",   default="",          help="MySQL password.")
    p.add_argument("--admin-user", default="admin",    help="Admin username for install.php.")
    p.add_argument("--admin-pass", default="changeme_NOW",
                   help="Admin password for install.php (override via ADMIN_PASS env var).")
    return p


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_args(args: argparse.Namespace) -> None:
    url = args.url
    if not re.match(r"^https?://", url, re.I):
        raise SystemExit("ERROR: --url must start with http:// or https://")

    if args.mode == "onion":
        if not re.match(r"^socks5h?://", args.tor_proxy, re.I):
            raise SystemExit(
                "ERROR: --tor-proxy must be a socks5h:// or socks5:// URL, "
                "e.g. socks5h://127.0.0.1:9050"
            )

    if args.max_depth < 0:
        raise SystemExit("ERROR: --max-depth must be >= 0")
    if args.max_pages < 1:
        raise SystemExit("ERROR: --max-pages must be >= 1")

    if args.mode == "dynamic" and args.admin_pass in ("changeme_NOW", ""):
        log.warning(
            "WARNING: Using default admin password. Set --admin-pass or ADMIN_PASS env var "
            "before running install.php."
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = build_parser()
    args   = parser.parse_args()
    validate_args(args)

    # ── Install dependencies ────────────────────────────────────────────────
    if not args.skip_deps:
        packages = list(PIP_PACKAGES_CORE)
        if args.mode == "onion":
            packages += PIP_PACKAGES_SOCKS
        _ensure_packages(packages)

    # ── Prepare output directory ────────────────────────────────────────────
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Tor connectivity check ──────────────────────────────────────────────
    if args.mode == "onion":
        crawler_check = SiteCrawler(
            start_url=args.url,
            output_dir=output_dir,
            mode="onion",
            keep_js=args.keep_js,
            tor_proxy=args.tor_proxy,
        )
        crawler_check.verify_tor()

    # ── Crawl ───────────────────────────────────────────────────────────────
    crawler = SiteCrawler(
        start_url=args.url,
        output_dir=output_dir,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        mode=args.mode,
        keep_js=args.keep_js,
        tor_proxy=args.tor_proxy,
    )

    log.info("Starting crawl: %s  [mode=%s, keep_js=%s]", args.url, args.mode, args.keep_js)
    first_css, first_logo = crawler.crawl()
    log.info("Crawl complete. Pages: %d", len(crawler._visited))

    # ── Generate PHP backend ────────────────────────────────────────────────
    if args.mode == "dynamic":
        gen = PhpBackendGenerator(
            output_dir=output_dir,
            first_css=first_css,
            first_logo=first_logo,
            db_host=args.db_host,
            db_name=args.db_name,
            db_user=args.db_user,
            db_pass=args.db_pass,
            admin_user=args.admin_user,
            admin_pass=args.admin_pass,
        )
        gen.generate()
        write_readme_backend(output_dir)

    # ── Write README_OFFLINE.txt ────────────────────────────────────────────
    write_readme_offline(output_dir, args.url, args.mode, args.keep_js)

    # ── Zip ─────────────────────────────────────────────────────────────────
    if args.zip:
        zip_output(output_dir)

    log.info("Done! Output: %s", output_dir)
    if args.mode == "dynamic":
        log.info(
            "Next steps: import schema.sql, start PHP server with 'php -S localhost:8000 -t %s', "
            "run install.php, then delete it. See README_BACKEND.md for details.",
            output_dir,
        )


if __name__ == "__main__":
    main()
