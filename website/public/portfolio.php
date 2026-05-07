<?php
require_once dirname(__DIR__) . '/includes/config.php';
require_once dirname(__DIR__) . '/includes/auth.php';

$page_title = 'Portfolio';
require_once dirname(__DIR__) . '/includes/header.php';
?>

<section class="page-hero page-hero-sm">
    <div class="container">
        <span class="section-label">Our Investments</span>
        <h1>Portfolio</h1>
        <p>A curated selection of our most impactful blockchain investments across all strategies.</p>
    </div>
</section>

<section class="section-dark">
    <div class="container">
        <div class="intro-grid">
            <div class="intro-text">
                <h2>Investment Philosophy</h2>
                <p>We invest at the earliest possible stage — often before a product exists — because we believe the greatest value is created by those who shape the infrastructure, not just those who use it. Our process combines deep technical due diligence with market structure analysis and network effect modeling.</p>
                <p>Our portfolio spans every meaningful layer of the blockchain stack: Layer 1 protocols, Layer 2 scaling solutions, DeFi primitives, privacy technologies, institutional infrastructure, and consumer applications. We seek companies and protocols that define new categories rather than compete in existing ones.</p>
            </div>
            <div class="portfolio-stats">
                <div class="stat-card">
                    <span class="stat-number">200+</span>
                    <span class="stat-label">Venture Investments</span>
                </div>
                <div class="stat-card">
                    <span class="stat-number">150+</span>
                    <span class="stat-label">Token Investments</span>
                </div>
                <div class="stat-card">
                    <span class="stat-number">40+</span>
                    <span class="stat-label">Countries</span>
                </div>
                <div class="stat-card">
                    <span class="stat-number">$4.7B+</span>
                    <span class="stat-label">AUM</span>
                </div>
            </div>
        </div>
    </div>
</section>

<section class="section-light">
    <div class="container">
        <h2 class="section-title">Portfolio Highlights</h2>
        <p class="section-subtitle">A selection of notable investments across our fund strategies.</p>
        <div class="portfolio-grid">
            <div class="portfolio-card">
                <div class="portfolio-category">Layer 1 Protocol</div>
                <h3>Monero (XMR)</h3>
                <p>The leading privacy-preserving cryptocurrency with mandatory privacy features. Our earliest and most conviction-driven investment, representing the gold standard for fungible digital cash.</p>
                <div class="portfolio-meta">
                    <span class="badge badge-confirmed">Active Position</span>
                    <span class="portfolio-year">Since 2014</span>
                </div>
            </div>
            <div class="portfolio-card">
                <div class="portfolio-category">DeFi Infrastructure</div>
                <h3>Decentralized Exchange Protocol</h3>
                <p>A foundational AMM protocol enabling trustless token swaps. Early participation in governance and liquidity provision created significant value as TVL grew from $10M to over $5B.</p>
                <div class="portfolio-meta">
                    <span class="badge badge-confirmed">Realized</span>
                    <span class="portfolio-year">2019–2022</span>
                </div>
            </div>
            <div class="portfolio-card">
                <div class="portfolio-category">Layer 2 Scaling</div>
                <h3>Zero-Knowledge Rollup Network</h3>
                <p>Next-generation Ethereum scaling using ZK proofs for trustless computation. Investment made at pre-mainnet stage; now one of the most widely adopted L2 networks globally.</p>
                <div class="portfolio-meta">
                    <span class="badge badge-confirmed">Active Position</span>
                    <span class="portfolio-year">Since 2021</span>
                </div>
            </div>
            <div class="portfolio-card">
                <div class="portfolio-category">Web3 Infrastructure</div>
                <h3>Decentralized Storage Protocol</h3>
                <p>Incentivized, verifiable, and censorship-resistant data storage. A critical component of the fully decentralized web stack powering dApps, NFTs, and archival storage.</p>
                <div class="portfolio-meta">
                    <span class="badge badge-confirmed">Active Position</span>
                    <span class="portfolio-year">Since 2020</span>
                </div>
            </div>
            <div class="portfolio-card">
                <div class="portfolio-category">AI + Blockchain</div>
                <h3>Decentralized AI Compute Network</h3>
                <p>An open marketplace for AI model training and inference on decentralized GPU networks. Combining the efficiency of distributed computing with blockchain incentive structures.</p>
                <div class="portfolio-meta">
                    <span class="badge badge-confirmed">Active Position</span>
                    <span class="portfolio-year">Since 2023</span>
                </div>
            </div>
            <div class="portfolio-card">
                <div class="portfolio-category">Digital Ownership</div>
                <h3>NFT Marketplace Protocol</h3>
                <p>A creator-first NFT platform with on-chain royalty enforcement. Early investment in the digital ownership primitive now used by millions of artists and collectors worldwide.</p>
                <div class="portfolio-meta">
                    <span class="badge badge-confirmed">Realized</span>
                    <span class="portfolio-year">2021–2023</span>
                </div>
            </div>
        </div>
    </div>
</section>

<section class="section-dark section-cta">
    <div class="container text-center">
        <h2>Join Our Portfolio as an Investor</h2>
        <p class="section-subtitle">Participate in the blockchain economy's next chapter alongside our institutional-grade portfolio.</p>
        <a href="/invest.php" class="btn-primary">Start Investing</a>
        <a href="/funds.php" class="btn-secondary" style="margin-left:1rem">View All Funds</a>
    </div>
</section>

<?php require_once dirname(__DIR__) . '/includes/footer.php'; ?>
