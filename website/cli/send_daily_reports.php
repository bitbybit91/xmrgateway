#!/usr/bin/env php
<?php
/**
 * send_daily_reports.php
 * Runs once every 24 hours via cron.
 * Sends each user a daily ROI summary for their active investments.
 */

declare(strict_types=1);

define('BASE_PATH',   dirname(__DIR__));
define('PUBLIC_PATH', BASE_PATH . '/public');

require BASE_PATH . '/vendor/autoload.php';
require BASE_PATH . '/config/config.php';

use App\Core\Database;
use App\Services\Mailer;

$db     = Database::getInstance();
$mailer = new Mailer();
$today  = date('Y-m-d');
$sent   = 0;

// Find all users who earned ROI today
$rows = $db->fetchAll(
    "SELECT u.id, u.name, u.email, SUM(t.amount_usd) AS daily_roi
     FROM transactions t
     JOIN users u ON u.id = t.user_id
     WHERE t.type = 'roi' AND t.status = 'confirmed' AND DATE(t.created_at) = ?
     GROUP BY u.id",
    [$today]
);

foreach ($rows as $row) {
    if ((float)$row['daily_roi'] <= 0) continue;

    try {
        $mailer->sendRoiAccrual($row['email'], $row['name'], (float)$row['daily_roi']);
        $sent++;
    } catch (\Throwable $e) {
        error_log("[send_daily_reports] Failed to mail {$row['email']}: " . $e->getMessage());
    }
}

echo "[send_daily_reports] Sent $sent daily ROI emails for $today.\n";
