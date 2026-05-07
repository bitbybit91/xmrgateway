<?php
class AcceptXmrClient {
    private string $internalUrl;
    private string $externalUrl;
    private string $token;

    public function __construct(string $internalUrl, string $externalUrl, string $token = '') {
        $this->internalUrl = rtrim($internalUrl, '/');
        $this->externalUrl = rtrim($externalUrl, '/');
        $this->token = $token;
    }

    public function createInvoice(
        int $piconeros,
        int $confirmations,
        int $expiryMinutes,
        string $order,
        ?string $callback = null
    ): array {
        $body = [
            'piconeros_due'          => $piconeros,
            'confirmations_required' => $confirmations,
            'expiration_in'          => $expiryMinutes * 60,
            'order'                  => $order,
        ];
        if ($callback !== null) {
            $body['callback'] = $callback;
        }
        return $this->request('POST', $this->internalUrl . '/invoice', $body, true);
    }

    public function getInvoice(string $invoiceId): array {
        $url = $this->externalUrl . '/invoice?id=' . urlencode($invoiceId);
        return $this->request('GET', $url, null, false);
    }

    public function deleteInvoice(string $invoiceId): array {
        $url = $this->internalUrl . '/invoice?id=' . urlencode($invoiceId);
        return $this->request('DELETE', $url, null, true);
    }

    private function request(string $method, string $url, ?array $body, bool $useAuth): array {
        $ch = curl_init();
        $headers = ['Accept: application/json'];
        if ($useAuth && $this->token !== '') {
            $headers[] = 'Authorization: Bearer ' . $this->token;
        }

        curl_setopt_array($ch, [
            CURLOPT_URL            => $url,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT        => 15,
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_CUSTOMREQUEST  => $method,
        ]);

        if ($body !== null) {
            $json = json_encode($body);
            $headers[] = 'Content-Type: application/json';
            $headers[] = 'Content-Length: ' . strlen($json);
            curl_setopt($ch, CURLOPT_POSTFIELDS, $json);
        }

        curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curlError = curl_error($ch);
        curl_close($ch);

        if ($response === false) {
            throw new RuntimeException('AcceptXMR request failed: ' . $curlError);
        }
        if ($httpCode < 200 || $httpCode >= 300) {
            throw new RuntimeException('AcceptXMR returned HTTP ' . $httpCode . ': ' . $response);
        }

        if ($response === '' || $response === null) {
            return [];
        }

        $decoded = json_decode($response, true);
        if (json_last_error() !== JSON_ERROR_NONE) {
            throw new RuntimeException('AcceptXMR invalid JSON response: ' . json_last_error_msg());
        }
        return $decoded;
    }
}
