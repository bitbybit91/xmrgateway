<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Core\{View, Database, Session};
use App\Models\Plan;

class HomeController
{
    public function index(array $params = []): void
    {
        $db       = Database::getInstance();
        $settings = [];
        foreach ($db->fetchAll('SELECT `key`, `value` FROM settings') as $row) {
            $settings[$row['key']] = $row['value'];
        }

        $plans = Plan::findAll(true);
        $stats = [
            'aum'         => $settings['aum_usd']           ?? '2500000000',
            'strategies'  => $settings['total_strategies']  ?? count($plans),
            'investments' => $settings['total_investments']  ?? '350',
            'countries'   => $settings['total_countries']    ?? '35',
            'years'       => (int)date('Y') - 2013,
        ];

        (new View())->display('home.twig', compact('settings', 'plans', 'stats'));
    }

    public function funds(array $params = []): void
    {
        $plans = Plan::findAll(true);
        (new View())->display('funds.twig', compact('plans'));
    }

    public function portfolio(array $params = []): void
    {
        (new View())->display('portfolio.twig');
    }

    public function insights(array $params = []): void
    {
        (new View())->display('insights.twig');
    }

    public function about(array $params = []): void
    {
        (new View())->display('about.twig');
    }

    public function subscribe(array $params = []): void
    {
        header('Content-Type: application/json');
        $email = trim($_POST['email'] ?? '');
        $name  = trim($_POST['name']  ?? '');

        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            echo json_encode(['success' => false, 'message' => 'Invalid email address.']);
            exit;
        }

        $db  = Database::getInstance();
        $existing = $db->fetchOne('SELECT id, status FROM newsletter_subscribers WHERE email = ?', [$email]);

        if ($existing) {
            if ($existing['status'] === 'unsubscribed') {
                $db->update('newsletter_subscribers', ['status' => 'active', 'name' => $name], 'id = ?', [$existing['id']]);
            }
            echo json_encode(['success' => true, 'message' => 'You are already subscribed!']);
            exit;
        }

        $db->insert('newsletter_subscribers', [
            'email'      => $email,
            'name'       => $name,
            'status'     => 'active',
            'token'      => bin2hex(random_bytes(16)),
            'created_at' => date('Y-m-d H:i:s'),
            'updated_at' => date('Y-m-d H:i:s'),
        ]);

        echo json_encode(['success' => true, 'message' => 'Successfully subscribed!']);
    }
}
