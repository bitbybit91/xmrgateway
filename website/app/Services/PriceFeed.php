<?php

declare(strict_types=1);

namespace App\Services;

/**
 * Live crypto price feed via CoinGecko public API.
 * Results are cached in storage/cache/prices.json for 60 seconds.
 */
class PriceFeed
{
    private string $cacheFile;
    private int    $cacheTtl = 60; // seconds

    public function __construct()
    {
        $this->cacheFile = CACHE_PATH . '/prices.json';
    }

    public function getXmrUsdPrice(): float
    {
        return $this->getPrices()['xmr'] ?? 150.0;
    }

    public function getBtcUsdPrice(): float
    {
        return $this->getPrices()['btc'] ?? 40000.0;
    }

    public function getEthUsdPrice(): float
    {
        return $this->getPrices()['eth'] ?? 2500.0;
    }

    public function getPrices(): array
    {
        // Check cache
        if (file_exists($this->cacheFile)) {
            $cached = json_decode(file_get_contents($this->cacheFile), true);
            if ($cached && isset($cached['_ts']) && (time() - $cached['_ts']) < $this->cacheTtl) {
                unset($cached['_ts']);
                return $cached;
            }
        }

        // Fetch from CoinGecko
        $url  = COINGECKO_API_URL . '/simple/price?ids=monero,bitcoin,ethereum&vs_currencies=usd';
        $data = $this->fetch($url);

        $prices = [
            'xmr' => (float)($data['monero']['usd']   ?? 150.0),
            'btc' => (float)($data['bitcoin']['usd']   ?? 40000.0),
            'eth' => (float)($data['ethereum']['usd']  ?? 2500.0),
        ];

        // Save to cache
        @file_put_contents($this->cacheFile, json_encode(['_ts' => time(), ...$prices]));

        return $prices;
    }

    /**
     * Convert USD amount to piconeros.
     * 1 XMR = 1,000,000,000,000 piconeros (1e12)
     */
    public function usdToXmrPiconeros(float $usd): int
    {
        $xmrPrice = $this->getXmrUsdPrice();
        if ($xmrPrice <= 0) return 0;
        $xmr = $usd / $xmrPrice;
        return (int)round($xmr * 1e12);
    }

    /**
     * Convert piconeros to USD.
     */
    public function piconerosToUsd(int $piconeros): float
    {
        return ($piconeros / 1e12) * $this->getXmrUsdPrice();
    }

    private function fetch(string $url): array
    {
        $ch = curl_init($url);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 10,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_USERAGENT      => 'CryptoInvestPlatform/1.0',
        ]);
        $body  = curl_exec($ch);
        $error = curl_error($ch);
        curl_close($ch);

        if ($body === false || $error) {
            error_log("[PriceFeed] cURL error: $error");
            return [];
        }

        return json_decode($body, true) ?? [];
    }
}
