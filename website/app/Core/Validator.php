<?php

declare(strict_types=1);

namespace App\Core;

/**
 * Input validator.
 */
class Validator
{
    private Database $db;

    public function __construct()
    {
        $this->db = Database::getInstance();
    }

    /**
     * Validate $data against $rules.
     * Rules are pipe-separated: 'required|email|min:6|max:100'
     *
     * @return array{valid: bool, errors: array<string,string>}
     */
    public function validate(array $data, array $rules): array
    {
        $errors = [];

        foreach ($rules as $field => $ruleString) {
            $ruleList = explode('|', $ruleString);
            $value    = $data[$field] ?? null;

            foreach ($ruleList as $rule) {
                [$ruleName, $ruleParam] = array_pad(explode(':', $rule, 2), 2, null);

                $error = match ($ruleName) {
                    'required'     => $this->ruleRequired($value),
                    'email'        => $this->ruleEmail($value),
                    'min'          => $this->ruleMin($value, (int)$ruleParam),
                    'max'          => $this->ruleMax($value, (int)$ruleParam),
                    'numeric'      => $this->ruleNumeric($value),
                    'integer'      => $this->ruleInteger($value),
                    'alpha'        => $this->ruleAlpha($value),
                    'alphanumeric' => $this->ruleAlphanumeric($value),
                    'confirmed'    => $this->ruleConfirmed($data, $field),
                    'regex'        => $this->ruleRegex($value, (string)$ruleParam),
                    'in'           => $this->ruleIn($value, $ruleParam ?? ''),
                    'unique'       => $this->ruleUnique($value, $ruleParam ?? '', $data['id'] ?? null),
                    'exists'       => $this->ruleExists($value, $ruleParam ?? ''),
                    default        => null,
                };

                if ($error !== null) {
                    $errors[$field] = $this->humanLabel($field) . ' ' . $error;
                    break; // First error per field
                }
            }
        }

        return ['valid' => empty($errors), 'errors' => $errors];
    }

    /** Trim + htmlspecialchars all string values. */
    public function sanitize(array $data): array
    {
        return array_map(
            fn($v) => is_string($v) ? htmlspecialchars(trim($v), ENT_QUOTES, 'UTF-8') : $v,
            $data
        );
    }

    // ── Rule implementations ─────────────────────────────────────────────────

    private function ruleRequired(mixed $v): ?string
    {
        return ($v === null || $v === '') ? 'is required.' : null;
    }

    private function ruleEmail(mixed $v): ?string
    {
        if ($v === null || $v === '') return null;
        return filter_var($v, FILTER_VALIDATE_EMAIL) ? null : 'must be a valid email address.';
    }

    private function ruleMin(mixed $v, int $min): ?string
    {
        if ($v === null || $v === '') return null;
        if (is_numeric($v)) return ((float)$v >= $min) ? null : "must be at least $min.";
        return (mb_strlen((string)$v) >= $min) ? null : "must be at least $min characters.";
    }

    private function ruleMax(mixed $v, int $max): ?string
    {
        if ($v === null || $v === '') return null;
        if (is_numeric($v)) return ((float)$v <= $max) ? null : "must be at most $max.";
        return (mb_strlen((string)$v) <= $max) ? null : "must be at most $max characters.";
    }

    private function ruleNumeric(mixed $v): ?string
    {
        if ($v === null || $v === '') return null;
        return is_numeric($v) ? null : 'must be a number.';
    }

    private function ruleInteger(mixed $v): ?string
    {
        if ($v === null || $v === '') return null;
        return filter_var($v, FILTER_VALIDATE_INT) !== false ? null : 'must be an integer.';
    }

    private function ruleAlpha(mixed $v): ?string
    {
        if ($v === null || $v === '') return null;
        return ctype_alpha((string)$v) ? null : 'must contain only letters.';
    }

    private function ruleAlphanumeric(mixed $v): ?string
    {
        if ($v === null || $v === '') return null;
        return ctype_alnum((string)$v) ? null : 'must contain only letters and numbers.';
    }

    private function ruleConfirmed(array $data, string $field): ?string
    {
        $v = $data[$field] ?? '';
        $c = $data[$field . '_confirmation'] ?? '';
        return $v === $c ? null : 'confirmation does not match.';
    }

    private function ruleRegex(mixed $v, string $pattern): ?string
    {
        if ($v === null || $v === '') return null;
        return preg_match($pattern, (string)$v) ? null : 'format is invalid.';
    }

    private function ruleIn(mixed $v, string $list): ?string
    {
        if ($v === null || $v === '') return null;
        $allowed = array_map('trim', explode(',', $list));
        return in_array($v, $allowed, true) ? null : 'is not a valid option.';
    }

    private function ruleUnique(mixed $v, string $param, mixed $exceptId): ?string
    {
        if ($v === null || $v === '') return null;
        [$table, $column] = array_pad(explode(',', $param), 2, 'id');
        $sql    = "SELECT COUNT(*) FROM `$table` WHERE `$column` = ?";
        $params = [$v];
        if ($exceptId) {
            $sql    .= ' AND id != ?';
            $params[] = $exceptId;
        }
        $count = (int)$this->db->fetchOne($sql, $params)[0];
        return $count === 0 ? null : 'is already taken.';
    }

    private function ruleExists(mixed $v, string $param): ?string
    {
        if ($v === null || $v === '') return null;
        [$table, $column] = array_pad(explode(',', $param), 2, 'id');
        $count = (int)$this->db->fetchOne("SELECT COUNT(*) FROM `$table` WHERE `$column` = ?", [$v])[0];
        return $count > 0 ? null : 'does not exist.';
    }

    private function humanLabel(string $field): string
    {
        return ucwords(str_replace(['_', '-'], ' ', $field));
    }
}
