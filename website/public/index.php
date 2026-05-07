<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/db.php';
require_once dirname(__DIR__) . '/includes/auth.php';
require_once dirname(__DIR__) . '/includes/csrf.php';

$page_title = 'Home';
$message = '';
$message_type = '';

// Newsletter subscribe handler
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_GET['action'] ?? '') === 'subscribe') {
    csrf_verify();
    $email = trim($_POST['email'] ?? '');
    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $message = 'Please enter a valid email address.';
        $message_type = 'error';
    } else {
        try {
            $pdo = DB::get();
            $stmt = $pdo->prepare('INSERT IGNORE INTO newsletter_subscribers (email) VALUES (:email)');
            $stmt->execute([':email' => $email]);
            $message = 'Thank you for subscribing! You will receive our latest insights.';
            $message_type = 'success';
        } catch (PDOException $e) {
            $message = 'Unable to process subscription. Please try again later.';
            $message_type = 'error';
        }
    }
}

require_once dirname(__DIR__) . '/includes/header.php';
?>

<?php if ($message): ?>
    <div class="alert alert-<?= htmlspecialchars($message_type, ENT_QUOTES, 'UTF-8') ?> container">
        <?= htmlspecialchars($message, ENT_QUOTES, 'UTF-8') ?>
    </div>
<?php endif; ?>

<!-- Hero -->
<section class="hero">
    <div class="hero-content">
        <p class="hero-eyebrow">Est. 2013 · Blockchain Investment</p>
        <h1 class="hero-headline">First independent investment firm focused exclusively on blockchain technology</h1>
        <p class="hero-sub">We back visionary founders and protocols at the frontier of Web3, DeFi, and digital assets. From seed to scale, CryptoInvest is your long-term partner in the blockchain economy.</p>
        <div class="hero-ctas">
            <a href="/funds.php" class="btn-primary">View Funds</a>
            <a href="/portfolio.php" class="btn-secondary">Our Portfolio</a>
        </div>
    </div>
</section>

<!-- Since 2013 intro -->
<section class="section-intro section-dark">
    <div class="container">
        <div class="intro-grid">
            <div class="intro-text">
                <span class="section-label">Since 2013</span>
                <h2>A decade of blockchain-first investing</h2>
                <p>CryptoInvest was founded in 2013 with a singular thesis: blockchain technology would fundamentally reshape global finance, commerce, and governance. Before Bitcoin reached $1,000 for the first time, we were already deep in the ecosystem — partnering with protocol teams, backing infrastructure founders, and building a portfolio that would define the next decade of digital assets.</p>
                <p>Today, our team of researchers, engineers, and operators manages capital across venture equity, early-stage tokens, and liquid strategies — always guided by rigorous fundamental analysis and an unwavering long-term perspective.</p>
            </div>
            <div class="intro-highlight">
                <blockquote>"The blockchain is the most important invention since the internet itself."</blockquote>
                <cite>— CryptoInvest Research Team</cite>
            </div>
        </div>
    </div>
</section>

<!-- Stats -->
<section class="section-stats section-light">
    <div class="container">
        <h2 class="section-title text-center">CryptoInvest at a Glance</h2>
        <div class="stat-grid">
            <div class="stat-card">
                <span class="stat-number">$4.7B+</span>
                <span class="stat-label">Assets Under Management</span>
            </div>
            <div class="stat-card">
                <span class="stat-number">3</span>
                <span class="stat-label">Fund Strategies</span>
            </div>
            <div class="stat-card">
                <span class="stat-number">120+</span>
                <span class="stat-label">Deals Led</span>
            </div>
            <div class="stat-card">
                <span class="stat-number">200+</span>
                <span class="stat-label">Venture Investments</span>
            </div>
            <div class="stat-card">
                <span class="stat-number">150+</span>
                <span class="stat-label">Token Investments</span>
            </div>
            <div class="stat-card">
                <span class="stat-number">40%</span>
                <span class="stat-label">Capital Outside U.S.</span>
            </div>
        </div>
    </div>
