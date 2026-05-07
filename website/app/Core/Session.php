<?php

declare(strict_types=1);

namespace App\Core;

/**
 * Session manager with secure defaults and flash message support.
 */
class Session
{
    private static bool $started = false;

    public static function start(): void
    {
        if (static::$started || session_status() === PHP_SESSION_ACTIVE) {
            static::$started = true;
            return;
        }

        session_set_cookie_params([
            'lifetime' => 0,
            'path'     => '/',
            'domain'   => '',
            'secure'   => (APP_ENV === 'production'),
            'httponly' => true,
            'samesite' => 'Strict',
        ]);

        session_name('ci_session');
        session_start();
        static::$started = true;
    }

    public static function set(string $key, mixed $value): void
    {
        static::start();
        $_SESSION[$key] = $value;
    }

    public static function get(string $key, mixed $default = null): mixed
    {
        static::start();
        return $_SESSION[$key] ?? $default;
    }

    public static function has(string $key): bool
    {
        static::start();
        return isset($_SESSION[$key]);
    }

    public static function remove(string $key): void
    {
        static::start();
        unset($_SESSION[$key]);
    }

    /** Store a flash value (read-once). */
    public static function flash(string $key, mixed $value): void
    {
        static::start();
        $_SESSION['_flash'][$key] = $value;
    }

    /** Read and delete a flash value. */
    public static function getFlash(string $key, mixed $default = null): mixed
    {
        static::start();
        $value = $_SESSION['_flash'][$key] ?? $default;
        unset($_SESSION['_flash'][$key]);
        return $value;
    }

    public static function userId(): ?int
    {
        $id = static::get('user_id');
        return $id !== null ? (int)$id : null;
    }

    public static function user(): ?array
    {
        return static::get('user');
    }

    public static function login(array $user): void
    {
        static::start();
        session_regenerate_id(true);
        $_SESSION['user_id'] = $user['id'];
        $_SESSION['user']    = $user;
    }

    public static function logout(): void
    {
        static::start();
        $_SESSION = [];
        if (ini_get('session.use_cookies')) {
            $params = session_get_cookie_params();
            setcookie(
                session_name(), '', time() - 42000,
                $params['path'], $params['domain'],
                $params['secure'], $params['httponly']
            );
        }
        session_destroy();
        static::$started = false;
    }

    public static function isLoggedIn(): bool
    {
        return static::has('user_id') && static::has('user');
    }

    public static function isAdmin(): bool
    {
        $user = static::user();
        return $user !== null && ($user['role'] ?? '') === 'admin';
    }
}
