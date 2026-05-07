<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Core\{View, Session, Csrf, Database};
use App\Models\{User, Plan, Investment, Payout};
use App\Services\{AcceptXmrClient, Mailer};

class AdminController
{
    private function auditLog(string $action, string $entityType, int $entityId, array $old = [], array $new = []): void
    {
        Database::getInstance()->insert('audit_logs', [
            'user_id'     => Session::userId(),
            'action'      => $action,
            'entity_type' => $entityType,
            'entity_id'   => $entityId,
            'old_values'  => $old ? json_encode($old) : null,
            'new_values'  => $new ? json_encode($new) : null,
            'ip_address'  => $_SERVER['REMOTE_ADDR'] ?? null,
            'user_agent'  => $_SERVER['HTTP_USER_AGENT'] ?? null,
            'created_at'  => date('Y-m-d H:i:s'),
        ]);
    }

    public function index(array $params = []): void
    {
        $db              = Database::getInstance();
        $totalInvested   = Investment::getTotalInvested();
        $activeUsers     = (int)($db->fetchOne("SELECT COUNT(*) as c FROM users WHERE status='active'"   )['c'] ?? 0);
        $pendingPayouts  = Payout::getTotalPending();
        $recentLogs      = $db->fetchAll(
            'SELECT l.*, u.name as user_name FROM audit_logs l LEFT JOIN users u ON u.id = l.user_id ORDER BY l.created_at DESC LIMIT 20'
        );
        $pendingPayoutList = Payout::findPending();
        $xmrOnline         = (new AcceptXmrClient())->healthCheck();

        (new View())->display('admin/index.twig', compact(
            'totalInvested', 'activeUsers', 'pendingPayouts', 'recentLogs', 'pendingPayoutList', 'xmrOnline'
        ));
    }

    public function users(array $params = []): void
    {
        $page    = max(1, (int)($_GET['page'] ?? 1));
        $limit   = 30;
        $offset  = ($page - 1) * $limit;
        $db      = Database::getInstance();
        $status  = $_GET['status'] ?? '';
        $search  = trim($_GET['q'] ?? '');

        $sql    = 'SELECT * FROM users WHERE 1=1';
        $qParams = [];
        if ($status) { $sql .= ' AND status = ?'; $qParams[] = $status; }
        if ($search)  { $sql .= ' AND (name LIKE ? OR email LIKE ?)'; $qParams[] = "%$search%"; $qParams[] = "%$search%"; }
        $sql .= ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
        $qParams[] = $limit;
        $qParams[] = $offset;

        $users = $db->fetchAll($sql, $qParams);
        (new View())->display('admin/users.twig', compact('users', 'page', 'search', 'status'));
    }

    public function viewUser(array $params = []): void
    {
        $user        = User::findById((int)($params['id'] ?? 0));
        if (!$user) { http_response_code(404); echo '404'; return; }
        $investments = Investment::findByUser($user['id']);
        (new View())->display('admin/user_detail.twig', compact('user', 'investments'));
    }

    public function updateUser(array $params = []): void
    {
        Csrf::middleware();
        $userId = (int)($params['id'] ?? 0);
        $old    = User::findById($userId);
        $data   = [];
        if (isset($_POST['status'])) $data['status'] = $_POST['status'];
        if (isset($_POST['role']))   $data['role']   = $_POST['role'];

        if ($data && $old) {
            User::update($userId, $data);
            $this->auditLog('update_user', 'user', $userId, $old, $data);
        }

        header('Location: ' . APP_URL . '/admin/users'); exit;
    }

    public function investments(array $params = []): void
    {
        $status      = $_GET['status'] ?? '';
        $investments = Investment::findAll($status, 50, 0);
        (new View())->display('admin/investments.twig', compact('investments', 'status'));
    }

    public function plans(array $params = []): void
    {
        $plans = Plan::findAll(false);
        (new View())->display('admin/plans.twig', compact('plans'));
    }

    public function createPlan(array $params = []): void
    {
        Csrf::middleware();
        $data = [
            'name'             => htmlspecialchars(trim($_POST['name'] ?? '')),
            'slug'             => preg_replace('/[^a-z0-9_-]/', '', strtolower(trim($_POST['slug'] ?? ''))),
            'description'      => htmlspecialchars(trim($_POST['description'] ?? '')),
            'min_amount_usd'   => (float)($_POST['min_amount_usd'] ?? 100),
            'max_amount_usd'   => (float)($_POST['max_amount_usd'] ?? 1000000),
            'daily_roi_percent' => (float)($_POST['daily_roi_percent'] ?? 0.08),
            'duration_days'    => (int)($_POST['duration_days'] ?? 30),
            'type'             => $_POST['type'] ?? 'liquid_token',
            'is_active'        => 1,
        ];
        $id = Plan::create($data);
        $this->auditLog('create_plan', 'plan', $id, [], $data);
        Session::flash('success', 'Plan created successfully.');
        header('Location: ' . APP_URL . '/admin/plans'); exit;
    }

