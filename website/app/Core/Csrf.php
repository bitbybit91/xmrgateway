<?php

declare(strict_types=1);

namespace App\Core;

/**
 * CSRF token generation and validation.
 */
class Csrf
{
    private const SESSION_KEY = '_csrf_token';

    public static function getToken(): string
    {
        Session::start();
        if (!Session::has(self::SESSION_KEY)) {
            Session::set(self::SESSION_KEY, bin2hex(random_bytes(32)));
        }
        return Session::get(self::SESSION_KEY);
    }

    public static function validateToken(string $token): bool
    {
        $stored = Session::get(self::SESSION_KEY, '');
        return hash_equals($stored, $token);
    }

    public static function field(): string
    {
        $token = self::getToken();
        return '<input type="hidden" name="_csrf_token" value="' . htmlspecialchars($token, ENT_QUOTES) . '">';
    }

    /**
     * Validate CSRF on mutating requests (POST/PUT/DELETE).
     * Aborts with 403 if invalid.
     */
    public static function middleware(): void
    {
        $method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
        if (!in_array($method, ['POST', 'PUT', 'DELETE', 'PATCH'], true)) {
            return;
        }

        $token = $_POST['_csrf_token']
            ?? $_SERVER['HTTP_X_CSRF_TOKEN']
            ?? '';

        if (!self::validateToken($token)) {
            http_response_code(403);
            header('Content-Type: application/json');
            echo json_encode(['error' => 'Invalid CSRF token']);
            exit;
        }

        // Rotate token after successful validation
        Session::set(self::SESSION_KEY, bin2hex(random_bytes(32)));
    }
}
