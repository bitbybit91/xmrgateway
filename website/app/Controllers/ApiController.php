<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Core\Database;
use App\Models\{Investment, Transaction, User};
use App\Services\{AcceptXmrClient, PriceFeed};

class ApiController
{
    public function invoiceStatus(array $params = []): void
    {
        header('Content-Type: application/json');
        $invoiceId = $params['id'] ?? '';

        $client  = new AcceptXmrClient();
        $invoice = $client->getInvoice($invoiceId);
        $tx      = Transaction::findByInvoiceId($invoiceId);

        echo json_encode([
            'invoice'   => $invoice,
            'db_status' => $tx['status'] ?? null,
            'confirmed' => ($tx['status'] ?? '') === 'confirmed',
        ]);
    }

    public function prices(array $params = []): void
    {
        header('Content-Type: application/json');
        echo json_encode((new PriceFeed())->getPrices());
    }

    public function stats(array $params = []): void
    {
        header('Content-Type: application/json');
        $db       = Database::getInstance();
        $settings = [];
        foreach ($db->fetchAll('SELECT `key`, `value` FROM settings') as $row) {
            $settings[$row['key']] = $row['value'];
        }
        echo json_encode([
            'aum'         => $settings['aum_usd']          ?? '0',
            'strategies'  => $settings['total_strategies'] ?? '3',
            'investments' => $settings['total_investments'] ?? '0',
            'countries'   => $settings['total_countries']  ?? '0',
            'users'       => User::count(),
            'db_invested' => Investment::getTotalInvested(),
        ]);
    }

    public function health(array $params = []): void
    {
        header('Content-Type: application/json');
        echo json_encode(['status' => 'ok', 'time' => date('c')]);
    }
}
