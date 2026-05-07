<?php

declare(strict_types=1);

namespace App\Models;

use App\Core\Database;

class Payout
{
    public static function findById(int $id): ?array
    {
        $row = Database::getInstance()->fetchOne('SELECT * FROM payouts WHERE id = ?', [$id]);
        return $row ?: null;
    }

    public static function findByUser(int $userId): array
    {
        return Database::getInstance()->fetchAll(
            'SELECT * FROM payouts WHERE user_id = ? ORDER BY created_at DESC',
            [$userId]
        );
    }

    public static function findPending(): array
    {
        return Database::getInstance()->fetchAll(
            "SELECT p.*, u.name as user_name, u.email FROM payouts p
             JOIN users u ON u.id = p.user_id
             WHERE p.status = 'pending' ORDER BY p.created_at ASC"
        );
    }

    public static function findAll(int $limit = 50, int $offset = 0): array
    {
        return Database::getInstance()->fetchAll(
            'SELECT p.*, u.name as user_name, u.email FROM payouts p
             JOIN users u ON u.id = p.user_id
             ORDER BY p.created_at DESC LIMIT ? OFFSET ?',
            [$limit, $offset]
        );
    }

    public static function create(array $data): int
    {
        $data['created_at'] = date('Y-m-d H:i:s');
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->insert('payouts', $data);
    }

    public static function approve(int $id, int $adminId): bool
    {
        return Database::getInstance()->update('payouts', [
            'status'      => 'approved',
            'approved_by' => $adminId,
            'updated_at'  => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }

    public static function reject(int $id, int $adminId, string $note): bool
    {
        return Database::getInstance()->update('payouts', [
            'status'      => 'rejected',
            'approved_by' => $adminId,
            'admin_note'  => $note,
            'updated_at'  => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }

    public static function complete(int $id): bool
    {
        return Database::getInstance()->update('payouts', [
            'status'     => 'completed',
            'updated_at' => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }

    public static function getTotalPending(): float
    {
        $row = Database::getInstance()->fetchOne(
            "SELECT COALESCE(SUM(amount_usd), 0) as total FROM payouts WHERE status IN ('pending','approved','processing')"
        );
        return (float)($row['total'] ?? 0);
    }
}
