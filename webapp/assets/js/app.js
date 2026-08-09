'use strict';

/**
 * webapp/assets/js/app.js
 *
 * Client-side logic:
 *  1. Fetches live XMR & BTC prices from our /api/prices.php proxy
 *     (which in turn calls CoinGecko) and populates conversion displays.
 *  2. Recalculates conversion on USD input fields in deposit / invest forms.
 */

// ── Price cache ───────────────────────────────────────────────────────────────
let prices = { xmr: null, btc: null, fetched_at: null };
const PRICE_TTL = 60_000; // 60 s before we refetch

async function fetchPrices() {
  const now = Date.now();
  if (prices.xmr && prices.btc && (now - prices.fetched_at) < PRICE_TTL) {
    return prices;
  }
  try {
    const res = await fetch('/api/prices.php');
    if (!res.ok) throw new Error('price fetch failed');
    const data = await res.json();
    prices.xmr       = data.xmr;
    prices.btc       = data.btc;
    prices.fetched_at = now;
  } catch (e) {
    console.warn('Could not load prices:', e);
  }
  return prices;
}

// ── Conversion helpers ────────────────────────────────────────────────────────
function usdToXmr(usd, rate) {
  if (!rate || rate === 0) return null;
  return (usd / rate).toFixed(6);
}

function usdToBtc(usd, rate) {
  if (!rate || rate === 0) return null;
  return (usd / rate).toFixed(8);
}

function formatUsd(n) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);
}

// ── Live conversion on input fields ──────────────────────────────────────────
/**
 * Wires up a USD input (#id) so that changing it updates a conversion display
 * element (#convDisplay) based on the selected coin (#coinSelect).
 */
async function wireConversionInput(inputId, convDisplayId, coinSelectId) {
  const input      = document.getElementById(inputId);
  const convDisplay = document.getElementById(convDisplayId);
  const coinSelect  = coinSelectId ? document.getElementById(coinSelectId) : null;

  if (!input || !convDisplay) return;

  async function update() {
    const usd  = parseFloat(input.value) || 0;
    const coin = coinSelect ? coinSelect.value : 'XMR';
    const p    = await fetchPrices();

    let coinAmt, rate;
    if (coin === 'BTC') {
      coinAmt = usdToBtc(usd, p.btc);
      rate    = p.btc;
    } else {
      coinAmt = usdToXmr(usd, p.xmr);
      rate    = p.xmr;
    }

    if (coinAmt === null || usd === 0) {
      convDisplay.textContent = 'Enter an amount above';
    } else {
      const rateStr = rate ? formatUsd(rate) : '\u2014';
      // Build DOM nodes instead of using innerHTML to avoid XSS
      const amtEl = document.createElement('span');
      amtEl.className = 'coin-amount';
      amtEl.textContent = `${coinAmt} ${coin}`;

      const rateEl = document.createElement('div');
      rateEl.className = 'rate-note';
      rateEl.textContent = `1 ${coin} = ${rateStr} USD \u00b7 via CoinGecko`;

      convDisplay.replaceChildren(amtEl, rateEl);
    }
  }

  input.addEventListener('input', update);
  if (coinSelect) coinSelect.addEventListener('change', update);
  // Initial render
  await update();
}

// ── Populate price ticker in the header (if element present) ─────────────────
async function updateTicker() {
  const p = await fetchPrices();
  const tickerXmr = document.getElementById('ticker-xmr');
  const tickerBtc = document.getElementById('ticker-btc');
  if (tickerXmr && p.xmr) tickerXmr.textContent = formatUsd(p.xmr);
  if (tickerBtc && p.btc) tickerBtc.textContent = formatUsd(p.btc);
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  updateTicker();
  // Deposit page
  wireConversionInput('usd-amount', 'conv-display', 'coin-select');
  // Invest page
  wireConversionInput('invest-amount', 'invest-conv-display', 'invest-coin');
});
