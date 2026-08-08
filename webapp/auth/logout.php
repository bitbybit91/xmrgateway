<?php
/**
 * webapp/auth/logout.php
 */
require_once dirname(__DIR__) . '/config/app.php';
session_destroy();
header('Location: ' . SITE_URL . '/index.php');
exit;
