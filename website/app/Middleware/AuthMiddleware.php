<?php

declare(strict_types=1);

namespace App\Middleware;

use App\Core\Session;

class AuthMiddleware
{
    public function __invoke(callable $next): void
    {
        if (!Session::isLoggedIn()) {
            header('Location: ' . APP_URL . '/login');
            exit;
        }

        // Verify account is still active
        $user = Session::user();
        if (in_array($user['status'] ?? '', ['suspended', 'banned'], true)) {
            Session::logout();
            header('Location: ' . APP_URL . '/login?reason=suspended');
            exit;
        }

        $next();
    }
}
