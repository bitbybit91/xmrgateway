<?php

declare(strict_types=1);

namespace App\Models;

use App\Core\Database;

class User
{
    public static function findById(int $id): ?array
    {
        $row = Database::getInstance()->fetchOne('SELECT * FROM users WHERE id = ?', [$id]);
        return $row ?: null;
    }

    public static function findByEmail(string $email): ?array
    {
        $row = Database::getInstance()->fetchOne('SELECT * FROM users WHERE email = ?', [$email]);
        return $row ?: null;
    }

    public static function findAll(int $limit = 50, int $offset = 0): array
    {
        return Database::getInstance()->fetchAll(
            'SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?',
            [$limit, $offset]
        );
    }

    public static function create(array $data): int
    {
        if (isset($data['password'])) {
            $data['password_hash'] = password_hash($data['password'], PASSWORD_BCRYPT, ['cost' => 12]);
            unset($data['password'], $data['password_confirmation']);
        }
        $data['referral_code'] = $data['referral_code'] ?? self::generateReferralCode();
        $data['created_at']    = date('Y-m-d H:i:s');
        $data['updated_at']    = date('Y-m-d H:i:s');
        return Database::getInstance()->insert('users', $data);
    }

    public static function update(int $id, array $data): bool
    {
        unset($data['password'], $data['password_hash']);
        $data['updated_at'] = date('Y-m-d H:i:s');
        return Database::getInstance()->update('users', $data, 'id = ?', [$id]) >= 0;
    }

    public static function updatePassword(int $id, string $newPassword): bool
    {
        $hash = password_hash($newPassword, PASSWORD_BCRYPT, ['cost' => 12]);
        return Database::getInstance()->update('users', [
            'password_hash'          => $hash,
            'password_reset_token'   => null,
            'password_reset_expires' => null,
            'updated_at'             => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]) >= 0;
    }

    public static function delete(int $id): bool
    {
        return Database::getInstance()->delete('users', 'id = ?', [$id]) > 0;
    }

    public static function verifyEmail(string $token): bool
    {
        $db   = Database::getInstance();
        $user = $db->fetchOne('SELECT id FROM users WHERE email_verification_token = ?', [$token]);
        if (!$user) return false;
        return $db->update('users', [
            'email_verified_at'        => date('Y-m-d H:i:s'),
            'email_verification_token' => null,
            'status'                   => 'active',
            'updated_at'               => date('Y-m-d H:i:s'),
        ], 'id = ?', [$user['id']]) > 0;
    }

    public static function generatePasswordReset(int $id): string
    {
        $token   = bin2hex(random_bytes(32));
        $expires = date('Y-m-d H:i:s', strtotime('+1 hour'));
        Database::getInstance()->update('users', [
            'password_reset_token'   => $token,
            'password_reset_expires' => $expires,
            'updated_at'             => date('Y-m-d H:i:s'),
        ], 'id = ?', [$id]);
        return $token;
    }

    public static function count(): int
    {
        $row = Database::getInstance()->fetchOne('SELECT COUNT(*) as cnt FROM users');
        return (int)($row['cnt'] ?? 0);
    }

    /**
     * Returns the user's spendable balance: sum of confirmed ROI
     * minus approved/completed withdrawals.
     */
    public static function getBalance(int $userId): float
    {
        $db = Database::getInstance();

        $roiRow = $db->fetchOne(
            "SELECT COALESCE(SUM(amount_usd), 0) as total
             FROM transactions
             WHERE user_id = ? AND type = 'roi' AND status = 'confirmed'",
            [$userId]
        );

        $withdrawRow = $db->fetchOne(
            "SELECT COALESCE(SUM(amount_usd), 0) as total
             FROM payouts
             WHERE user_id = ? AND status IN ('approved','processing','completed')",
            [$userId]
        );

        return max(0, (float)($roiRow['total'] ?? 0) - (float)($withdrawRow['total'] ?? 0));
    }

    public static function generateReferralCode(): string
    {
        do {
            $code = strtoupper(substr(bin2hex(random_bytes(4)), 0, 8));
            $exists = Database::getInstance()->fetchOne('SELECT id FROM users WHERE referral_code = ?', [$code]);
        } while ($exists);
        return $code;
    }
}
