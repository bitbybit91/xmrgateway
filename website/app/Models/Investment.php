<?php

declare(strict_types=1);

namespace App\Models;

use App\Core\Database;

class Investment
{
    public static function findById(int $id): ?array
    {
        $row = Database::getInstance()->fetchOne(
            'SELECT i.*, p.name as plan_name, p.daily_roi_percent, p.duration_days
             FROM investments i JOIN plans p ON p.id = i.plan_id
             WHERE i.id = ?',
            [$id]
        );
        return $row ?: null;
    }

    public static function findByUser(int $userId, string $status = ''): array
    {
        $sql    = 'SELECT i.*, p.name as plan_name, p.daily_roi_percent, p.type as plan_type
                   FROM investments i JOIN plans p ON p.id = i.plan_id
                   WHERE i.user_id = ?';
        $params = [$userId];
        if ($status !== '') {
            $sql    .= ' AND i.status = ?';
            $params[] = $status;
        }
        $sql .= ' ORDER BY i.created_at DESC';
        return Database::getInstance()->fetchAll($sql, $params);
    }

    public static function findAll(string $status = '', int $limit = 50, int $offset = 0): array
    {
        $sql    = 'SELECT i.*, u.name as user_name, u.email, p.name as plan_name
                   FROM investments i
                   JOIN users u ON u.id = i.user_id
                   JOIN plans p ON p.id = i.plan_id';
        $params = [];
        if ($status !== '') {
            $sql    .= ' WHERE i.status = ?';
            $params[] = $status;
        }
        $sql    .= ' ORDER BY i.created_at DESC LIMIT ? OFFSET ?';
        $params[] = $limit;
        $params[] = $offset;
        return Database::getInstance()->fetchAll($sql, $params);
    }

    public static function create(array $data): int
    {
        $data['created_at'] = date('Y-m-d H:i:s');
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->insert('investments', $data);
    }

    public static function update(int $id, array $data): bool
    {
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->update('investments', $data, 'id = ?', [$id]) >= 0;
    }

    public static function activate(int $id): bool
    {
        $db  = Database::getInstance();
        $inv = $db->fetchOne(
            'SELECT i.*, p.duration_days FROM investments i JOIN plans p ON p.id = i.plan_id WHERE i.id = ?',
            [$id]
        );
        if (!$inv) return false;

        $start = date('Y-m-d H:i:s');
        $end   = date('Y-m-d H:i:s', strtotime("+{$inv['duration_days']} days"));

        return $db->update('investments', [
            'status'     => 'active',
            'start_date' => $start,
            'end_date'   => $end,
            'updated_at' => $start,
        ], 'id = ?', [$id]) > 0;
    }

    public static function mature(int $id): bool
    {
        return Database::getInstance()->update('investments', [
            'status'     => 'matured',
            'updated_at' => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }

    public static function getTotalInvested(): float
    {
        $row = Database::getInstance()->fetchOne(
            "SELECT COALESCE(SUM(amount_usd), 0) as total FROM investments WHERE status != 'cancelled'"
        );
        return (float)($row['total'] ?? 0);
    }

    public static function getActiveCount(): int
    {
        $row = Database::getInstance()->fetchOne(
            "SELECT COUNT(*) as cnt FROM investments WHERE status = 'active'"
        );
        return (int)($row['cnt'] ?? 0);
    }

    public static function getStats(): array
    {
        $db = Database::getInstance();
        return [
            'total_invested' => self::getTotalInvested(),
            'active_count'   => self::getActiveCount(),
            'pending_count'  => (int)($db->fetchOne(
                "SELECT COUNT(*) as cnt FROM investments WHERE status = 'pending_payment'"
            )['cnt'] ?? 0),
            'matured_count'  => (int)($db->fetchOne(
                "SELECT COUNT(*) as cnt FROM investments WHERE status = 'matured'"
            )['cnt'] ?? 0),
        ];
    }
}
