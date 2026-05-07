<?php

declare(strict_types=1);

namespace App\Core;

use Twig\Environment;
use Twig\Loader\FilesystemLoader;
use Twig\TwigFilter;

/**
 * Twig template renderer.
 */
class View
{
    private Environment $twig;

    public function __construct()
    {
        $loader = new FilesystemLoader(BASE_PATH . '/views');

        $options = ['debug' => (APP_ENV !== 'production')];
        if (APP_ENV === 'production') {
            $cacheDir = CACHE_PATH . '/twig';
            if (!is_dir($cacheDir)) {
                mkdir($cacheDir, 0755, true);
            }
            $options['cache'] = $cacheDir;
        }

        $this->twig = new Environment($loader, $options);

        $this->addGlobals();
        $this->addFilters();
    }

    private function addGlobals(): void
    {
        $this->twig->addGlobal('app_name',     APP_NAME);
        $this->twig->addGlobal('app_url',      APP_URL);
        $this->twig->addGlobal('current_user', Session::user());
        $this->twig->addGlobal('csrf_token',   Csrf::field());
        $this->twig->addGlobal('flash_success', Session::getFlash('success'));
        $this->twig->addGlobal('flash_error',   Session::getFlash('error'));
        $this->twig->addGlobal('flash_info',    Session::getFlash('info'));
    }

    private function addFilters(): void
    {
        $this->twig->addFilter(new TwigFilter('format_usd', function (mixed $amount): string {
            return '$' . number_format((float)$amount, 2, '.', ',');
        }));

        $this->twig->addFilter(new TwigFilter('format_xmr', function (mixed $piconeros): string {
            return number_format((int)$piconeros / 1e12, 12, '.', '') . ' XMR';
        }));

        $this->twig->addFilter(new TwigFilter('time_ago', function (mixed $datetime): string {
            if (!$datetime) return 'Never';
            $ts   = is_numeric($datetime) ? (int)$datetime : strtotime((string)$datetime);
            $diff = time() - $ts;
            return match (true) {
                $diff < 60      => 'Just now',
                $diff < 3600    => floor($diff / 60) . ' min ago',
                $diff < 86400   => floor($diff / 3600) . ' hours ago',
                $diff < 604800  => floor($diff / 86400) . ' days ago',
                default         => date('M j, Y', $ts),
            };
        }));

        $this->twig->addFilter(new TwigFilter('short_address', function (string $addr): string {
            return strlen($addr) > 20
                ? substr($addr, 0, 8) . '...' . substr($addr, -8)
                : $addr;
        }));
    }

    public function render(string $template, array $data = []): string
    {
        return $this->twig->render($template, $data);
    }

    public function display(string $template, array $data = []): void
    {
        echo $this->render($template, $data);
    }
}
