<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';

auth_start_session();
$user = auth_require();

$investments = [];

try {
    $pdo  = DB::get();
    $stmt = $pdo->prepare(
        'SELECT i.id, i.amount_xmr, i.status, i.confirmations, i.created_at, i.confirmed_at,
                f.name AS fund_name, f.slug AS fund_slug, f.apy_target,
                i.acceptxmr_invoice_id
         FROM investments i
         JOIN funds f ON f.id = i.fund_id
         WHERE i.user_id = :uid
         ORDER BY i.created_at DESC'
    );
    $stmt->execute([':uid' => $user['user_id']]);
    $investments = $stmt->fetchAll();
} catch (PDOException $e) {
    // Show empty state
}

$status_badges = [
    'pending'   => ['class' => 'badge-pending',   'label' => 'Pending'],
    'confirmed' => ['class' => 'badge-confirmed', 'label' => 'Confirmed'],
    'expired'   => ['class' => 'badge-expired',   'label' => 'Expired'],
    'cancelled' => ['class' => 'badge-cancelled', 'label' => 'Cancelled'],
];

$page_title = 'Dashboard';
require_once dirname(__DIR__) . '/includes/header.php';
?>

<section class="page-hero page-hero-sm">
    <div class="container">
        <span class="section-label">Your Account</span>
        <h1>Welcome, <?= htmlspecialchars($user['full_name'], ENT_QUOTES, 'UTF-8') ?></h1>
        <p>Manage your investments and track payment status.</p>
    </div>
</section>

<section class="section-dark">
    <div class="container">

        <div class="dashboard-header">
            <h2>Your Investments</h2>
            <a href="/funds.php" class="btn-primary btn-sm">+ Start New Investment</a>
        </div>

        <?php if (empty($investments)): ?>
            <div class="empty-state card">
                <p class="empty-icon">&#128200;</p>
                <h3>No investments yet</h3>
                <p>You haven't made any investments yet. Browse our funds to get started.</p>
                <a href="/funds.php" class="btn-primary">View Funds</a>
            </div>
        <?php else: ?>
            <div class="table-wrap">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Fund</th>
                            <th>Amount (XMR)</th>
                            <th>Status</th>
                            <th>Confirmations</th>
                            <th>Date</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <?php foreach ($investments as $inv): ?>
                            <?php $badge = $status_badges[$inv['status']] ?? ['class' => 'badge-pending', 'label' => ucfirst($inv['status'])]; ?>
                            <tr>
                                <td><?= (int)$inv['id'] ?></td>
                                <td>
                                    <strong><?= htmlspecialchars($inv['fund_name'], ENT_QUOTES, 'UTF-8') ?></strong>
                                    <small class="text-muted"><?= htmlspecialchars(number_format((float)$inv['apy_target'], 2), ENT_QUOTES, 'UTF-8') ?>% APY target</small>
                                </td>
                                <td class="gold"><?= htmlspecialchars(rtrim(rtrim(number_format((float)$inv['amount_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?></td>
                                <td><span class="badge <?= htmlspecialchars($badge['class'], ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars($badge['label'], ENT_QUOTES, 'UTF-8') ?></span></td>
                                <td><?= (int)$inv['confirmations'] ?> / <?= XMR_CONFIRMATIONS_REQUIRED ?></td>
                                <td>
                                    <?= htmlspecialchars(date('M j, Y', strtotime($inv['created_at'])), ENT_QUOTES, 'UTF-8') ?>
                                    <?php if ($inv['confirmed_at']): ?>
                                        <br><small class="text-muted">Confirmed <?= htmlspecialchars(date('M j, Y', strtotime($inv['confirmed_at'])), ENT_QUOTES, 'UTF-8') ?></small>
                                    <?php endif; ?>
                                </td>
                                <td>
                                    <?php if ($inv['status'] === 'pending'): ?>
                                        <a href="/confirm.php?inv=<?= urlencode($inv['acceptxmr_invoice_id']) ?>" class="btn-secondary btn-xs">View Payment</a>
                                    <?php else: ?>
                                        <span class="text-muted">—</span>
                                    <?php endif; ?>
                                </td>
                            </tr>
                        <?php endforeach; ?>
                    </tbody>
                </table>
            </div>
        <?php endif; ?>

        <div class="dashboard-account card" style="margin-top:2rem">
            <h3>Account Details</h3>
            <table class="info-table">
                <tr><td>Email</td><td><?= htmlspecialchars($user['email'], ENT_QUOTES, 'UTF-8') ?></td></tr>
                <tr><td>Full Name</td><td><?= htmlspecialchars($user['full_name'], ENT_QUOTES, 'UTF-8') ?></td></tr>
                <tr><td>KYC Status</td><td><span class="badge badge-<?= htmlspecialchars($user['kyc_status'], ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(ucfirst($user['kyc_status']), ENT_QUOTES, 'UTF-8') ?></span></td></tr>
            </table>
        </div>
    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
