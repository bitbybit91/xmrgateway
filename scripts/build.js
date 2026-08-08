#!/usr/bin/env node
'use strict';

// ─── Static Site Generator for AcceptXMR Frontend ───────────────────────────
// Reads config/crypto.config.json, validates addresses, copies static assets
// from server/static/ into dist/, and generates dist/config.js with a
// window.CRYPTO_CONFIG global so the frontend can reference configured values.
// ─────────────────────────────────────────────────────────────────────────────

const fs = require('fs');
const path = require('path');

// ── Paths ────────────────────────────────────────────────────────────────────
const ROOT = path.resolve(__dirname, '..');
const CONFIG_FILE = path.join(ROOT, 'config', 'crypto.config.json');
const STATIC_SRC = path.join(ROOT, 'server', 'static');
const DIST = path.join(ROOT, 'dist');

// ── Validation helpers ────────────────────────────────────────────────────────

/**
 * Returns true when addr looks like a valid Monero primary or subaddress.
 * Primary addresses start with '4', integrated/subaddresses with '8'.
 * Valid lengths are 95 (standard) or 106 (integrated).
 */
function isValidXmrAddress(addr) {
  return (
    typeof addr === 'string' &&
    /^[48][0-9A-Za-z]{94}([0-9A-Za-z]{11})?$/.test(addr)
  );
}

/**
 * Returns true when addr matches one of:
 *   P2PKH  – starts with 1, 25–34 chars of Base58
 *   P2SH   – starts with 3, 25–34 chars of Base58
 *   Bech32 – starts with bc1 (mainnet) or tb1 (testnet)
 */
function isValidBtcAddress(addr) {
  if (typeof addr !== 'string') return false;
  const p2pkh = /^1[1-9A-HJ-NP-Za-km-z]{24,33}$/;
  const p2sh = /^3[1-9A-HJ-NP-Za-km-z]{24,33}$/;
  const bech32 = /^(bc1|tb1)[ac-hj-np-z02-9]{6,87}$/i;
  return p2pkh.test(addr) || p2sh.test(addr) || bech32.test(addr);
}

// ── Load & validate config ───────────────────────────────────────────────────

function loadConfig() {
  if (!fs.existsSync(CONFIG_FILE)) {
    console.error(
      `\nERROR: Configuration file not found: ${CONFIG_FILE}\n` +
      `Copy the example and fill in your addresses:\n` +
      `  cp config/crypto.config.example.json config/crypto.config.json\n`
    );
    process.exit(1);
  }

  let cfg;
  try {
    cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'));
  } catch (err) {
    console.error(`\nERROR: Failed to parse ${CONFIG_FILE}: ${err.message}\n`);
    process.exit(1);
  }

  // Collect all validation errors before failing so the user sees them all.
  const errors = [];

  // XMR primary address
  const xmrAddr = cfg.xmr && cfg.xmr.primaryAddress;
  if (!isValidXmrAddress(xmrAddr)) {
    errors.push(
      `  config.xmr.primaryAddress is invalid ("${xmrAddr}"). ` +
      `Must start with 4 or 8 and be 95 or 106 characters long.`
    );
  }

  // XMR view key (64 hex chars)
  const xmrKey = cfg.xmr && cfg.xmr.viewKey;
  if (typeof xmrKey !== 'string' || !/^[0-9a-fA-F]{64}$/.test(xmrKey)) {
    errors.push(
      `  config.xmr.viewKey is invalid ("${xmrKey}"). ` +
      `Must be a 64-character hex string.`
    );
  }

  // BTC receiving address
  const btcAddr = cfg.btc && cfg.btc.receivingAddress;
  if (!isValidBtcAddress(btcAddr)) {
    errors.push(
      `  config.btc.receivingAddress is invalid ("${btcAddr}"). ` +
      `Must be a valid P2PKH, P2SH, or Bech32 address.`
    );
  }

  // acceptxmr.daemonUrl
  const daemonUrl = cfg.acceptxmr && cfg.acceptxmr.daemonUrl;
  if (typeof daemonUrl !== 'string' || !daemonUrl.startsWith('http')) {
    errors.push(
      `  config.acceptxmr.daemonUrl is invalid ("${daemonUrl}"). ` +
      `Must be a valid http/https URL.`
    );
  }

  if (errors.length > 0) {
    console.error(
      `\nERROR: ${CONFIG_FILE} contains invalid values:\n\n` +
      errors.join('\n') +
      `\n\nFix the above fields and re-run npm run build.\n`
    );
    process.exit(1);
  }

  return cfg;
}

