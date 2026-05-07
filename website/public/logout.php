<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';

auth_start_session();

try {
    $pdo = DB::get();
    auth_logout($pdo);
} catch (PDOException $e) {
    // Destroy session even if DB fails
    session_destroy();
}

header('Location: /login.php');
exit;
