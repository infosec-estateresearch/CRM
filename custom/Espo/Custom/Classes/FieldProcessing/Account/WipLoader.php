<?php

namespace Espo\Custom\Classes\FieldProcessing\Account;

use Espo\Core\Acl;
use Espo\Core\FieldProcessing\Loader;
use Espo\Core\FieldProcessing\Loader\Params;
use Espo\Core\Utils\Log;
use Espo\ORM\Entity;

/**
 * CRM-WIP-INT-001R2: read-only WIP panel on the Account. Nothing is stored.
 *
 * 1. No WipSummary grant: no field is set and no request is made.
 * 2. Granted but no valid sfId: a fixed status, no request.
 * 3. Otherwise one authenticated GET to the WIP read-only API. Every failure
 *    becomes a status; nothing is thrown to the page, and no log line holds the
 *    token, the URL, the sfId or the body.
 *
 * @implements Loader<Entity>
 */
class WipLoader implements Loader
{
    private const SCOPE = 'WipSummary';
    private const MAX_BODY = 262144;
    private const MAX_CASES = 50;
    private const MAX_TEXT = 255;

    private const S_OK = 'WIP data available';
    private const S_NONE = 'No current WIP cases';
    private const S_ABSENT = 'Firm not found in WIP';
    private const S_NO_SFID = 'No Salesforce ID on this Account';
    private const S_DOWN = 'WIP unavailable';

    private const TOP_KEYS = ['salesforceAccountId', 'companyName', 'truncated', 'cases'];
    private const CASE_KEYS = ['reference', 'name', 'type', 'status', 'openedAt', 'wip',
        'feesInvoiced', 'estimatedYield', 'actualYield', 'asOf'];

    public function __construct(private Acl $acl, private Log $log)
    {
    }

    public function process(Entity $entity, Params $params): void
    {
        try {
            if (!$this->acl->checkScope(self::SCOPE)) {
                return;
            }

            $sfId = $entity->get('sfId');

            if (!is_string($sfId) || preg_match('/^[A-Za-z0-9]{18}$/D', $sfId) !== 1) {
                $this->set($entity, self::S_NO_SFID, '');

                return;
            }

            [$status, $text] = $this->fetch($sfId);
            $this->set($entity, $status, $text);
        } catch (\Throwable $e) {
            $this->logFailure(get_class($e), null);
            $this->set($entity, self::S_DOWN, '');
        }
    }

    private function set(Entity $entity, string $status, string $cases): void
    {
        $entity->set('wipStatus', $status);
        $entity->set('wipCases', $cases);
    }

    private function logFailure(string $class, ?int $http): void
    {
        $this->log->warning('WIP loader: ' . $class . ($http === null ? '' : ' http=' . $http));
    }

    /** @return array{string, string} */
    private function fetch(string $sfId): array
    {
        $base = getenv('CRM_WIP_API_URL');
        $token = getenv('CRM_WIP_API_TOKEN');

        if (!is_string($base) || $base === '' || !is_string($token) || $token === '') {
            $this->logFailure('NotConfigured', null);

            return [self::S_DOWN, ''];
        }

        $url = $this->buildUrl($base, $sfId);

        if ($url === null) {
            $this->logFailure('BadConfiguredUrl', null);

            return [self::S_DOWN, ''];
        }

        [$http, $body, $error] = $this->request($url, $token);

        if ($error !== null) {
            $this->logFailure($error, null);

            return [self::S_DOWN, ''];
        }

        if ($http === 404) {
            return [self::S_ABSENT, ''];
        }

        if ($http !== 200) {
            $this->logFailure('HttpStatus', $http);

            return [self::S_DOWN, ''];
        }

        $result = $this->parse($body, $sfId);

        if ($result === null) {
            $this->logFailure('BadResponse', $http);

            return [self::S_DOWN, ''];
        }

        return $result;
    }

    private function buildUrl(string $base, string $sfId): ?string
    {
        $parts = parse_url($base);

        if (
            !is_array($parts) ||
            !in_array($parts['scheme'] ?? '', ['http', 'https'], true) ||
            ($parts['host'] ?? '') === '' ||
            isset($parts['user']) || isset($parts['pass']) ||
            isset($parts['query']) || isset($parts['fragment']) ||
            preg_match('/[\x00-\x20\x7f]/', $base) === 1
        ) {
            return null;
        }

        return rtrim($base, '/') . '/api/v1/accounts/' . $sfId . '/wip';
    }