// ── File-system helpers ───────────────────────────────────────────────────────

/** Recursively copy a directory, overwriting destination files. */
function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/** Write a file, creating parent directories as needed. */
function writeFile(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, content, 'utf8');
}

// ── Generate dist/config.js ───────────────────────────────────────────────────

/**
 * Emit a <script>-loadable JS file that exposes the crypto config as a
 * window-level global so static HTML pages can reference it without a server.
 * The private view key is intentionally excluded from the browser bundle.
 */
function generateConfigJs(cfg) {
  // Only include data safe for the browser — never the private view key.
  const browserSafe = {
    xmr: {
      primaryAddress: cfg.xmr.primaryAddress,
      restoreHeight: cfg.xmr.restoreHeight !== undefined ? cfg.xmr.restoreHeight : 0,
    },
    btc: {
      receivingAddress: cfg.btc.receivingAddress,
      network: cfg.btc.network || 'mainnet',
    },
    acceptxmr: {
      daemonUrl: cfg.acceptxmr.daemonUrl,
      scanInterval: cfg.acceptxmr.scanInterval !== undefined ? cfg.acceptxmr.scanInterval : 1000,
    },
  };

  return (
    '// Auto-generated by scripts/build.js — do not edit directly.\n' +
    '// Re-run `npm run build` after changing config/crypto.config.json.\n' +
    `window.CRYPTO_CONFIG = ${JSON.stringify(browserSafe, null, 2)};\n`
  );
}

// ── Generate dist/index.html ──────────────────────────────────────────────────

/**
 * Produce a self-contained index.html that references config.js.
 * It mirrors the structure of server/static/pay.html but replaces
 * Tera template variables with static placeholders and adds config.js.
 */
function generateIndexHtml() {
  const payHtmlSrc = path.join(STATIC_SRC, 'pay.html');
  let html = fs.readFileSync(payHtmlSrc, 'utf8');

  // Replace Tera-style template expressions with static placeholder text so
  // the page renders without a Rust backend.  The JS in acceptxmr.js updates
  // these elements dynamically via the WebSocket / REST calls at runtime.
  html = html
    .replace(/\{\{address\}\}/g, '')
    .replace(/\{\{\s*amount_paid\s*\}\}/g, '0')
    .replace(/\{\{[^}]+\}\}/g, '');

  // Inject config.js before the closing </body> (or at the very end if absent).
  const configScriptTag = '<script type="text/javascript" src="config.js"></script>\n';
  if (html.includes('</body>')) {
    html = html.replace('</body>', `${configScriptTag}</body>`);
  } else {
    html = html + configScriptTag;
  }

  return html;
}

// ── Main ──────────────────────────────────────────────────────────────────────

function main() {
  console.log('AcceptXMR static site generator\n');

  // 1. Load and validate configuration.
  console.log(`Reading config from ${CONFIG_FILE} …`);
  const cfg = loadConfig();
  console.log('  Config OK.');

  // 2. Clean and recreate dist/.
  console.log(`\nCleaning dist/ …`);
  if (fs.existsSync(DIST)) {
    fs.rmSync(DIST, { recursive: true, force: true });
  }
  fs.mkdirSync(DIST, { recursive: true });

  // 3. Copy all server/static/ assets verbatim into dist/.
  //    This preserves CSS, JS, images, vendor libs, and HTML templates.
  console.log(`Copying static assets from server/static/ …`);
  copyDir(STATIC_SRC, DIST);

  // 4. Generate dist/config.js with browser-safe config values.
  console.log('Generating dist/config.js …');
  writeFile(path.join(DIST, 'config.js'), generateConfigJs(cfg));

  // 5. Generate dist/index.html from pay.html with Tera vars stripped.
  console.log('Generating dist/index.html …');
  writeFile(path.join(DIST, 'index.html'), generateIndexHtml());

  // 6. Print a summary of what was written.
  console.log('\nBuild complete. Output:');
  (function list(dir, indent) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      console.log(' '.repeat(indent) + entry.name + (entry.isDirectory() ? '/' : ''));
      if (entry.isDirectory()) list(path.join(dir, entry.name), indent + 2);
    }
  })(DIST, 2);

  console.log(`\nServe dist/ with any static file host, e.g.:\n  npx serve dist/\n  python3 -m http.server --directory dist 8080\n`);
}

main();
