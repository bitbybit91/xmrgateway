<?php

declare(strict_types=1);

namespace App\Services;

/**
 * HTTP client for the AcceptXMR payment gateway.
 * Internal API (port 8081): create/delete invoices, list IDs.
 * External API (port 8080): get invoice status (safe for end-user polling).
 */
class AcceptXmrClient
{
    private string $internalUrl;
    private string $externalUrl;
    private string $internalToken;
    private string $externalToken;

    public function __construct()
    {
        $this->internalUrl   = ACCEPTXMR_INTERNAL_URL;
        $this->externalUrl   = ACCEPTXMR_EXTERNAL_URL;
        $this->internalToken = ACCEPTXMR_INTERNAL_TOKEN;
        $this->externalToken = ACCEPTXMR_EXTERNAL_TOKEN;
    }

    /**
     * Create a new invoice on AcceptXMR.
     *
     * @param int    $picenorosRequired  Amount in piconeros (1 XMR = 1e12 piconeros)
     * @param int    $confirmationsRequired
     * @param int    $expirationSeconds  Seconds until invoice expires
     * @param string $callbackUrl        URL AcceptXMR will POST updates to
     * @param string $order              Free-form order metadata string
     * @return array{invoice_id: string}|false
     */
    public function createInvoice(
        int    $picenorosRequired,
        int    $confirmationsRequired,
        int    $expirationSeconds,
        string $callbackUrl,
        string $order
    ): array|false {
        return $this->request('POST', $this->internalUrl . '/invoice', [
            'piconeros_due'          => $picenorosRequired,
            'confirmations_required' => $confirmationsRequired,
            'expiration_in'          => $expirationSeconds,
            'callback'               => $callbackUrl,
            'order'                  => $order,
        ], $this->internalToken);
    }

    /**
     * Get invoice status from external API (safe for end users).
     */
    public function getInvoice(string $invoiceId): array|false
    {
        $url = $this->externalUrl . '/invoice?id=' . urlencode($invoiceId);
        return $this->request('GET', $url, [], $this->externalToken);
    }

    /**
     * Delete (stop tracking) an invoice via internal API.
     */
    public function deleteInvoice(string $invoiceId): bool
    {
        $url    = $this->internalUrl . '/invoice?id=' . urlencode($invoiceId);
        $result = $this->request('DELETE', $url, [], $this->internalToken);
        return $result !== false;
    }

    /**
     * Get all currently tracked invoice IDs.
     */
    public function getAllInvoiceIds(): array
    {
        $result = $this->request('GET', $this->internalUrl . '/invoice/ids', [], $this->internalToken);
        return is_array($result) ? $result : [];
    }

    /**
     * Simple health check — returns true if AcceptXMR external API is reachable.
     */
    public function healthCheck(): bool
    {
        $ch = curl_init($this->externalUrl . '/health');
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 5,
            CURLOPT_CONNECTTIMEOUT => 3,
        ]);
        curl_exec($ch);
        $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        return $code === 200;
    }

    // ── Private helpers ──────────────────────────────────────────────────────

    private function request(string $method, string $url, array $data = [], string $token = ''): array|false
    {
        $ch = curl_init($url);

        $headers = ['Content-Type: application/json', 'Accept: application/json'];
        if ($token !== '') {
            $headers[] = 'Authorization: Bearer ' . $token;
        }

        $options = [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_HTTPHEADER     => $headers,
            CURLOPT_CUSTOMREQUEST  => $method,
        ];

        if ($method === 'POST' && !empty($data)) {
            $options[CURLOPT_POSTFIELDS] = json_encode($data);
        }

        curl_setopt_array($ch, $options);

        $body  = curl_exec($ch);
        $code  = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $error = curl_error($ch);
        curl_close($ch);

        if ($body === false || $error) {
            error_log("[AcceptXmrClient] cURL error for $method $url: $error");
            return false;
        }

        if ($code < 200 || $code >= 300) {
            error_log("[AcceptXmrClient] HTTP $code for $method $url — body: $body");
            return false;
        }

        if ($body === '' || $body === 'null') {
            return [];
        }

        $decoded = json_decode($body, true);
        if ($decoded === null && json_last_error() !== JSON_ERROR_NONE) {
            error_log("[AcceptXmrClient] JSON decode error for $method $url: " . json_last_error_msg());
            return false;
        }

        return $decoded ?? [];
    }
}