</section>

<!-- Timeline -->
<section class="section-timeline section-dark">
    <div class="container">
        <h2 class="section-title">A History of Firsts</h2>
        <p class="section-subtitle">We have led the industry at every major inflection point.</p>
        <div class="timeline">
            <div class="timeline-item">
                <span class="timeline-year">2013</span>
                <div class="timeline-content">
                    <h3>First Blockchain Fund</h3>
                    <p>Launched the industry's first dedicated blockchain venture fund, backing Bitcoin infrastructure and early wallets.</p>
                </div>
            </div>
            <div class="timeline-item">
                <span class="timeline-year">2017</span>
                <div class="timeline-content">
                    <h3>First ICO Fund</h3>
                    <p>Created the first institutional-grade fund focused exclusively on token offerings, establishing frameworks still used industry-wide.</p>
                </div>
            </div>
            <div class="timeline-item">
                <span class="timeline-year">2019</span>
                <div class="timeline-content">
                    <h3>First DeFi Investment</h3>
                    <p>Recognized the transformative potential of decentralized finance before the term was widely used, leading seed rounds in foundational DeFi protocols.</p>
                </div>
            </div>
            <div class="timeline-item">
                <span class="timeline-year">2021</span>
                <div class="timeline-content">
                    <h3>First NFT Fund</h3>
                    <p>Launched a dedicated strategy for non-fungible tokens and digital ownership, investing in creators, marketplaces, and IP rights management protocols.</p>
                </div>
            </div>
            <div class="timeline-item">
                <span class="timeline-year">2023</span>
                <div class="timeline-content">
                    <h3>First AI + Blockchain Investment</h3>
                    <p>At the intersection of artificial intelligence and decentralized networks, we identified the next computing paradigm and deployed early capital into pioneering protocols.</p>
                </div>
            </div>
        </div>
    </div>
</section>

<!-- Investment Types -->
<section class="section-funds section-light">
    <div class="container">
        <h2 class="section-title text-center">Investment Strategies</h2>
        <p class="section-subtitle text-center">Three distinct strategies to match your risk profile and investment horizon.</p>
        <div class="fund-cards">
            <div class="fund-card">
                <div class="fund-card-tier tier-1">Tier I</div>
                <h3>Venture Equity Fund</h3>
                <p>Early-stage equity positions in the most promising Web3 infrastructure companies. Long-term value creation through founder partnerships.</p>
                <ul class="fund-highlights">
                    <li>Min. Investment: 5 XMR</li>
                    <li>Target APY: 22.5%</li>
                    <li>Horizon: 5–10 years</li>
                </ul>
                <a href="/invest.php?fund=venture-equity" class="btn-primary btn-sm">Invest Now</a>
            </div>
            <div class="fund-card fund-card-featured">
                <div class="fund-card-tier tier-2">Tier II</div>
                <h3>Early-Stage Token Fund</h3>
                <p>Pre-market token investments with asymmetric upside. We identify breakthrough protocols before mainstream adoption curves begin.</p>
                <ul class="fund-highlights">
                    <li>Min. Investment: 1 XMR</li>
                    <li>Target APY: 35%</li>
                    <li>Horizon: 2–5 years</li>
                </ul>
                <a href="/invest.php?fund=early-stage-token" class="btn-primary btn-sm">Invest Now</a>
            </div>
            <div class="fund-card">
                <div class="fund-card-tier tier-3">Tier III</div>
                <h3>Liquid Token Fund</h3>
                <p>A diversified portfolio of established cryptocurrencies optimized for risk-adjusted returns with flexible liquidity provisions.</p>
                <ul class="fund-highlights">
                    <li>Min. Investment: 0.1 XMR</li>
                    <li>Target APY: 15%</li>
                    <li>Horizon: 1–3 years</li>
                </ul>
                <a href="/invest.php?fund=liquid-token" class="btn-primary btn-sm">Invest Now</a>
            </div>
        </div>
    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
