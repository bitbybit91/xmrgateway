<?php

declare(strict_types=1);

namespace App\Middleware;

use App\Core\Session;

class AdminMiddleware
{
    public function __invoke(callable $next): void
    {
        if (!Session::isLoggedIn() || !Session::isAdmin()) {
            http_response_code(403);
            header('Content-Type: application/json');
            echo json_encode(['error' => 'Forbidden', 'code' => 403]);
            exit;
        }

        $next();
    }
}
