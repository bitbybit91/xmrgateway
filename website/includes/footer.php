<?php
require_once __DIR__ . '/config.php';
require_once __DIR__ . '/csrf.php';
?>
</main>
<footer class="site-footer">
    <div class="footer-container">
        <div class="footer-grid">
            <div class="footer-col">
                <h4><?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></h4>
                <p class="footer-tagline">First independent investment firm focused exclusively on blockchain technology.</p>
            </div>
            <div class="footer-col">
                <h4>Navigation</h4>
                <ul class="footer-links">
                    <li><a href="/funds.php">Funds</a></li>
                    <li><a href="/portfolio.php">Portfolio</a></li>
                    <li><a href="/insights.php">Insights</a></li>
                    <li><a href="/invest.php">Invest</a></li>
                </ul>
            </div>
            <div class="footer-col">
                <h4>Company</h4>
                <ul class="footer-links">
                    <li><a href="#">Contact</a></li>
                    <li><a href="#">Legal</a></li>
                    <li><a href="#">Privacy Policy</a></li>
                    <li><a href="#">Terms of Service</a></li>
                </ul>
            </div>
            <div class="footer-col footer-newsletter">
                <h4>Stay Informed</h4>
                <p>Get market insights and fund updates delivered to your inbox.</p>
                <form method="POST" action="/index.php?action=subscribe" class="newsletter-form">
                    <?= csrf_field() ?>
                    <div class="newsletter-row">
                        <input type="email" name="email" placeholder="Your email address" required class="newsletter-input">
                        <button type="submit" class="btn-primary btn-sm">Subscribe</button>
                    </div>
                </form>
            </div>
        </div>
        <div class="footer-bottom">
            <p class="copyright">&copy; <?= date('Y') ?> <?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?>. All rights reserved.</p>
            <p class="disclaimer">
                <strong>Legal Disclaimer:</strong> This platform is for educational/demonstration purposes only.
                Accepting investments may require licensing under SEC, FINRA, MiFID II, or equivalent regulations
                depending on your jurisdiction. Nothing on this site constitutes financial advice. Past performance
                is not indicative of future results. Cryptocurrency investments carry significant risk including
                total loss of capital.
            </p>
        </div>
    </div>
</footer>
</body>
</html>
