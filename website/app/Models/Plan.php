<?php

declare(strict_types=1);

namespace App\Models;

use App\Core\Database;

class Plan
{
    public static function findAll(bool $activeOnly = true): array
    {
        $sql    = 'SELECT * FROM plans';
        $params = [];
        if ($activeOnly) {
            $sql .= ' WHERE is_active = 1';
        }
        $sql .= ' ORDER BY min_amount_usd ASC';
        return Database::getInstance()->fetchAll($sql, $params);
    }

    public static function findById(int $id): ?array
    {
        $row = Database::getInstance()->fetchOne('SELECT * FROM plans WHERE id = ?', [$id]);
        return $row ?: null;
    }

    public static function findBySlug(string $slug): ?array
    {
        $row = Database::getInstance()->fetchOne('SELECT * FROM plans WHERE slug = ?', [$slug]);
        return $row ?: null;
    }

    public static function create(array $data): int
    {
        $data['created_at'] = date('Y-m-d H:i:s');
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->insert('plans', $data);
    }

    public static function update(int $id, array $data): bool
    {
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->update('plans', $data, 'id = ?', [$id]) >= 0;
    }

    public static function delete(int $id): bool
    {
        // Soft-delete
        return Database::getInstance()->update('plans', [
            'is_active'  => 0,
            'updated_at' => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }
}
