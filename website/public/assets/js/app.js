/**
 * Crypto Investment Platform — app.js
 * Vanilla JS: nav scroll, reveal animations, cookie banner, price ticker, newsletter
 */

// ── Nav: turn solid on scroll ──────────────────────────────────────────────
const nav = document.getElementById('main-nav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 50);
  }, { passive: true });
}

// ── Hamburger menu ─────────────────────────────────────────────────────────
const hamburger = document.getElementById('hamburger');
if (hamburger) {
  hamburger.addEventListener('click', () => {
    const links   = document.getElementById('nav-links');
    const actions = document.querySelector('.nav-actions');
    links?.classList.toggle('open');
    actions?.classList.toggle('open');
  });
}

// ── Intersection Observer: reveal animations ───────────────────────────────
const revealEls = document.querySelectorAll('.reveal');
if (revealEls.length) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

  revealEls.forEach(el => observer.observe(el));
}

// ── Auto-dismiss toasts ────────────────────────────────────────────────────
const toast = document.getElementById('toast');
if (toast) {
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity .4s';
    setTimeout(() => toast.remove(), 400);
  }, 4500);
}

// ── Cookie banner ──────────────────────────────────────────────────────────
const cookieBanner = document.getElementById('cookie-banner');
const cookieAccept = document.getElementById('cookie-accept');
if (cookieBanner && !localStorage.getItem('cookie_ok')) {
  setTimeout(() => cookieBanner.classList.add('show'), 1500);
}
if (cookieAccept) {
  cookieAccept.addEventListener('click', () => {
    localStorage.setItem('cookie_ok', '1');
    cookieBanner.classList.remove('show');
  });
}

// ── Live price ticker ──────────────────────────────────────────────────────
const priceXmr = document.getElementById('price-xmr');
const priceBtc = document.getElementById('price-btc');
const priceEth = document.getElementById('price-eth');

async function fetchPrices() {
  try {
    const res  = await fetch('/api/prices');
    const data = await res.json();
    const fmt  = (n) => '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (priceXmr && data.xmr) priceXmr.textContent = fmt(data.xmr);
    if (priceBtc && data.btc) priceBtc.textContent = fmt(data.btc);
    if (priceEth && data.eth) priceEth.textContent = fmt(data.eth);
  } catch (_) { /* silently fail */ }
}

if (priceXmr || priceBtc || priceEth) {
  fetchPrices();
  setInterval(fetchPrices, 60000);
}

// ── Newsletter form ────────────────────────────────────────────────────────
const newsletterForm = document.getElementById('newsletter-form');
const newsletterMsg  = document.getElementById('newsletter-msg');
if (newsletterForm) {
  newsletterForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = newsletterForm.email.value.trim();
    try {
      const res  = await fetch('/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'email=' + encodeURIComponent(email),
      });
      const data = await res.json();
      if (newsletterMsg) {
        newsletterMsg.textContent = data.message || 'Done!';
        newsletterMsg.style.color = data.success ? '#065f46' : '#7f1d1d';
      }
      if (data.success) newsletterForm.reset();
    } catch (_) {
      if (newsletterMsg) newsletterMsg.textContent = 'An error occurred. Please try again.';
    }
  });
}
