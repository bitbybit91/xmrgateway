<?php
/**
 * webapp/includes/footer.php
 */
function include_footer(): void
{
    ?>

<!-- ── Footer ──────────────────────────────────────────────────────────────── -->
<footer class="xmr-footer mt-auto">
  <div class="container py-5">
    <div class="row g-4">
      <div class="col-lg-4">
        <h5 class="fw-bold mb-3"><span class="brand-accent">XMR</span> Gateway Capital</h5>
        <p class="text-muted small">
          A privacy-first crypto investment platform powered by Monero and Bitcoin.
          Your keys, your coins, your future.
        </p>
      </div>
      <div class="col-lg-2 col-6">
        <h6 class="text-uppercase fw-semibold mb-3 text-muted small">Funds</h6>
        <ul class="list-unstyled small">
          <li><a href="<?= SITE_URL ?>/index.php#funds" class="footer-link">Bitcoin Fund</a></li>
          <li><a href="<?= SITE_URL ?>/index.php#funds" class="footer-link">Monero Fund</a></li>
          <li><a href="<?= SITE_URL ?>/index.php#funds" class="footer-link">Crypto Blend</a></li>
          <li><a href="<?= SITE_URL ?>/index.php#funds" class="footer-link">DeFi Yield</a></li>
        </ul>
      </div>
      <div class="col-lg-2 col-6">
        <h6 class="text-uppercase fw-semibold mb-3 text-muted small">Account</h6>
        <ul class="list-unstyled small">
          <li><a href="<?= SITE_URL ?>/auth/register.php" class="footer-link">Open Account</a></li>
          <li><a href="<?= SITE_URL ?>/auth/login.php"    class="footer-link">Sign In</a></li>
          <li><a href="<?= SITE_URL ?>/dashboard/index.php" class="footer-link">Dashboard</a></li>
        </ul>
      </div>
      <div class="col-lg-4">
        <h6 class="text-uppercase fw-semibold mb-3 text-muted small">Disclaimer</h6>
        <p class="text-muted small">
          Cryptocurrency investments carry significant risk. Past performance is not
          indicative of future results. Invest only what you can afford to lose.
          This platform is not regulated financial advice.
        </p>
      </div>
    </div>
    <hr class="border-secondary mt-4">
    <div class="row align-items-center">
      <div class="col-md-6 small text-muted">
        &copy; <?= date('Y') ?> <?= SITE_NAME ?>. All rights reserved.
      </div>
      <div class="col-md-6 text-md-end small text-muted">
        Powered by <a href="https://www.getmonero.org" target="_blank" class="footer-link">Monero</a>
        &amp; <a href="https://bitcoin.org" target="_blank" class="footer-link">Bitcoin</a>
      </div>
    </div>
  </div>
</footer>

<!-- Bootstrap 5 JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"
        integrity="sha384-YvpcrYf0tY3lHB60NNkmXc4s9bIOgUxi8T/jzmMQEnOGm8ZDPuS/RRcB+CDvKQ49"
        crossorigin="anonymous"></script>

<!-- Site JS -->
<script src="<?= SITE_URL ?>/assets/js/app.js"></script>

</body>
</html>
    <?php
}
