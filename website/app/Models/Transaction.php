<?php

declare(strict_types=1);

namespace App\Models;

use App\Core\Database;

class Transaction
{
    // Allow static access shortcut
    public static function getInstance(): static
    {
        return new static();
    }

    public static function findById(int $id): ?array
    {
        $row = Database::getInstance()->fetchOne('SELECT * FROM transactions WHERE id = ?', [$id]);
        return $row ?: null;
    }

    public static function findByInvoiceId(string $invoiceId): ?array
    {
        $row = Database::getInstance()->fetchOne(
            'SELECT * FROM transactions WHERE acceptxmr_invoice_id = ?',
            [$invoiceId]
        );
        return $row ?: null;
    }

    public static function findByUser(int $userId, int $limit = 20): array
    {
        return Database::getInstance()->fetchAll(
            'SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
            [$userId, $limit]
        );
    }

    public static function findPending(): array
    {
        return Database::getInstance()->fetchAll(
            "SELECT * FROM transactions WHERE status = 'pending' AND type = 'deposit' AND acceptxmr_invoice_id IS NOT NULL"
        );
    }

    public static function create(array $data): int
    {
        $data['created_at'] = date('Y-m-d H:i:s');
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->insert('transactions', $data);
    }

    public static function update(int $id, array $data): bool
    {
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->update('transactions', $data, 'id = ?', [$id]) >= 0;
    }

    public function expire(int $id): bool
    {
        return Database::getInstance()->update('transactions', [
            'status'     => 'expired',
            'updated_at' => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }

    public static function confirm(int $id, int $confirmations): bool
    {
        return Database::getInstance()->update('transactions', [
            'status'        => 'confirmed',
            'confirmations' => $confirmations,
            'updated_at'    => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }

    public static function fail(int $id): bool
    {
        return Database::getInstance()->update('transactions', [
            'status'     => 'failed',
            'updated_at' => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) > 0;
    }
}
