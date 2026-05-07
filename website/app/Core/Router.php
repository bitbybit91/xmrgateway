<?php

declare(strict_types=1);

namespace App\Core;

/**
 * Simple HTTP router with named-parameter support.
 * Supports handler formats:
 *   - 'ControllerClass@method'
 *   - [ControllerClass::class, 'method']
 */
class Router
{
    /** @var array<array{method:string,pattern:string,handler:mixed,middleware:array}> */
    private array $routes = [];

    public function get(string $pattern, mixed $handler, array $middleware = []): void
    {
        $this->addRoute('GET', $pattern, $handler, $middleware);
    }

    public function post(string $pattern, mixed $handler, array $middleware = []): void
    {
        $this->addRoute('POST', $pattern, $handler, $middleware);
    }

    public function put(string $pattern, mixed $handler, array $middleware = []): void
    {
        $this->addRoute('PUT', $pattern, $handler, $middleware);
    }

    public function delete(string $pattern, mixed $handler, array $middleware = []): void
    {
        $this->addRoute('DELETE', $pattern, $handler, $middleware);
    }

    private function addRoute(string $method, string $pattern, mixed $handler, array $middleware): void
    {
        $this->routes[] = compact('method', 'pattern', 'handler', 'middleware');
    }

    public function dispatch(): void
    {
        $method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
        $uri    = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH) ?? '/';
        $uri    = '/' . trim($uri, '/');
        if ($uri === '') $uri = '/';

        foreach ($this->routes as $route) {
            if ($route['method'] !== $method) {
                continue;
            }

            $params = [];
            $regex  = $this->patternToRegex($route['pattern']);
            if (!preg_match($regex, $uri, $matches)) {
                continue;
            }

            // Collect named captures
            foreach ($matches as $key => $value) {
                if (is_string($key)) {
                    $params[$key] = $value;
                }
            }

            // Build middleware + handler chain
            $handler = $this->resolveHandler($route['handler'], $params);
            $chain   = $handler;

            foreach (array_reverse($route['middleware']) as $mw) {
                $next  = $chain;
                $mwObj = new $mw();
                $chain = fn() => $mwObj($next);
            }

            $chain();
            return;
        }

        // 404
        http_response_code(404);
        header('Content-Type: application/json');
        echo json_encode(['error' => 'Not Found', 'code' => 404]);
    }

    private function patternToRegex(string $pattern): string
    {
        $regex = preg_replace('/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/', '(?P<$1>[^/]+)', $pattern);
        return '#^' . $regex . '$#';
    }

    private function resolveHandler(mixed $handler, array $params): callable
    {
        if (is_callable($handler)) {
            return fn() => $handler($params);
        }

        [$class, $method] = match (true) {
            is_array($handler) => $handler,
            is_string($handler) && str_contains($handler, '@') => explode('@', $handler, 2),
            default => throw new \InvalidArgumentException("Invalid route handler: " . print_r($handler, true)),
        };

        // Resolve short class names into full namespace
        if (!str_contains($class, '\\')) {
            $class = 'App\\Controllers\\' . $class;
        }

        $controller = new $class();
        return fn() => $controller->$method($params);
    }
}