    /** @return array{int, string, ?string} status, body, failure class */
    private function request(string $url, string $token): array
    {
        $ch = curl_init($url);

        if ($ch === false) {
            return [0, '', 'CurlInit'];
        }

        $body = '';
        $tooBig = false;

        curl_setopt_array($ch, [
            CURLOPT_HTTPGET => true,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $token, 'Accept: application/json'],
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_MAXREDIRS => 0,
            CURLOPT_PROTOCOLS => CURLPROTO_HTTP | CURLPROTO_HTTPS,
            CURLOPT_REDIR_PROTOCOLS => 0,
            CURLOPT_PROXY => '',
            CURLOPT_CONNECTTIMEOUT_MS => 2000,
            CURLOPT_TIMEOUT_MS => 3000,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
            CURLOPT_WRITEFUNCTION => function ($c, string $chunk) use (&$body, &$tooBig): int {
                if (strlen($body) + strlen($chunk) > self::MAX_BODY) {
                    $tooBig = true;

                    return -1;
                }

                $body .= $chunk;

                return strlen($chunk);
            },
        ]);

        $ok = curl_exec($ch);
        $http = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
        $errno = curl_errno($ch);
        curl_close($ch);

        if ($tooBig) {
            return [$http, '', 'BodyTooLarge'];
        }

        if ($ok === false || $errno !== 0) {
            return [$http, '', 'Transport' . ($errno === 28 ? 'Timeout' : '')];
        }

        return [$http, $body, null];
    }

    /** @return ?array{string, string} */
    private function parse(string $body, string $sfId): ?array
    {
        $data = json_decode($body, true, 8);

        if (!is_array($data) || array_is_list($data) || count($data) !== count(self::TOP_KEYS) ||
            array_diff(self::TOP_KEYS, array_keys($data)) !== []) {
            return null;
        }

        if ($data['salesforceAccountId'] !== $sfId || !$this->isText($data['companyName'], false) ||
            !is_bool($data['truncated']) || !is_array($data['cases']) ||
            !array_is_list($data['cases']) || count($data['cases']) > self::MAX_CASES) {
            return null;
        }

        $lines = [];

        foreach ($data['cases'] as $case) {
            $line = $this->caseLine($case);

            if ($line === null) {
                return null;
            }

            $lines[] = $line;
        }

        if ($lines === []) {
            return $data['truncated'] ? null : [self::S_NONE, ''];
        }

        if ($data['truncated']) {
            $lines[] = 'More current cases exist in WIP than are shown here.';
        }

        return [self::S_OK, implode("\n", $lines)];
    }

    private function caseLine(mixed $case): ?string
    {
        if (!is_array($case) || array_is_list($case) || count($case) !== count(self::CASE_KEYS) ||
            array_diff(self::CASE_KEYS, array_keys($case)) !== []) {
            return null;
        }

        if (!$this->isText($case['reference'], false)) {
            return null;
        }

        foreach (['name', 'type', 'status'] as $key) {
            if (!$this->isText($case[$key], true)) {
                return null;
            }
        }

        foreach (['openedAt', 'asOf'] as $key) {
            if ($case[$key] !== null &&
                (!is_string($case[$key]) || preg_match('/^\d{4}-\d{2}-\d{2}$/D', $case[$key]) !== 1)) {
                return null;
            }
        }

        foreach (['wip', 'feesInvoiced', 'estimatedYield', 'actualYield'] as $key) {
            if ($case[$key] !== null &&
                (!is_string($case[$key]) || preg_match('/^-?\d{1,15}(\.\d{1,4})?$/D', $case[$key]) !== 1)) {
                return null;
            }
        }

        $dash = "\u{2014}";
        $head = array_filter([
            $this->clean($case['reference']),
            $this->clean($case['name']),
            $this->clean($case['type']),
            $this->clean($case['status']),
            $case['openedAt'] === null ? '' : 'opened ' . $case['openedAt'],
        ], fn ($v) => $v !== '');

        return implode(' | ', [
            implode(' - ', $head),
            'WIP value ' . ($case['wip'] ?? $dash),
            'Fees invoiced ' . ($case['feesInvoiced'] ?? $dash),
            'Revised or actual yield (source value) ' . ($case['actualYield'] ?? $dash),
            'Estimated yield ' . ($case['estimatedYield'] ?? $dash),
            'as of ' . ($case['asOf'] ?? $dash),
        ]);
    }

    private function isText(mixed $value, bool $nullable): bool
    {
        if ($value === null) {
            return $nullable;
        }

        return is_string($value) && mb_check_encoding($value, 'UTF-8') &&
            mb_strlen($value, 'UTF-8') <= self::MAX_TEXT;
    }

    /** Plain text only: control characters become spaces (Espo escapes the rest). */
    private function clean(?string $value): string
    {
        return trim((string) preg_replace('/[\x00-\x1f\x7f]+/u', ' ', (string) $value));
    }
}
