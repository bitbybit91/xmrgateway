<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';
require_once dirname(__DIR__) . '/includes/csrf.php';

auth_start_session();
$user = auth_require();

$error   = '';
$fund    = null;
$slug    = trim($_GET['fund'] ?? '');

if ($slug !== '') {
    try {
        $pdo  = DB::get();
        $stmt = $pdo->prepare('SELECT * FROM funds WHERE slug = :slug AND active = 1 LIMIT 1');
        $stmt->execute([':slug' => $slug]);
        $fund = $stmt->fetch();
    } catch (PDOException $e) {
        $error = 'Unable to load fund details. Please try again.';
    }
} else {
    // Show fund selection
    try {
        $pdo  = DB::get();
        $stmt = $pdo->prepare('SELECT * FROM funds WHERE active = 1 ORDER BY tier ASC');
        $stmt->execute();
        $all_funds = $stmt->fetchAll();
    } catch (PDOException $e) {
        $all_funds = [];
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $fund !== null) {
    csrf_verify();

    $amount_xmr = trim($_POST['amount_xmr'] ?? '');

    if (!is_numeric($amount_xmr) || (float)$amount_xmr <= 0) {
        $error = 'Please enter a valid XMR amount.';
    } elseif ((float)$amount_xmr < (float)$fund['min_investment_xmr']) {
        $error = 'Minimum investment for this fund is ' . rtrim(rtrim(number_format((float)$fund['min_investment_xmr'], 12), '0'), '.') . ' XMR.';
    } else {
        try {
            require_once dirname(__DIR__) . '/includes/acceptxmr_client.php';
            $pdo    = DB::get();
            $client = new AcceptXmrClient(ACCEPTXMR_INTERNAL_URL, ACCEPTXMR_EXTERNAL_URL, ACCEPTXMR_TOKEN);

            $piconeros    = (int)bcmul(sprintf('%.12f', (float)$amount_xmr), '1000000000000', 0);
            $order_ref    = 'user_' . $user['user_id'] . '_fund_' . $fund['id'] . '_' . time();
            $callback_url = SITE_URL . '/scripts/poll_payments.php';

            $result = $client->createInvoice(
                $piconeros,
                XMR_CONFIRMATIONS_REQUIRED,
                INVOICE_EXPIRY_MINUTES,
                $order_ref,
                null
            );

            if (empty($result['invoice_id'])) {
                throw new RuntimeException('No invoice_id in AcceptXMR response.');
            }

            $invoice_id = $result['invoice_id'];

            $stmt = $pdo->prepare(
                'INSERT INTO investments
                    (user_id, fund_id, amount_xmr, acceptxmr_invoice_id, status)
                 VALUES (:user_id, :fund_id, :amount_xmr, :invoice_id, \'pending\')'
            );
            $stmt->execute([
                ':user_id'    => $user['user_id'],
                ':fund_id'    => $fund['id'],
                ':amount_xmr' => $amount_xmr,
                ':invoice_id' => $invoice_id,
            ]);

            header('Location: /confirm.php?inv=' . urlencode($invoice_id));
            exit;

        } catch (RuntimeException $e) {
            $error = 'Payment system error. Please try again. (' . htmlspecialchars($e->getMessage(), ENT_QUOTES, 'UTF-8') . ')';
        } catch (PDOException $e) {
            $error = 'Database error. Please try again.';
        }
    }
}

$page_title = $fund ? 'Invest in ' . $fund['name'] : 'Invest';
require_once dirname(__DIR__) . '/includes/header.php';
?>

<section class="page-hero page-hero-sm">
    <div class="container">
        <span class="section-label">Get Started</span>
        <h1><?= htmlspecialchars($page_title, ENT_QUOTES, 'UTF-8') ?></h1>
    </div>
</section>

<section class="section-dark">
    <div class="container container-narrow">

        <?php if ($error): ?>
            <div class="alert alert-error"><?= htmlspecialchars($error, ENT_QUOTES, 'UTF-8') ?></div>
        <?php endif; ?>

        <?php if ($fund === null && empty($slug)): ?>
            <h2>Select a Fund</h2>
            <p class="section-subtitle">Choose an investment strategy to continue.</p>
            <div class="fund-cards">
                <?php foreach (($all_funds ?? []) as $f): ?>
                    <div class="fund-card">
                        <h3><?= htmlspecialchars($f['name'], ENT_QUOTES, 'UTF-8') ?></h3>
                        <p><?= htmlspecialchars(mb_substr($f['description'], 0, 120), ENT_QUOTES, 'UTF-8') ?>…</p>
                        <p><strong>Min:</strong> <?= htmlspecialchars(rtrim(rtrim(number_format((float)$f['min_investment_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?> XMR &nbsp;|&nbsp; <strong>Target APY:</strong> <?= htmlspecialchars(number_format((float)$f['apy_target'], 2), ENT_QUOTES, 'UTF-8') ?>%</p>
                        <a href="/invest.php?fund=<?= urlencode($f['slug']) ?>" class="btn-primary btn-sm">Select Fund</a>
                    </div>
                <?php endforeach; ?>
            </div>

        <?php elseif ($fund === null): ?>
            <div class="alert alert-error">Fund not found or not active. <a href="/funds.php">View all funds</a></div>

        <?php else: ?>
            <div class="invest-layout">
                <div class="invest-fund-info card">
                    <h2><?= htmlspecialchars($fund['name'], ENT_QUOTES, 'UTF-8') ?></h2>
                    <p><?= htmlspecialchars($fund['description'], ENT_QUOTES, 'UTF-8') ?></p>
                    <table class="info-table">
                        <tr>
                            <td>Minimum Investment</td>
                            <td class="gold"><?= htmlspecialchars(rtrim(rtrim(number_format((float)$fund['min_investment_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?> XMR</td>
                        </tr>
                        <tr>
                            <td>Target APY</td>
                            <td class="gold"><?= htmlspecialchars(number_format((float)$fund['apy_target'], 2), ENT_QUOTES, 'UTF-8') ?>%</td>
                        </tr>
                        <tr>
                            <td>Payment Method</td>
                            <td>Monero (XMR)</td>
                        </tr>
                        <tr>
                            <td>Confirmations Required</td>
                            <td><?= XMR_CONFIRMATIONS_REQUIRED ?></td>
                        </tr>
                        <tr>
                            <td>Invoice Expiry</td>
                            <td><?= INVOICE_EXPIRY_MINUTES ?> minutes</td>
                        </tr>
                    </table>
                </div>

                <div class="invest-form-wrap card">
                    <h3>Create Investment</h3>
                    <form method="POST" action="/invest.php?fund=<?= urlencode($fund['slug']) ?>" class="invest-form">
                        <?= csrf_field() ?>
                        <div class="form-group">
                            <label for="amount_xmr">Investment Amount (XMR)</label>
                            <input
                                type="number"
                                id="amount_xmr"
                                name="amount_xmr"
                                step="0.000000000001"
                                min="<?= htmlspecialchars($fund['min_investment_xmr'], ENT_QUOTES, 'UTF-8') ?>"
                                placeholder="e.g. <?= htmlspecialchars(rtrim(rtrim(number_format((float)$fund['min_investment_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?>"
                                value="<?= htmlspecialchars($_POST['amount_xmr'] ?? '', ENT_QUOTES, 'UTF-8') ?>"
                                required
                            >
                            <small>Minimum: <?= htmlspecialchars(rtrim(rtrim(number_format((float)$fund['min_investment_xmr'], 12), '0'), '.'), ENT_QUOTES, 'UTF-8') ?> XMR</small>
                        </div>
                        <div class="alert alert-warning">
                            <strong>Important:</strong> After submitting, you will receive a unique Monero payment address. Send the exact amount shown within <?= INVOICE_EXPIRY_MINUTES ?> minutes to confirm your investment.
                        </div>
                        <button type="submit" class="btn-primary btn-block">Generate Payment Address</button>
                    </form>
                </div>
            </div>
        <?php endif; ?>

    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
