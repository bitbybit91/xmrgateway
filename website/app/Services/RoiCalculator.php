<?php

declare(strict_types=1);

namespace App\Services;

use App\Core\Database;

class RoiCalculator
{
    public function calculateDailyRoi(float $principalUsd, float $dailyRoiPercent): float
    {
        return $principalUsd * ($dailyRoiPercent / 100.0);
    }

    public function calculateHourlyRoi(float $principalUsd, float $dailyRoiPercent): float
    {
        return $this->calculateDailyRoi($principalUsd, $dailyRoiPercent) / 24.0;
    }

    public function calculateTotalRoi(float $principalUsd, float $dailyRoiPercent, int $durationDays): float
    {
        return $this->calculateDailyRoi($principalUsd, $dailyRoiPercent) * $durationDays;
    }

    public function calculateEndDate(string $startDate, int $durationDays): string
    {
        return date('Y-m-d', strtotime($startDate . ' +' . $durationDays . ' days'));
    }

    public function isMatured(string $endDate): bool
    {
        return strtotime($endDate) <= time();
    }

    public function calculateAccruedRoi(int $investmentId): float
    {
        $row = Database::getInstance()->fetchOne(
            'SELECT COALESCE(SUM(amount_usd), 0) as total FROM roi_accruals WHERE investment_id = ?',
            [$investmentId]
        );
        return (float)($row['total'] ?? 0);
    }
}
