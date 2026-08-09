<?php
/**
 * webapp/api/prices.php
 *
 * Thin proxy to CoinGecko free API.
 * Returns { "xmr": <float>, "btc": <float> } in JSON.
 * Caches result for 60 seconds in a temp file to respect rate limits.
 */
header('Content-Type: application/json');
header('Cache-Control: no-store');
header('Access-Control-Allow-Origin: *');

$cacheFile = sys_get_temp_dir() . '/xmrgateway_prices.json';
$cacheTtl  = 60; // seconds

// Serve from cache if fresh
if (file_exists($cacheFile) && (time() - filemtime($cacheFile)) < $cacheTtl) {
    echo file_get_contents($cacheFile);
    exit;
}

// Fetch from CoinGecko
$url = 'https://api.coingecko.com/api/v3/simple/price?ids=monero,bitcoin&vs_currencies=usd';

$ctx = stream_context_create([
    'http' => [
        'timeout'       => 5,
        'ignore_errors' => true,
        'header'        => "Accept: application/json\r\nUser-Agent: xmrgateway/1.0\r\n",
    ],
]);

$raw  = @file_get_contents($url, false, $ctx);
$data = $raw ? json_decode($raw, true) : null;

if (
    $data &&
    isset($data['monero']['usd']) &&
    isset($data['bitcoin']['usd'])
) {
    $result = json_encode([
        'xmr'        => (float) $data['monero']['usd'],
        'btc'        => (float) $data['bitcoin']['usd'],
        'fetched_at' => time(),
        'source'     => 'CoinGecko',
    ]);
    file_put_contents($cacheFile, $result);
    echo $result;
} else {
    // Return cached stale data if available, otherwise error
    if (file_exists($cacheFile)) {
        echo file_get_contents($cacheFile);
    } else {
        http_response_code(503);
        echo json_encode(['error' => 'Price data unavailable. Try again shortly.']);
    }
}