    public function updatePlan(array $params = []): void
    {
        Csrf::middleware();
        $planId = (int)($params['id'] ?? 0);
        $old    = Plan::findById($planId);
        $data   = [
            'name'              => htmlspecialchars(trim($_POST['name'] ?? '')),
            'description'       => htmlspecialchars(trim($_POST['description'] ?? '')),
            'min_amount_usd'    => (float)($_POST['min_amount_usd'] ?? 100),
            'max_amount_usd'    => (float)($_POST['max_amount_usd'] ?? 1000000),
            'daily_roi_percent' => (float)($_POST['daily_roi_percent'] ?? 0.08),
            'duration_days'     => (int)($_POST['duration_days'] ?? 30),
            'type'              => $_POST['type'] ?? 'liquid_token',
            'is_active'         => (int)($_POST['is_active'] ?? 1),
        ];
        Plan::update($planId, $data);
        $this->auditLog('update_plan', 'plan', $planId, $old ?? [], $data);
        Session::flash('success', 'Plan updated.');
        header('Location: ' . APP_URL . '/admin/plans'); exit;
    }

    public function deletePlan(array $params = []): void
    {
        Csrf::middleware();
        $planId = (int)($params['id'] ?? 0);
        Plan::delete($planId);
        $this->auditLog('delete_plan', 'plan', $planId);
        Session::flash('success', 'Plan deactivated.');
        header('Location: ' . APP_URL . '/admin/plans'); exit;
    }

    public function payouts(array $params = []): void
    {
        $payouts = Payout::findAll(50, 0);
        (new View())->display('admin/payouts.twig', compact('payouts'));
    }

    public function approvePayout(array $params = []): void
    {
        Csrf::middleware();
        $payoutId = (int)($params['id'] ?? 0);
        $payout   = Payout::findById($payoutId);
        if ($payout) {
            Payout::approve($payoutId, Session::userId());
            $user = User::findById($payout['user_id']);
            if ($user) (new Mailer())->sendWithdrawalApproved($user['email'], $user['name'], (float)$payout['amount_usd']);
            $this->auditLog('approve_payout', 'payout', $payoutId);
        }
        header('Location: ' . APP_URL . '/admin/payouts'); exit;
    }

    public function rejectPayout(array $params = []): void
    {
        Csrf::middleware();
        $payoutId = (int)($params['id'] ?? 0);
        $note     = htmlspecialchars(trim($_POST['note'] ?? 'No reason provided.'));
        $payout   = Payout::findById($payoutId);
        if ($payout) {
            Payout::reject($payoutId, Session::userId(), $note);
            $user = User::findById($payout['user_id']);
            if ($user) (new Mailer())->sendWithdrawalRejected($user['email'], $user['name'], (float)$payout['amount_usd'], $note);
            $this->auditLog('reject_payout', 'payout', $payoutId, [], ['note' => $note]);
        }
        header('Location: ' . APP_URL . '/admin/payouts'); exit;
    }

    public function settings(array $params = []): void
    {
        $db       = Database::getInstance();
        $settings = [];
        foreach ($db->fetchAll('SELECT `key`, `value` FROM settings') as $row) {
            $settings[$row['key']] = $row['value'];
        }
        (new View())->display('admin/settings.twig', compact('settings'));
    }

    public function updateSettings(array $params = []): void
    {
        Csrf::middleware();
        $db      = Database::getInstance();
        $allowed = ['site_name','site_tagline','contact_email','aum_usd','total_strategies',
                    'total_investments','total_countries','accent_color'];
        foreach ($allowed as $key) {
            if (isset($_POST[$key])) {
                $val = htmlspecialchars(trim($_POST[$key]));
                $db->execute(
                    'INSERT INTO settings (`key`,`value`) VALUES (?,?) ON DUPLICATE KEY UPDATE `value`=?',
                    [$key, $val, $val]
                );
            }
        }
        Session::flash('success', 'Settings saved.');
        header('Location: ' . APP_URL . '/admin/settings'); exit;
    }

    public function auditLogs(array $params = []): void
    {
        $page   = max(1, (int)($_GET['page'] ?? 1));
        $limit  = 50;
        $offset = ($page - 1) * $limit;
        $logs   = Database::getInstance()->fetchAll(
            'SELECT l.*, u.name as user_name FROM audit_logs l LEFT JOIN users u ON u.id = l.user_id ORDER BY l.created_at DESC LIMIT ? OFFSET ?',
            [$limit, $offset]
        );
        (new View())->display('admin/audit_logs.twig', compact('logs', 'page'));
    }

    public function exportNewsletter(array $params = []): void
    {
        $subs = Database::getInstance()->fetchAll(
            "SELECT email, name, status, created_at FROM newsletter_subscribers ORDER BY created_at DESC"
        );

        header('Content-Type: text/csv; charset=UTF-8');
        header('Content-Disposition: attachment; filename="newsletter_' . date('Y-m-d') . '.csv"');
        $out = fopen('php://output', 'w');
        fwrite($out, "\xEF\xBB\xBF"); // UTF-8 BOM
        fputcsv($out, ['Email', 'Name', 'Status', 'Subscribed At']);
        foreach ($subs as $sub) {
            fputcsv($out, [$sub['email'], $sub['name'], $sub['status'], $sub['created_at']]);
        }
        fclose($out);
        exit;
    }
}
