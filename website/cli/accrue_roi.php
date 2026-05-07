#!/usr/bin/env php
<?php
/**
 * accrue_roi.php
 * Runs hourly via cron.
 * Calculates hourly ROI for every active investment and records it.
 * Marks investments as matured when end_date has passed.
 */

declare(strict_types=1);

define('BASE_PATH',   dirname(__DIR__));
define('PUBLIC_PATH', BASE_PATH . '/public');

require BASE_PATH . '/vendor/autoload.php';
require BASE_PATH . '/config/config.php';

use App\Core\Database;
use App\Models\Investment;
use App\Services\RoiCalculator;

$db      = Database::getInstance();
$calc    = new RoiCalculator();
$now     = date('Y-m-d H:i:s');
$today   = date('Y-m-d');

// Fetch all active investments
$active = $db->fetchAll(
    "SELECT i.*, p.daily_roi_percent, p.duration_days
     FROM investments i JOIN plans p ON p.id = i.plan_id
     WHERE i.status = 'active'"
);

$accrued  = 0;
$matured  = 0;

foreach ($active as $inv) {
    $principalUsd = (float)$inv['amount_usd'];
    $dailyRoi     = (float)$inv['daily_roi_percent'];
    $hourlyRoi    = $calc->calculateHourlyRoi($principalUsd, $dailyRoi);
    $endDate      = $inv['end_date'];

    // Check if investment has matured
    if ($endDate && strtotime($endDate) <= time()) {
        Investment::mature((int)$inv['id']);
        $matured++;
        echo "[accrue_roi] Investment #{$inv['id']} matured.\n";
        continue;
    }

    // Record hourly accrual
    try {
        $db->insert('roi_accruals', [
            'investment_id' => (int)$inv['id'],
            'amount_usd'    => round($hourlyRoi, 8),
            'accrual_date'  => $today,
            'created_at'    => $now,
        ]);

        // Update total_roi_usd on the investment
        $db->execute(
            'UPDATE investments SET total_roi_usd = total_roi_usd + ?, updated_at = ? WHERE id = ?',
            [round($hourlyRoi, 8), $now, $inv['id']]
        );

        // Record a confirmed ROI transaction for the balance calculation
        $db->insert('transactions', [
            'user_id'       => $inv['user_id'],
            'investment_id' => $inv['id'],
            'type'          => 'roi',
            'amount_usd'    => round($hourlyRoi, 8),
            'amount_xmr'    => 0,
            'status'        => 'confirmed',
            'created_at'    => $now,
            'updated_at'    => $now,
        ]);

        $accrued++;
    } catch (\Throwable $e) {
        error_log("[accrue_roi] Error for investment #{$inv['id']}: " . $e->getMessage());
    }
}

echo "[accrue_roi] Done. Accrued for $accrued investments, $matured matured.\n";
