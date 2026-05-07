#!/usr/bin/env python3
"""
deploy_investment_site.py  v1.0.0
══════════════════════════════════════════════════════════════════════════════
Automated, idempotent deployment script for a PHP-based crypto investment
company website on Ubuntu 20.04 LTS.

  • Apache 2.4 vhost bound to 127.0.0.1 only  (no clearnet exposure)
  • PHP 7.4 backend — ZERO JavaScript, pure CSS3 UI
  • Pantera Capital-inspired dark-gold institutional design
  • AcceptXMR-Server via Docker (busyboredom/acceptxmr) for XMR invoicing
  • Tor v3 hidden service via /etc/tor/torrc.d/  (torrc is never overwritten)
  • Safe for systems with existing hidden services / Apache vhosts

USAGE
  sudo python3 deploy_investment_site.py [OPTIONS]

OPTIONS
  --wallet-address ADDR   XMR primary address          (required on first run)
  --viewkey KEY           XMR private view key          (required on first run)
  --api-token TOKEN       AcceptXMR internal API token  (auto-generated if omitted)
  --site-name NAME        Firm name          (default: Meridian Capital)
  --tagline TEXT          Hero tagline       (default: Digital Asset Investment Management)
  --apache-port PORT      127.0.0.1 listen port for Apache vhost  (default: 8888)
  --site-dir DIR          Apache DocumentRoot            (default: /var/www/investment_site)
  --contact-email EMAIL   Contact e-mail displayed on site
  --xmr-daemon URL        Monero daemon URL  (default: http://xmr-node.cakewallet.com:18081/)
  --restore-height N      Wallet restore height          (default: null)
  --skip-acceptxmr        Skip AcceptXMR Docker deployment
  --dry-run               Print every action; modify nothing
  --force                 Re-create website files even if they already exist

REQUIREMENTS
  Ubuntu 20.04 LTS, root privileges, internet access.
"""

# ─── stdlib only ──────────────────────────────────────────────────────────────
import argparse
import datetime
import json
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import textwrap
import time

# ─── version ──────────────────────────────────────────────────────────────────
SCRIPT_VERSION = "1.0.0"

# ─── well-known paths ─────────────────────────────────────────────────────────
TORRC_PATH        = "/etc/tor/torrc"
TORRC_BAK_PATH    = "/etc/tor/torrc.bak"
TORRC_D_DIR       = "/etc/tor/torrc.d"
TOR_CONF_FILE     = f"{TORRC_D_DIR}/investment_site.conf"
HIDDEN_SVC_DIR    = "/var/lib/tor/investment_site"
APACHE_PORTS_CONF = "/etc/apache2/ports.conf"
APACHE_SITES_AVAIL = "/etc/apache2/sites-available"
VHOST_CONF        = f"{APACHE_SITES_AVAIL}/investment_site.conf"
ACCEPTXMR_DIR     = "/opt/xmrgateway"
ACCEPTXMR_CONF    = "/etc/xmrgateway/acceptxmr.yaml"
ACCEPTXMR_ENV     = "/etc/xmrgateway/.env"
ACCEPTXMR_SERVICE = "/etc/systemd/system/acceptxmr.service"
ACCEPTXMR_DB_DIR  = "/var/lib/acceptxmr/db"
ACCEPTXMR_CERT_DIR = "/var/lib/acceptxmr/cert"

# ─── defaults ─────────────────────────────────────────────────────────────────
DEFAULT_SITE_NAME    = "Meridian Capital"
DEFAULT_TAGLINE      = "Digital Asset Investment Management"
DEFAULT_APACHE_PORT  = 8888
DEFAULT_SITE_DIR     = "/var/www/investment_site"
DEFAULT_XMR_DAEMON   = "http://xmr-node.cakewallet.com:18081/"
DEFAULT_CONTACT_EMAIL = "contact@meridian.onion"
ACCEPTXMR_EXT_PORT   = 8080
ACCEPTXMR_INT_PORT   = 8081

IDEMPOTENCY_TAG = "# MANAGED BY deploy_investment_site.py"

# ══════════════════════════════════════════════════════════════════════════════
#  EMBEDDED WEBSITE CONTENT
#  All PHP / HTML / CSS is stored as raw Python strings so that PHP's $ signs
#  are never misinterpreted.  Python-side values are injected with .replace().
# ══════════════════════════════════════════════════════════════════════════════

# ─── css/style.css ────────────────────────────────────────────────────────────
SITE_CSS = r"""/* ══════════════════════════════════════════════════════
   Meridian Capital — Main Stylesheet
   Pure CSS3 · No JavaScript · CSS Grid + Flexbox
   ══════════════════════════════════════════════════════ */

/* ── Custom properties ── */
:root {
  --bg:           #090909;
  --bg-alt:       #111111;
  --bg-card:      #161616;
  --bg-hover:     #1e1e1e;
  --accent:       #c8a96e;
  --accent-dark:  #a07840;
  --accent-light: #dfc08c;
  --text:         #f0ece4;
  --text-muted:   #888880;
  --text-dim:     #555550;
  --border:       #272720;
  --border-light: #333328;
  --success:      #4caf50;
  --warning:      #e07b2c;
  --error:        #e05c3c;
  --shadow:       0 8px 32px rgba(0,0,0,.7);
  --shadow-sm:    0 2px 12px rgba(0,0,0,.5);
  --radius:       4px;
  --radius-lg:    8px;
  --transition:   all .22s ease;
  --font-display: Georgia,'Times New Roman',serif;
  --font-body:    'Helvetica Neue',Arial,Helvetica,sans-serif;
  --max-w:        1180px;
}

/* ── Reset ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 16px; scroll-behavior: smooth; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-body);
  line-height: 1.65;
  min-height: 100vh;
}
img { max-width: 100%; height: auto; display: block; }
a   { color: var(--accent); text-decoration: none; transition: var(--transition); }
a:hover { color: var(--accent-light); }
ul, ol { list-style: none; }
h1,h2,h3,h4,h5 {
  font-family: var(--font-display);
  font-weight: normal;
  line-height: 1.2;
  color: var(--text);
}

/* ── Layout helpers ── */
.container {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 0 24px;
}
.section { padding: 80px 0; }
.section-alt { background: var(--bg-alt); }
.section-title {
  font-family: var(--font-display);
  font-size: clamp(1.6rem, 3vw, 2.4rem);
  color: var(--text);
  margin-bottom: .4em;
}
.section-sub {
  color: var(--text-muted);
  font-size: .95rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  margin-bottom: 1rem;
}
.divider {
  width: 48px; height: 2px;
  background: var(--accent);
  margin: 1.2rem 0 2.4rem;
}
.text-center { text-align: center; }
.text-muted  { color: var(--text-muted); }
.mt-1 { margin-top: .5rem; }
.mt-2 { margin-top: 1rem;  }
.mt-3 { margin-top: 1.5rem;}
.mt-4 { margin-top: 2rem;  }
.flex { display: flex; }
.flex-center { display: flex; align-items: center; justify-content: center; }
.grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px,1fr)); gap: 2rem; }
.grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap: 2rem; }
.grid-4 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 1.5rem; }

/* ── Buttons ── */
.btn {
  display: inline-block;
  padding: .72rem 2rem;
  font-family: var(--font-body);
  font-size: .9rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  border: 1px solid var(--accent);
  color: var(--accent);
  background: transparent;
  cursor: pointer;
  transition: var(--transition);
  border-radius: var(--radius);
}
.btn:hover {
  background: var(--accent);
  color: var(--bg);
  text-decoration: none;
}
.btn-solid {
  background: var(--accent);
  color: var(--bg);
}
.btn-solid:hover {
  background: var(--accent-light);
  border-color: var(--accent-light);
  color: var(--bg);
}
.btn-lg { padding: .9rem 2.6rem; font-size: 1rem; }

/* ── Navigation ── */
.site-header {
  position: sticky; top: 0; z-index: 900;
  background: rgba(9,9,9,.96);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(6px);
}
.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
}
.nav-logo {
  font-family: var(--font-display);
  font-size: 1.2rem;
  color: var(--text) !important;
  letter-spacing: .04em;
}
.nav-logo span { color: var(--accent); }

/* CSS-only mobile hamburger toggle */
.nav-toggle { display: none; }
.nav-toggle-label {
  display: none;
  flex-direction: column;
  gap: 5px;
  cursor: pointer;
  padding: 4px;
}
.nav-toggle-label span {
  display: block;
  width: 24px; height: 2px;
  background: var(--text);
  transition: var(--transition);
}

.nav-menu {
  display: flex;
  align-items: center;
  gap: 2px;
}
.nav-item { position: relative; }
.nav-item > a {
  display: block;
  padding: .55rem 1rem;
  font-size: .85rem;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--text-muted);
  transition: var(--transition);
  white-space: nowrap;
}
.nav-item > a:hover,
.nav-item > a.active { color: var(--accent); }

/* Dropdown — CSS :hover only, no JS */
.nav-dropdown {
  display: none;
  position: absolute;
  top: 100%; left: 0;
  min-width: 200px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-top: 2px solid var(--accent);
  box-shadow: var(--shadow);
  z-index: 999;
}
.nav-dropdown a {
  display: block;
  padding: .65rem 1.2rem;
  font-size: .84rem;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  transition: var(--transition);
}
.nav-dropdown a:last-child { border-bottom: none; }
.nav-dropdown a:hover { color: var(--accent); background: var(--bg-hover); }
.nav-item:hover .nav-dropdown { display: block; }

.nav-cta {
  margin-left: 1rem;
}

/* Mobile: checkbox hack */
@media (max-width: 820px) {
  .nav-toggle-label { display: flex; }
  .nav-menu {
    display: none;
    position: absolute;
    top: 64px; left: 0; right: 0;
    flex-direction: column;
    align-items: stretch;
    background: var(--bg-alt);
    border-bottom: 1px solid var(--border);
    padding: .5rem 0;
    gap: 0;
  }
  .nav-toggle:checked ~ .nav-menu { display: flex; }
  .nav-item > a { text-align: center; padding: .8rem 1.2rem; }
  .nav-dropdown {
    position: static;
    display: none;
    border: none;
    border-top: 1px solid var(--border);
    box-shadow: none;
  }
  .nav-item:hover .nav-dropdown { display: none; } /* disable hover on mobile */
  .nav-cta { margin: .5rem 1.2rem; }
}

/* ── Hero section ── */
.hero {
  min-height: 88vh;
  display: flex;
  align-items: center;
  background:
    linear-gradient(160deg, rgba(200,169,110,.06) 0%, transparent 50%),
    var(--bg);
  border-bottom: 1px solid var(--border);
  position: relative;
  overflow: hidden;
}
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 80% 60% at 70% 40%, rgba(200,169,110,.04) 0%, transparent 70%);
  pointer-events: none;
}
.hero-content { position: relative; z-index: 1; max-width: 680px; }
.hero-eyebrow {
  font-size: .78rem;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 1.4rem;
  display: flex;
  align-items: center;
  gap: .7rem;
}
.hero-eyebrow::before {
  content: '';
  display: inline-block;
  width: 28px; height: 1px;
  background: var(--accent);
}
.hero-heading {
  font-family: var(--font-display);
  font-size: clamp(2.2rem, 5.5vw, 4.2rem);
  color: var(--text);
  line-height: 1.1;
  margin-bottom: 1.6rem;
}
.hero-heading em {
  font-style: italic;
  color: var(--accent);
}
.hero-body {
  font-size: 1.05rem;
  color: var(--text-muted);
  max-width: 520px;
  margin-bottom: 2.4rem;
  line-height: 1.75;
}
.hero-actions { display: flex; gap: 1rem; flex-wrap: wrap; }

/* ── Stat bar ── */
.stat-bar {
  background: var(--bg-alt);
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  padding: 2rem 0;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0;
  text-align: center;
}
.stat-item {
  padding: 1rem 1.5rem;
  border-right: 1px solid var(--border);
}
.stat-item:last-child { border-right: none; }
.stat-num {
  font-family: var(--font-display);
  font-size: 2rem;
  color: var(--accent);
  display: block;
}
.stat-label {
  font-size: .75rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: .25rem;
}

/* ── Cards ── */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 2rem;
  transition: var(--transition);
}
.card:hover {
  border-color: var(--border-light);
  transform: translateY(-3px);
  box-shadow: var(--shadow);
}
.card-accent-top { border-top: 2px solid var(--accent); }
.card-icon {
  width: 44px; height: 44px;
  border-radius: 50%;
  background: rgba(200,169,110,.1);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 1.2rem;
  font-size: 1.2rem;
  color: var(--accent);
}
.card-title {
  font-family: var(--font-display);
  font-size: 1.15rem;
  margin-bottom: .5rem;
}
.card-body { color: var(--text-muted); font-size: .9rem; line-height: 1.7; }

/* ── Strategy / portfolio cards ── */
.strategy-tag {
  display: inline-block;
  font-size: .72rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--accent);
  border: 1px solid var(--accent-dark);
  border-radius: var(--radius);
  padding: .2rem .7rem;
  margin-bottom: 1rem;
}
.strategy-meta {
  display: flex;
  gap: 1.5rem;
  margin-top: 1.2rem;
  font-size: .82rem;
  color: var(--text-dim);
}
.strategy-meta strong { color: var(--text-muted); }

/* ── Team cards ── */
.team-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 2rem;
  text-align: center;
  transition: var(--transition);
}
.team-card:hover { border-color: var(--border-light); box-shadow: var(--shadow-sm); }
.team-avatar {
  width: 80px; height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-dark), var(--accent));
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 1.2rem;
  font-family: var(--font-display);
  font-size: 1.6rem;
  color: var(--bg);
}
.team-name  { font-family: var(--font-display); font-size: 1.05rem; margin-bottom: .2rem; }
.team-role  { color: var(--accent); font-size: .8rem; letter-spacing: .1em; text-transform: uppercase; margin-bottom: .8rem; }
.team-bio   { color: var(--text-muted); font-size: .88rem; line-height: 1.65; }

/* ── Forms ── */
.form-group { margin-bottom: 1.4rem; }
.form-label {
  display: block;
  font-size: .82rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: .5rem;
}
.form-control {
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  padding: .75rem 1rem;
  color: var(--text);
  font-size: .95rem;
  font-family: var(--font-body);
  transition: var(--transition);
  -webkit-appearance: none;
}
.form-control:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(200,169,110,.15);
}
select.form-control { cursor: pointer; }
textarea.form-control { resize: vertical; min-height: 110px; }
.form-note { font-size: .8rem; color: var(--text-dim); margin-top: .4rem; }
.form-error { color: var(--error); font-size: .85rem; margin-top: .4rem; }

/* ── Payment page ── */
.payment-wrap {
  max-width: 640px;
  margin: 60px auto;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: 3px solid var(--accent);
  border-radius: var(--radius-lg);
  padding: 2.4rem;
  box-shadow: var(--shadow);
}
.payment-status {
  display: inline-flex;
  align-items: center;
  gap: .5rem;
  font-size: .8rem;
  letter-spacing: .1em;
  text-transform: uppercase;
  padding: .3rem .9rem;
  border-radius: 999px;
  border: 1px solid;
  margin-bottom: 1.6rem;
}
.status-awaiting { color: var(--warning); border-color: var(--warning); background: rgba(224,123,44,.08); }
.status-partial   { color: #f59e0b;        border-color: #f59e0b;        background: rgba(245,158,11,.08); }
.status-confirmed { color: var(--success); border-color: var(--success); background: rgba(76,175,80,.08); }
.status-expired   { color: var(--error);   border-color: var(--error);   background: rgba(224,92,60,.08); }

.payment-address-box {
  background: var(--bg);
  border: 1px solid var(--border-light);
  border-radius: var(--radius);
  padding: 1rem;
  font-family: monospace;
  font-size: .82rem;
  color: var(--accent-light);
  word-break: break-all;
  margin: 1rem 0;
  line-height: 1.6;
}
.payment-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: .65rem 0;
  border-bottom: 1px solid var(--border);
  font-size: .9rem;
}
.payment-row:last-child { border-bottom: none; }
.payment-row .label { color: var(--text-muted); }
.payment-row .value { color: var(--text); font-family: monospace; }
.payment-progress {
  background: var(--border);
  border-radius: 999px;
  height: 6px;
  margin-top: 1rem;
  overflow: hidden;
}
.payment-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent-dark), var(--accent));
  border-radius: 999px;
  transition: width 1s ease;
}
.payment-refresh-note {
  font-size: .78rem;
  color: var(--text-dim);
  text-align: center;
  margin-top: 1.4rem;
}

/* ── Alert boxes ── */
.alert {
  border-radius: var(--radius);
  padding: 1rem 1.2rem;
  margin-bottom: 1.2rem;
  font-size: .9rem;
  border: 1px solid;
}
.alert-info    { background: rgba(200,169,110,.07); border-color: var(--accent-dark); color: var(--accent-light); }
.alert-success { background: rgba(76,175,80,.08);   border-color: #4caf50; color: #81c784; }
.alert-error   { background: rgba(224,92,60,.08);   border-color: var(--error); color: #ef9a9a; }
.alert-warning { background: rgba(224,123,44,.08);  border-color: var(--warning); color: #ffb74d; }

/* ── Footer ── */
.site-footer {
  background: var(--bg-alt);
  border-top: 1px solid var(--border);
  padding: 56px 0 28px;
}
.footer-grid {
  display: grid;
  grid-template-columns: 1.8fr repeat(3, 1fr);
  gap: 3rem;
  margin-bottom: 3rem;
}
.footer-brand {
  font-family: var(--font-display);
  font-size: 1.05rem;
  color: var(--text);
  margin-bottom: .8rem;
}
.footer-brand span { color: var(--accent); }
.footer-tagline { color: var(--text-dim); font-size: .85rem; line-height: 1.7; }
.footer-col h4 {
  font-family: var(--font-body);
  font-size: .75rem;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 1rem;
}
.footer-col a {
  display: block;
  font-size: .88rem;
  color: var(--text-dim);
  padding: .25rem 0;
  transition: var(--transition);
}
.footer-col a:hover { color: var(--accent); }
.footer-bottom {
  border-top: 1px solid var(--border);
  padding-top: 1.4rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: .8rem;
  font-size: .78rem;
  color: var(--text-dim);
}
.footer-disclaimer {
  font-size: .75rem;
  color: var(--text-dim);
  margin-top: 1rem;
  line-height: 1.6;
  max-width: 780px;
}

@media (max-width: 768px) {
  .footer-grid { grid-template-columns: 1fr 1fr; }
  .footer-grid > :first-child { grid-column: 1 / -1; }
  .stat-grid { grid-template-columns: 1fr 1fr; }
  .stat-item { border-right: none; border-bottom: 1px solid var(--border); }
  .stat-item:nth-child(even) { border-right: none; }
  .hero { min-height: 70vh; }
  .section { padding: 56px 0; }
}
@media (max-width: 480px) {
  .footer-grid { grid-template-columns: 1fr; }
  .hero-actions { flex-direction: column; }
  .hero-actions .btn { text-align: center; }
  .payment-wrap { margin: 24px; padding: 1.4rem; }
}

/* ── Page header (inner pages) ── */
.page-header {
  padding: 64px 0 40px;
  background: linear-gradient(180deg, rgba(200,169,110,.04) 0%, transparent 100%);
  border-bottom: 1px solid var(--border);
}
.page-header h1 {
  font-size: clamp(1.8rem, 4vw, 3rem);
  margin-bottom: .5rem;
}
.page-header p { color: var(--text-muted); max-width: 580px; }

/* ── Breadcrumb ── */
.breadcrumb {
  display: flex;
  gap: .5rem;
  font-size: .78rem;
  color: var(--text-dim);
  margin-bottom: .8rem;
}
.breadcrumb a { color: var(--text-dim); }
.breadcrumb a:hover { color: var(--accent); }
.breadcrumb span { color: var(--text-muted); }
"""

# ─── inc/config.php ───────────────────────────────────────────────────────────
PHP_CONFIG = r"""<?php
/**
 * Site configuration  — generated by deploy_investment_site.py
 * Edit values below to customise the site.
 */

// ── Firm identity ──────────────────────────────────────────────────────────
define('SITE_NAME',    'PLACEHOLDER_SITE_NAME');
define('SITE_TAGLINE', 'PLACEHOLDER_TAGLINE');
define('SITE_URL',     'PLACEHOLDER_SITE_URL');

// ── Contact ────────────────────────────────────────────────────────────────
define('CONTACT_EMAIL', 'PLACEHOLDER_CONTACT_EMAIL');

// ── AcceptXMR connection ───────────────────────────────────────────────────
// Internal API (invoice creation) — localhost only, never exposed externally
define('AXMR_INT_URL',   'https://127.0.0.1:PLACEHOLDER_INT_PORT');
define('AXMR_EXT_URL',   'http://127.0.0.1:PLACEHOLDER_EXT_PORT');
define('AXMR_TOKEN',     'PLACEHOLDER_API_TOKEN');

// ── Invoice settings ───────────────────────────────────────────────────────
define('INV_CONFIRMATIONS', 2);        // confirmations before "paid"
define('INV_EXPIRY_SECS',   3600);     // 1 hour

// ── Currency conversion ────────────────────────────────────────────────────
define('XMR_PRICE_API', 'https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd');
define('PICONEROS_PER_XMR', 1000000000000);  // 1e12

// ── Minimum investment (USD) ───────────────────────────────────────────────
define('MIN_INVEST_USD', 100);

/**
 * Fetch live XMR/USD price from CoinGecko (server-side, no JS).
 * Returns float or null on failure.
 */
function fetch_xmr_usd_price(): ?float {
    if (!function_exists('curl_init')) return null;
    $ch = curl_init(XMR_PRICE_API);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 6,
        CURLOPT_USERAGENT      => 'InvestmentSite/1.0',
    ]);
    $raw  = curl_exec($ch);
    $err  = curl_errno($ch);
    curl_close($ch);
    if ($err || !$raw) return null;
    $data = json_decode($raw, true);
    return (float)($data['monero']['usd'] ?? 0) ?: null;
}

/**
 * Convert USD to piconeros.
 * Returns int|null — null if price unavailable.
 */
function usd_to_piconeros(float $usd): ?int {
    $price = fetch_xmr_usd_price();
    if (!$price) return null;
    $xmr = $usd / $price;
    return (int)round($xmr * PICONEROS_PER_XMR);
}

/**
 * Create an AcceptXMR invoice via the internal API.
 * Returns the invoice_id string or null on failure.
 */
function create_invoice(int $piconeros, string $order): ?string {
    if (!function_exists('curl_init')) return null;
    $payload = json_encode([
        'piconeros_due'          => $piconeros,
        'confirmations_required' => INV_CONFIRMATIONS,
        'expiration_in'          => INV_EXPIRY_SECS,
        'order'                  => $order,
    ]);
    $ch = curl_init(AXMR_INT_URL . '/invoice');
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => [
            'Content-Type: application/json',
            'Authorization: Bearer ' . AXMR_TOKEN,
        ],
        CURLOPT_SSL_VERIFYPEER => false,  // self-signed cert on localhost
        CURLOPT_SSL_VERIFYHOST => false,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
    ]);
    $raw = curl_exec($ch);
    $err = curl_errno($ch);
    curl_close($ch);
    if ($err || !$raw) return null;
    $data = json_decode($raw, true);
    return $data['invoice_id'] ?? null;
}

/**
 * Fetch an invoice's current status from the external API.
 * Returns associative array or null on failure.
 */
function get_invoice(string $id): ?array {
    if (!function_exists('curl_init')) return null;
    $url = AXMR_EXT_URL . '/invoice?id=' . urlencode($id);
    $ch  = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 8,
    ]);
    $raw = curl_exec($ch);
    $err = curl_errno($ch);
    curl_close($ch);
    if ($err || !$raw) return null;
    return json_decode($raw, true) ?: null;
}
"""

# ─── inc/header.php ───────────────────────────────────────────────────────────
PHP_HEADER = r"""<?php
/**
 * Shared page header / navigation
 * Included at the top of every page.
 *
 * Expected variable before include:
 *   $page_title   (string)  — used in <title>
 *   $active_nav   (string)  — e.g. 'about', 'invest' …
 */
require_once __DIR__ . '/config.php';
$page_title  = $page_title  ?? SITE_NAME;
$active_nav  = $active_nav  ?? '';
function nav_active(string $page, string $active): string {
    return $page === $active ? ' active' : '';
}
?><!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow">
  <title><?= htmlspecialchars($page_title) ?> — <?= SITE_NAME ?></title>
  <link rel="stylesheet" href="/css/style.css">
<?php if (!empty($meta_refresh)): ?>
  <meta http-equiv="refresh" content="<?= (int)$meta_refresh ?>">
<?php endif; ?>
</head>
<body>

<header class="site-header">
  <div class="container nav-inner">

    <!-- Logo / brand -->
    <a href="/" class="nav-logo"><?= SITE_NAME ?><span>.</span></a>

    <!-- Mobile hamburger — CSS checkbox hack, zero JS -->
    <input type="checkbox" id="nav-toggle" class="nav-toggle">
    <label for="nav-toggle" class="nav-toggle-label" aria-label="Toggle navigation">
      <span></span><span></span><span></span>
    </label>

    <!-- Navigation menu -->
    <nav class="nav-menu" role="navigation">

      <div class="nav-item">
        <a href="/" class="<?= nav_active('home', $active_nav) ?>">Home</a>
      </div>

      <div class="nav-item">
        <a href="/about.php" class="<?= nav_active('about', $active_nav) ?>">About</a>
      </div>

      <div class="nav-item">
        <a href="/portfolio.php" class="<?= nav_active('portfolio', $active_nav) ?>">
          Strategies ▾
        </a>
        <div class="nav-dropdown">
          <a href="/portfolio.php#liquid">Liquid Strategies</a>
          <a href="/portfolio.php#venture">Venture Fund</a>
          <a href="/portfolio.php#infrastructure">Infrastructure</a>
        </div>
      </div>

      <div class="nav-item">
        <a href="/team.php" class="<?= nav_active('team', $active_nav) ?>">Team</a>
      </div>

      <div class="nav-item">
        <a href="/contact.php" class="<?= nav_active('contact', $active_nav) ?>">Contact</a>
      </div>

      <div class="nav-item nav-cta">
        <a href="/invest.php" class="btn btn-solid<?= nav_active('invest', $active_nav) ?>">
          Invest
        </a>
      </div>

    </nav>
  </div>
</header>
"""

# ─── inc/footer.php ───────────────────────────────────────────────────────────
PHP_FOOTER = r"""<?php
/**
 * Shared site footer — included at the bottom of every page.
 */
require_once __DIR__ . '/config.php';
$year = date('Y');
?>
<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">

      <div>
        <div class="footer-brand"><?= SITE_NAME ?><span>.</span></div>
        <p class="footer-tagline">
          Institutional digital asset investment management.<br>
          Accessible exclusively via Tor.
        </p>
      </div>

      <div class="footer-col">
        <h4>Company</h4>
        <a href="/about.php">About</a>
        <a href="/team.php">Team</a>
        <a href="/contact.php">Contact</a>
      </div>

      <div class="footer-col">
        <h4>Strategies</h4>
        <a href="/portfolio.php#liquid">Liquid</a>
        <a href="/portfolio.php#venture">Venture</a>
        <a href="/portfolio.php#infrastructure">Infrastructure</a>
      </div>

      <div class="footer-col">
        <h4>Invest</h4>
        <a href="/invest.php">Open Position</a>
        <a href="/contact.php">Enquire</a>
      </div>

    </div>

    <div class="footer-bottom">
      <span>&copy; <?= $year ?> <?= SITE_NAME ?>. All rights reserved.</span>
      <span>Tor-native · Monero-first · Privacy-preserving</span>
    </div>

    <p class="footer-disclaimer">
      Risk disclosure: Digital assets are highly volatile. Past performance is
      not indicative of future results. Investment in digital assets carries
      significant risk, including the possible loss of all invested capital.
      Nothing on this site constitutes financial advice. Access is restricted
      to accredited investors or jurisdictions where permitted.
    </p>
  </div>
</footer>

</body>
</html>
"""

# ─── index.php ────────────────────────────────────────────────────────────────
PHP_INDEX = r"""<?php
$page_title = 'Home';
$active_nav = 'home';
include 'inc/header.php';
?>

<!-- Hero -->
<section class="hero">
  <div class="container">
    <div class="hero-content">
      <div class="hero-eyebrow">Est. <?= date('Y') ?> &mdash; <?= SITE_TAGLINE ?></div>
      <h1 class="hero-heading">
        Capital at the <em>frontier</em><br>of digital finance.
      </h1>
      <p class="hero-body">
        <?= SITE_NAME ?> manages concentrated positions across the most
        compelling opportunities in blockchain infrastructure, liquid crypto
        assets, and early-stage protocols — with institutional rigour and
        absolute privacy.
      </p>
      <div class="hero-actions">
        <a href="/invest.php" class="btn btn-solid btn-lg">Open a Position</a>
        <a href="/portfolio.php" class="btn btn-lg">Our Strategies</a>
      </div>
    </div>
  </div>
</section>

<!-- Key stats -->
<div class="stat-bar">
  <div class="container">
    <div class="stat-grid">
      <div class="stat-item">
        <span class="stat-num">$1.2B+</span>
        <span class="stat-label">Assets Under Management</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">8+</span>
        <span class="stat-label">Years of Operation</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">3</span>
        <span class="stat-label">Investment Strategies</span>
      </div>
      <div class="stat-item">
        <span class="stat-num">XMR</span>
        <span class="stat-label">Native Settlement Currency</span>
      </div>
    </div>
  </div>
</div>

<!-- About blurb -->
<section class="section">
  <div class="container">
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:4rem;align-items:center">
      <div>
        <p class="section-sub">Who we are</p>
        <h2 class="section-title">Built for the next generation of digital capital.</h2>
        <div class="divider"></div>
        <p style="color:var(--text-muted);line-height:1.8;margin-bottom:1rem">
          <?= SITE_NAME ?> is a privacy-first investment management firm
          specialising in digital assets. We operate exclusively via the Tor
          network, accept only Monero (XMR), and maintain strict counterparty
          anonymity to protect both the firm and its investors.
        </p>
        <p style="color:var(--text-muted);line-height:1.8;margin-bottom:1.6rem">
          Our team combines decades of experience in traditional finance with
          deep technical expertise across blockchain architecture, cryptographic
          security, and decentralised protocol design.
        </p>
        <a href="/about.php" class="btn">Learn More About Us</a>
      </div>
      <div style="display:grid;gap:1.2rem">
        <?php
        $pillars = [
          ['Privacy-first mandate', 'All investor identities and positions are shielded. We accept no KYC obligations.'],
          ['Monero-native settlement', 'Subscriptions, redemptions, and distributions are conducted exclusively in XMR.'],
          ['On-chain transparency', 'Positions are verifiable on-chain. No custodian risk, no counterparty opacity.'],
        ];
        foreach ($pillars as $p): ?>
        <div class="card card-accent-top">
          <div class="card-title"><?= htmlspecialchars($p[0]) ?></div>
          <div class="card-body"><?= htmlspecialchars($p[1]) ?></div>
        </div>
        <?php endforeach; ?>
      </div>
    </div>
  </div>
</section>

<!-- Strategy overview -->
<section class="section section-alt">
  <div class="container">
    <div class="text-center" style="max-width:560px;margin:0 auto 3rem">
      <p class="section-sub">Investment Strategies</p>
      <h2 class="section-title">Three distinct mandates. One consistent edge.</h2>
      <div class="divider" style="margin:1rem auto"></div>
    </div>
    <div class="grid-3">
      <?php
      $strategies = [
        ['Liquid',         'Concentrated long-bias portfolio of major digital assets with tactical short overlays.',         '2016', 'Open'],
        ['Venture',        'Early-stage protocol investments with a 5–7 year horizon. Focused on L1/L2 infrastructure.', '2018', 'Closed'],
        ['Infrastructure', 'Mining, staking, and node operation for yield-bearing digital asset exposure.',                 '2020', 'Open'],
      ];
      foreach ($strategies as [$name, $desc, $vintage, $status]): ?>
      <div class="card">
        <span class="strategy-tag"><?= $name ?> Strategy</span>
        <div class="card-title"><?= SITE_NAME ?> <?= $name ?> Fund</div>
        <div class="card-body"><?= htmlspecialchars($desc) ?></div>
        <div class="strategy-meta">
          <span><strong>Vintage:</strong> <?= $vintage ?></span>
          <span><strong>Status:</strong> <span style="color:<?= $status==='Open'?'var(--success)':'var(--warning)' ?>"><?= $status ?></span></span>
        </div>
      </div>
      <?php endforeach; ?>
    </div>
    <div class="text-center mt-4">
      <a href="/portfolio.php" class="btn">View All Strategies</a>
    </div>
  </div>
</section>

<!-- CTA -->
<section class="section">
  <div class="container text-center" style="max-width:600px;margin:0 auto">
    <p class="section-sub">Get Started</p>
    <h2 class="section-title">Ready to allocate capital?</h2>
    <div class="divider" style="margin:1rem auto"></div>
    <p style="color:var(--text-muted);margin-bottom:2rem">
      Open a position today using Monero. Minimum investment applies.
      All on-boarding is anonymous and completed entirely over Tor.
    </p>
    <a href="/invest.php" class="btn btn-solid btn-lg">Open a Position Now</a>
  </div>
</section>

<?php include 'inc/footer.php'; ?>
"""

# ─── about.php ────────────────────────────────────────────────────────────────
PHP_ABOUT = r"""<?php
$page_title = 'About';
$active_nav = 'about';
include 'inc/header.php';
?>

<div class="page-header">
  <div class="container">
    <div class="breadcrumb"><a href="/">Home</a> <span>/</span> <span>About</span></div>
    <h1>About <?= SITE_NAME ?></h1>
    <p><?= SITE_TAGLINE ?></p>
  </div>
</div>

<section class="section">
  <div class="container" style="max-width:800px">
    <p class="section-sub">Our Mission</p>
    <h2 class="section-title">Capital allocation at the intersection of privacy and performance.</h2>
    <div class="divider"></div>
    <p style="color:var(--text-muted);line-height:1.9;margin-bottom:1.4rem">
      <?= SITE_NAME ?> was founded on a single conviction: institutional-grade digital
      asset management must be possible without sacrificing the privacy properties that
      make cryptocurrency uniquely valuable. We exist to prove that thesis at scale.
    </p>
    <p style="color:var(--text-muted);line-height:1.9;margin-bottom:1.4rem">
      Operating exclusively on the Tor network and settling entirely in Monero (XMR),
      we have built infrastructure that protects investors from surveillance, censorship,
      and regulatory overreach — without compromising on performance or operational
      integrity.
    </p>
    <p style="color:var(--text-muted);line-height:1.9;margin-bottom:2.5rem">
      Our investment philosophy is disciplined and contrarian. We seek positions where
      our informational edge — derived from deep protocol-level analysis — creates
      asymmetric return profiles unavailable to conventional asset managers.
    </p>
  </div>
</section>

<section class="section section-alt">
  <div class="container">
    <p class="section-sub">Our Values</p>
    <h2 class="section-title">Principles that guide every decision.</h2>
    <div class="divider"></div>
    <div class="grid-3" style="margin-top:2rem">
      <?php
      $values = [
        ['Privacy by Design',   'Investor confidentiality is non-negotiable. Every system, process, and communication is architected for maximum anonymity.'],
        ['Intellectual Rigour', 'Positions are built on first-principles analysis of protocol mechanics, token economics, and network effects — not narrative.'],
        ['Operational Security', 'Air-gapped signing, multi-sig custody, Tor-only communications, and zero counterparty exposure define our operational model.'],
        ['Long-term Orientation','We measure performance in years, not quarters. Our fund structures reflect patient capital allocation with no forced liquidity.'],
        ['Radical Transparency', 'While investor identities are private, all portfolio positions are on-chain verifiable. No black boxes, no custodian trust.'],
        ['Monero Maximalism',   'XMR is the only currency we accept and distribute. We believe fungible, private money is foundational to financial sovereignty.'],
      ];
      foreach ($values as [$title, $body]): ?>
      <div class="card">
        <div class="card-title"><?= htmlspecialchars($title) ?></div>
        <div class="card-body"><?= htmlspecialchars($body) ?></div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<section class="section">
  <div class="container" style="max-width:760px">
    <p class="section-sub">Structure &amp; Operations</p>
    <h2 class="section-title">Built for longevity.</h2>
    <div class="divider"></div>
    <?php
    $ops = [
      ['Legal structure',      'Offshore private investment partnership with no KYC requirements.'],
      ['Custody model',        'Self-custody only. Funds are held in multi-sig cold storage controlled by the investment committee.'],
      ['Settlement currency',  'Monero (XMR). All subscriptions and redemptions denominated in XMR.'],
      ['Minimum investment',   'XMR equivalent of USD ' . number_format(MIN_INVEST_USD) . '.'],
      ['Lock-up',              'Quarterly redemption windows. 30-day notice required.'],
      ['Reporting',            'Monthly NAV reports delivered via encrypted messaging.'],
      ['Communication',        'All correspondence conducted over Tor. No clearnet contact channels.'],
    ];
    foreach ($ops as [$k, $v]): ?>
    <div class="payment-row">
      <span class="label"><?= htmlspecialchars($k) ?></span>
      <span class="value" style="font-family:var(--font-body);text-align:right"><?= htmlspecialchars($v) ?></span>
    </div>
    <?php endforeach; ?>
    <div class="mt-4">
      <a href="/invest.php" class="btn btn-solid">Open a Position</a>
      &nbsp;
      <a href="/contact.php" class="btn">Enquire</a>
    </div>
  </div>
</section>

<?php include 'inc/footer.php'; ?>
"""

# ─── portfolio.php ────────────────────────────────────────────────────────────
PHP_PORTFOLIO = r"""<?php
$page_title = 'Investment Strategies';
$active_nav = 'portfolio';
include 'inc/header.php';

$strategies = [
  [
    'id'       => 'liquid',
    'name'     => 'Liquid Strategy',
    'tag'      => 'Liquid',
    'vintage'  => '2016',
    'status'   => 'Open',
    'min'      => '$10,000 equivalent',
    'horizon'  => '12–36 months rolling',
    'headline' => 'Concentrated digital asset portfolios with high conviction.',
    'body'     => 'The Liquid Strategy maintains long-bias concentrated positions across
      Bitcoin, Monero, and select large-cap digital assets. Tactical short overlays
      via non-custodial derivatives are deployed during periods of elevated risk.
      Portfolio turnover is low; typical holding periods exceed 12 months.',
    'assets'   => ['Bitcoin (BTC)', 'Monero (XMR)', 'Ethereum (ETH)', 'Solana (SOL)', 'Select large-caps'],
  ],
  [
    'id'       => 'venture',
    'name'     => 'Venture Fund',
    'tag'      => 'Venture',
    'vintage'  => '2018',
    'status'   => 'Closed',
    'min'      => '$50,000 equivalent',
    'horizon'  => '5–7 years',
    'headline' => 'Early-stage protocol investments with asymmetric upside.',
    'body'     => 'The Venture Fund makes concentrated early-stage investments in
      blockchain protocols, cryptographic privacy tools, and decentralised
      infrastructure projects. Typical ticket size: XMR 500–5,000 equivalent.
      The fund is currently closed to new subscriptions; the next vintage opens
      subject to deployment of current portfolio.',
    'assets'   => ['L1 protocols', 'Privacy tooling', 'ZK infrastructure', 'DEX / AMM primitives'],
  ],
  [
    'id'       => 'infrastructure',
    'name'     => 'Infrastructure Strategy',
    'tag'      => 'Infrastructure',
    'vintage'  => '2020',
    'status'   => 'Open',
    'min'      => '$5,000 equivalent',
    'horizon'  => 'Perpetual',
    'headline' => 'Yield from blockchain infrastructure operation.',
    'body'     => 'The Infrastructure Strategy generates yield through direct operation
      of mining hardware (primarily Monero RandomX), staking nodes on proof-of-stake
      networks, and Lightning Network routing. Returns are denominated in the native
      asset of each position. Investors receive XMR-equivalent distributions quarterly.',
    'assets'   => ['XMR RandomX mining', 'PoS staking nodes', 'Lightning routing', 'Monero node infrastructure'],
  ],
];
?>

<div class="page-header">
  <div class="container">
    <div class="breadcrumb"><a href="/">Home</a> <span>/</span> <span>Strategies</span></div>
    <h1>Investment Strategies</h1>
    <p>Three distinct mandates covering the full spectrum of digital asset opportunities.</p>
  </div>
</div>

<?php foreach ($strategies as $s): ?>
<section class="section <?= $s['id'] === 'venture' ? 'section-alt' : '' ?>" id="<?= $s['id'] ?>">
  <div class="container">
    <div style="display:grid;grid-template-columns:1fr 340px;gap:3.5rem;align-items:start">
      <div>
        <span class="strategy-tag"><?= $s['tag'] ?></span>
        <h2 class="section-title"><?= $s['name'] ?></h2>
        <div class="divider"></div>
        <p style="font-size:1.05rem;color:var(--text);margin-bottom:1rem;font-family:var(--font-display)">
          <?= htmlspecialchars($s['headline']) ?>
        </p>
        <p style="color:var(--text-muted);line-height:1.85;margin-bottom:1.6rem">
          <?= htmlspecialchars($s['body']) ?>
        </p>
        <p style="color:var(--text-muted);font-size:.9rem;margin-bottom:.4rem">
          <strong style="color:var(--text-muted)">Target assets:</strong>
        </p>
        <ul style="display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1.6rem">
          <?php foreach ($s['assets'] as $asset): ?>
          <li style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:.25rem .8rem;font-size:.82rem;color:var(--text-muted)"><?= htmlspecialchars($asset) ?></li>
          <?php endforeach; ?>
        </ul>
        <?php if ($s['status'] === 'Open'): ?>
        <a href="/invest.php?strategy=<?= urlencode($s['id']) ?>" class="btn btn-solid">Invest in this Strategy</a>
        <?php else: ?>
        <span class="btn" style="opacity:.5;cursor:not-allowed">Currently Closed</span>
        <?php endif; ?>
      </div>
      <div>
        <div class="card" style="position:sticky;top:84px">
          <h4 style="font-size:.75rem;letter-spacing:.12em;text-transform:uppercase;color:var(--text-muted);margin-bottom:1rem">Fund Details</h4>
          <?php foreach ([
            'Vintage'         => $s['vintage'],
            'Status'          => $s['status'],
            'Min. Investment' => $s['min'],
            'Time Horizon'    => $s['horizon'],
            'Settlement'      => 'Monero (XMR)',
          ] as $k => $v): ?>
          <div class="payment-row">
            <span class="label"><?= htmlspecialchars($k) ?></span>
            <span class="value" style="font-family:var(--font-body);color:<?= $k==='Status'&&$v==='Open'?'var(--success)':($k==='Status'?'var(--warning)':'var(--text)') ?>"><?= htmlspecialchars($v) ?></span>
          </div>
          <?php endforeach; ?>
        </div>
      </div>
    </div>
  </div>
</section>
<?php endforeach; ?>

<?php include 'inc/footer.php'; ?>
"""

# ─── team.php ─────────────────────────────────────────────────────────────────
PHP_TEAM = r"""<?php
$page_title = 'Team';
$active_nav = 'team';
include 'inc/header.php';

$team = [
  [
    'initials' => 'AM',
    'name'     => 'A. Mercer',
    'role'     => 'Managing Partner',
    'bio'      => '18 years in asset management across hedge funds and family offices. Transitioned to digital assets in 2013 following independent research into cryptographic money. Leads investment committee and fund strategy.',
  ],
  [
    'initials' => 'KS',
    'name'     => 'K. Strand',
    'role'     => 'Chief Technology Officer',
    'bio'      => 'Former protocol engineer at a privacy-focused L1 blockchain. Expertise in cryptographic primitives, ZK proof systems, and secure multi-party computation. Oversees operational security and technical due diligence.',
  ],
  [
    'initials' => 'RL',
    'name'     => 'R. Laine',
    'role'     => 'Head of Research',
    'bio'      => 'PhD in applied mathematics. Specialises in tokenomic modelling, on-chain analytics, and macroeconomic analysis of digital asset markets. Authored multiple peer-reviewed papers on monetary policy and blockchain economics.',
  ],
  [
    'initials' => 'TW',
    'name'     => 'T. Weiss',
    'role'     => 'Head of Operations',
    'bio'      => 'Background in institutional trading infrastructure and quantitative finance. Manages custody operations, multi-sig procedures, and investor relations. Previously with a Swiss private bank digital assets desk.',
  ],
];
?>

<div class="page-header">
  <div class="container">
    <div class="breadcrumb"><a href="/">Home</a> <span>/</span> <span>Team</span></div>
    <h1>Our Team</h1>
    <p>Experienced professionals with deep roots in both traditional finance and cryptography.</p>
  </div>
</div>

<section class="section">
  <div class="container">
    <div class="grid-4" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">
      <?php foreach ($team as $member): ?>
      <div class="team-card">
        <div class="team-avatar"><?= htmlspecialchars($member['initials']) ?></div>
        <div class="team-name"><?= htmlspecialchars($member['name']) ?></div>
        <div class="team-role"><?= htmlspecialchars($member['role']) ?></div>
        <div class="team-bio"><?= htmlspecialchars($member['bio']) ?></div>
      </div>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<section class="section section-alt">
  <div class="container text-center" style="max-width:620px;margin:0 auto">
    <p class="section-sub">Anonymity</p>
    <h2 class="section-title">Privacy extends to our team.</h2>
    <div class="divider" style="margin:1rem auto"></div>
    <p style="color:var(--text-muted);line-height:1.85">
      In keeping with our core values, all team members operate under pseudonyms
      and maintain separate operational identities. This is not a limitation —
      it is a deliberate feature of our security architecture. Our track record
      and on-chain verifiable positions speak for themselves.
    </p>
    <div class="mt-4">
      <a href="/contact.php" class="btn">Get in Touch</a>
    </div>
  </div>
</section>

<?php include 'inc/footer.php'; ?>
"""

# ─── invest.php ───────────────────────────────────────────────────────────────
PHP_INVEST = r"""<?php
/**
 * invest.php — Investment onboarding page.
 *
 * GET  → shows the investment form.
 * POST → validates input, fetches live XMR price, creates AcceptXMR invoice,
 *        and redirects to payment.php.  Zero JavaScript required.
 */
$page_title = 'Invest';
$active_nav = 'invest';
require_once 'inc/config.php';

$errors   = [];
$strategy = htmlspecialchars($_GET['strategy'] ?? '');

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    // ── Collect & sanitise ───────────────────────────────────────────────────
    $amount_usd  = (float) ($_POST['amount_usd']   ?? 0);
    $strat_post  = trim($_POST['strategy']          ?? '');
    $note        = trim(mb_substr($_POST['note']    ?? '', 0, 400));
    $csrf_token  = $_POST['csrf_token'] ?? '';

    // ── CSRF check (session-based) ────────────────────────────────────────────
    session_start();
    if (!hash_equals($_SESSION['csrf_token'] ?? '', $csrf_token)) {
        $errors[] = 'Invalid form token. Please reload and try again.';
    }

    // ── Validation ────────────────────────────────────────────────────────────
    if ($amount_usd < MIN_INVEST_USD) {
        $errors[] = 'Minimum investment is USD ' . number_format(MIN_INVEST_USD) . '.';
    }
    $valid_strats = ['liquid', 'infrastructure'];
    if (!in_array($strat_post, $valid_strats, true)) {
        $errors[] = 'Please select a valid open strategy.';
    }

    if (empty($errors)) {
        // ── Convert USD → piconeros (server-side, no JS) ─────────────────────
        $piconeros = usd_to_piconeros($amount_usd);
        if (!$piconeros) {
            $errors[] = 'Unable to fetch live XMR price. Please try again in a moment.';
        } else {
            // ── Create AcceptXMR invoice ──────────────────────────────────────
            $order_desc = sprintf('%s | %s strategy | Note: %s',
                SITE_NAME, $strat_post, $note ?: 'none');
            $invoice_id = create_invoice($piconeros, $order_desc);
            if (!$invoice_id) {
                $errors[] = 'Payment processor is temporarily unavailable. Please try again shortly.';
            } else {
                // ── Success: redirect to payment page ─────────────────────────
                $redirect = sprintf('/payment.php?id=%s&usd=%s&strategy=%s',
                    urlencode($invoice_id),
                    urlencode(number_format($amount_usd, 2)),
                    urlencode($strat_post));
                header('Location: ' . $redirect, true, 303);
                exit;
            }
        }
    }
} else {
    session_start();
}

// ── Generate CSRF token ────────────────────────────────────────────────────────
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}
$csrf_token = $_SESSION['csrf_token'];
?>

<div class="page-header">
  <div class="container">
    <div class="breadcrumb"><a href="/">Home</a> <span>/</span> <span>Invest</span></div>
    <h1>Open a Position</h1>
    <p>Institutional digital asset investment — private, anonymous, Monero-settled.</p>
  </div>
</div>

<section class="section">
  <div class="container" style="max-width:720px;margin:0 auto">

    <?php if (!empty($errors)): ?>
    <div class="alert alert-error">
      <?php foreach ($errors as $e): ?>
        <div><?= htmlspecialchars($e) ?></div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>

    <div class="alert alert-info">
      <strong>How it works:</strong> Enter your investment amount and select a strategy.
      We will calculate the live XMR equivalent and generate a Monero payment address
      for you. No account, no KYC, no clearnet connection required.
    </div>

    <form method="POST" action="/invest.php">
      <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($csrf_token) ?>">

      <div class="form-group">
        <label class="form-label" for="strategy">Strategy</label>
        <select name="strategy" id="strategy" class="form-control" required>
          <option value="">— Select strategy —</option>
          <option value="liquid"         <?= ($strategy==='liquid'||($_POST['strategy']??'')==='liquid')         ?'selected':'' ?>>Liquid Strategy (Open)</option>
          <option value="infrastructure" <?= ($strategy==='infrastructure'||($_POST['strategy']??'')==='infrastructure') ?'selected':'' ?>>Infrastructure Strategy (Open)</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label" for="amount_usd">Investment Amount (USD equivalent)</label>
        <input type="number"
               name="amount_usd"
               id="amount_usd"
               class="form-control"
               min="<?= MIN_INVEST_USD ?>"
               step="100"
               value="<?= htmlspecialchars($_POST['amount_usd'] ?? '') ?>"
               placeholder="e.g. 5000"
               required>
        <div class="form-note">
          Minimum: USD <?= number_format(MIN_INVEST_USD) ?>.
          Amount will be converted to XMR at the live rate when you submit.
        </div>
      </div>

      <div class="form-group">
        <label class="form-label" for="note">Optional note <span style="font-size:.75rem;text-transform:none;letter-spacing:0">(max 400 chars)</span></label>
        <textarea name="note" id="note" class="form-control" maxlength="400"
                  placeholder="Referral code, preferred settlement timing, etc."><?= htmlspecialchars($_POST['note'] ?? '') ?></textarea>
      </div>

      <div class="form-group" style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin-top:1.5rem">
        <label style="display:flex;gap:.7rem;align-items:flex-start;cursor:pointer">
          <input type="checkbox" name="ack" value="1" required
                 style="margin-top:.3rem;accent-color:var(--accent)">
          <span style="font-size:.88rem;color:var(--text-muted)">
            I acknowledge that digital asset investment involves significant risk including
            possible total loss of capital, that this does not constitute financial advice,
            and that I am accessing this platform of my own accord in a jurisdiction where
            doing so is lawful.
          </span>
        </label>
      </div>

      <button type="submit" class="btn btn-solid btn-lg" style="width:100%;margin-top:.5rem">
        Generate Payment Address
      </button>
    </form>

    <div style="margin-top:2rem;padding-top:1.5rem;border-top:1px solid var(--border)">
      <p style="font-size:.85rem;color:var(--text-dim)">
        Questions? <a href="/contact.php">Contact us</a> before investing.
        Venture Fund allocations require prior enquiry.
      </p>
    </div>

  </div>
</section>

<?php include 'inc/footer.php'; ?>
"""

# ─── payment.php ──────────────────────────────────────────────────────────────
PHP_PAYMENT = r"""<?php
/**
 * payment.php — Monero payment / invoice status page.
 *
 * Polls AcceptXMR's external API via server-side PHP curl.
 * Status refresh is achieved with HTML <meta http-equiv="refresh"> — no JS.
 *
 * Query params:
 *   id        AcceptXMR invoice ID
 *   usd       original USD amount (display only)
 *   strategy  strategy slug (display only)
 */
require_once 'inc/config.php';

$invoice_id  = trim($_GET['id']       ?? '');
$usd_display = htmlspecialchars($_GET['usd']      ?? '?');
$strategy    = htmlspecialchars($_GET['strategy'] ?? 'liquid');

$invoice     = null;
$fetch_error = false;
$refresh_secs = 30;

if ($invoice_id === '') {
    header('Location: /invest.php', true, 302);
    exit;
}

// Validate invoice ID — alphanumeric, underscore, hyphen only
if (!preg_match('/^[A-Za-z0-9_\-]{4,80}$/', $invoice_id)) {
    header('Location: /invest.php', true, 302);
    exit;
}

$invoice = get_invoice($invoice_id);
if ($invoice === null) {
    $fetch_error = true;
}

// Determine status label and CSS class
$status_class = 'status-awaiting';
$status_label = 'Awaiting Payment';
$is_done      = false;

if ($invoice) {
    $paid  = (int)($invoice['amount_paid']      ?? 0);
    $due   = (int)($invoice['amount_requested'] ?? 0);
    $confs = $invoice['confirmations']          ?? null;
    $req   = (int)($invoice['confirmations_required'] ?? INV_CONFIRMATIONS);
    $exp   = (int)($invoice['expiration_in']    ?? 0);

    if ($paid >= $due && $paid > 0 && $confs !== null && $confs >= $req) {
        $status_class = 'status-confirmed';
        $status_label = 'Confirmed';
        $is_done      = true;
        $refresh_secs = 0;
    } elseif ($paid > 0 && $paid < $due) {
        $status_class = 'status-partial';
        $status_label = 'Partially Paid';
    } elseif ($exp <= 0) {
        $status_class = 'status-expired';
        $status_label = 'Expired';
        $is_done      = true;
        $refresh_secs = 0;
    }
}

// XMR formatting helper (piconeros → XMR, 12 decimal places)
function fmt_xmr(int $piconeros): string {
    return number_format($piconeros / 1e12, 12, '.', '');
}

// Percent paid (cap at 100)
$pct_paid = 0;
if ($invoice && isset($invoice['amount_requested']) && $invoice['amount_requested'] > 0) {
    $pct_paid = min(100, (int)(($invoice['amount_paid'] / $invoice['amount_requested']) * 100));
}

// ── Output page ───────────────────────────────────────────────────────────────
// $meta_refresh is read by inc/header.php and placed inside <head>
$meta_refresh = ($refresh_secs > 0) ? $refresh_secs : null;
$page_title   = 'Payment — ' . $status_label;
$active_nav   = '';
include 'inc/header.php';
?>

<section style="padding:40px 0 80px">
  <div class="container">
    <div class="payment-wrap">

      <div class="breadcrumb" style="margin-bottom:1.2rem">
        <a href="/">Home</a> <span>/</span>
        <a href="/invest.php">Invest</a> <span>/</span>
        <span>Payment</span>
      </div>

      <h1 style="font-family:var(--font-display);font-size:1.5rem;margin-bottom:.6rem">
        Monero Invoice
      </h1>

      <span class="payment-status <?= $status_class ?>">
        &#9679; <?= $status_label ?>
      </span>

      <?php if ($fetch_error): ?>
      <div class="alert alert-error">
        Payment processor unreachable. Please reload in a moment.
        <br><a href="/payment.php?id=<?= urlencode($invoice_id) ?>&usd=<?= urlencode($usd_display) ?>&strategy=<?= urlencode($strategy) ?>">Retry</a>
      </div>

      <?php elseif ($status_class === 'status-expired'): ?>
      <div class="alert alert-warning">
        This invoice has expired. Please <a href="/invest.php">create a new one</a>.
      </div>

      <?php elseif ($status_class === 'status-confirmed'): ?>
      <div class="alert alert-success">
        <strong>Payment confirmed.</strong> Your investment position is being processed.
        You will receive an encrypted update from our team within 24 hours.
      </div>

      <?php else: ?>

      <!-- Payment details -->
      <?php if ($invoice): ?>

      <p style="font-size:.88rem;color:var(--text-muted);margin-bottom:1rem">
        Send <strong style="color:var(--accent)"><?= fmt_xmr((int)($invoice['amount_requested'] ?? 0)) ?> XMR</strong>
        to the address below. This page refreshes automatically every <?= $refresh_secs ?> seconds.
      </p>

      <div class="payment-address-box">
        <?= htmlspecialchars($invoice['address'] ?? '—') ?>
      </div>

      <p style="font-size:.78rem;color:var(--text-dim);margin-bottom:1.2rem">
        You may also use the Monero URI:
        <code style="word-break:break-all;color:var(--text-muted)"><?= htmlspecialchars($invoice['uri'] ?? '—') ?></code>
      </p>

      <div style="margin:1.2rem 0">
        <div class="payment-row">
          <span class="label">Amount due</span>
          <span class="value"><?= fmt_xmr((int)($invoice['amount_requested'] ?? 0)) ?> XMR</span>
        </div>
        <div class="payment-row">
          <span class="label">Amount received</span>
          <span class="value"><?= fmt_xmr((int)($invoice['amount_paid'] ?? 0)) ?> XMR</span>
        </div>
        <div class="payment-row">
          <span class="label">Confirmations</span>
          <span class="value">
            <?= ($invoice['confirmations'] ?? '—') ?> / <?= (int)($invoice['confirmations_required'] ?? INV_CONFIRMATIONS) ?>
          </span>
        </div>
        <div class="payment-row">
          <span class="label">Expires in</span>
          <span class="value"><?= (int)($invoice['expiration_in'] ?? 0) ?> blocks</span>
        </div>
        <div class="payment-row">
          <span class="label">Strategy</span>
          <span class="value"><?= htmlspecialchars(ucfirst($strategy)) ?></span>
        </div>
        <div class="payment-row">
          <span class="label">USD equivalent</span>
          <span class="value">$<?= $usd_display ?></span>
        </div>
      </div>

      <!-- Progress bar -->
      <div class="payment-progress">
        <div class="payment-progress-fill" style="width:<?= $pct_paid ?>%"></div>
      </div>

      <?php endif; /* $invoice */ ?>
      <?php endif; /* not expired/confirmed */ ?>

      <?php if (!$is_done && $refresh_secs > 0): ?>
      <p class="payment-refresh-note">
        &#8635; This page refreshes every <?= $refresh_secs ?> seconds.
        <a href="/payment.php?id=<?= urlencode($invoice_id) ?>&usd=<?= urlencode($usd_display) ?>&strategy=<?= urlencode($strategy) ?>">Refresh now</a>
      </p>
      <?php endif; ?>

      <div style="margin-top:1.6rem;padding-top:1.2rem;border-top:1px solid var(--border);font-size:.82rem;color:var(--text-dim)">
        Invoice ID: <code style="color:var(--text-muted)"><?= htmlspecialchars($invoice_id) ?></code><br>
        <span>Keep this URL bookmarked to check payment status.</span>
      </div>

    </div><!-- /.payment-wrap -->
  </div>
</section>

<?php include 'inc/footer.php'; ?>
"""

# ─── contact.php ──────────────────────────────────────────────────────────────
PHP_CONTACT = r"""<?php
$page_title = 'Contact';
$active_nav = 'contact';
include 'inc/header.php';
?>

<div class="page-header">
  <div class="container">
    <div class="breadcrumb"><a href="/">Home</a> <span>/</span> <span>Contact</span></div>
    <h1>Contact</h1>
    <p>All communications are Tor-native and end-to-end encrypted.</p>
  </div>
</div>

<section class="section">
  <div class="container" style="max-width:720px;margin:0 auto">

    <div class="alert alert-info" style="margin-bottom:2rem">
      <strong>Privacy notice:</strong> We operate exclusively on Tor.
      Do not attempt to contact us via clearnet channels.
      We will not respond to requests received outside this network.
    </div>

    <div class="grid-2" style="margin-bottom:3rem">

      <div class="card card-accent-top">
        <div class="card-title">Encrypted Email</div>
        <div class="card-body">
          For investment enquiries, redemption requests, and general correspondence.
          PGP-encrypted communications only.
        </div>
        <div style="margin-top:1.2rem;font-family:monospace;font-size:.9rem;color:var(--accent-light)">
          <?= CONTACT_EMAIL ?>
        </div>
      </div>

      <div class="card card-accent-top">
        <div class="card-title">Open a Position</div>
        <div class="card-body">
          Ready to invest? Use our anonymous onboarding flow to create a Monero
          invoice and open a position without any prior contact required.
        </div>
        <div style="margin-top:1.4rem">
          <a href="/invest.php" class="btn btn-solid">Invest Now</a>
        </div>
      </div>

    </div>

    <h2 class="section-title" style="font-size:1.4rem;margin-bottom:1rem">Response policy</h2>
    <div class="divider"></div>
    <?php
    $policies = [
      'Response time'       => '24–72 hours for initial enquiries.',
      'Investment enquiries'=> 'Venture Fund allocation requests require a minimum of 7 days for due diligence.',
      'Redemptions'         => 'Quarterly redemption windows. Submit redemption requests at least 30 days prior to quarter end.',
      'Encryption'          => 'We will only respond to PGP-encrypted messages. Unencrypted messages are discarded.',
      'Language'            => 'English only.',
    ];
    foreach ($policies as $k => $v): ?>
    <div class="payment-row">
      <span class="label"><?= htmlspecialchars($k) ?></span>
      <span style="color:var(--text-muted);font-size:.9rem;text-align:right;max-width:320px"><?= htmlspecialchars($v) ?></span>
    </div>
    <?php endforeach; ?>

  </div>
</section>

<?php include 'inc/footer.php'; ?>
"""

# ─── .htaccess ────────────────────────────────────────────────────────────────
HTACCESS = r"""# deploy_investment_site.py — Apache .htaccess
Options -Indexes -Includes

# ── Security headers ───────────────────────────────────────────────────────────
<IfModule mod_headers.c>
    Header always set X-Frame-Options "DENY"
    Header always set X-Content-Type-Options "nosniff"
    Header always set Referrer-Policy "no-referrer"
    Header always set Content-Security-Policy "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; script-src 'none'; object-src 'none'; base-uri 'self'"
    Header always set Permissions-Policy "interest-cohort=()"
    Header always set Cache-Control "no-store, no-cache, must-revalidate"
</IfModule>

# ── Deny access to sensitive files ────────────────────────────────────────────
<FilesMatch "\.(bak|log|sh|sql|env)$">
    Order allow,deny
    Deny from all
</FilesMatch>

# ── Protect inc/ directory ─────────────────────────────────────────────────────
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteRule ^inc/         - [F,L]
</IfModule>

# ── Pretty URLs (optional) ─────────────────────────────────────────────────────
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^([a-z]+)$ /$1.php [QSA,L]
</IfModule>

# ── PHP settings ───────────────────────────────────────────────────────────────
<IfModule mod_php7.c>
    php_flag display_errors Off
    php_flag expose_php     Off
    php_value session.cookie_httponly 1
    php_value session.cookie_samesite Strict
    php_value session.use_strict_mode 1
</IfModule>
"""

# ─── robots.txt ───────────────────────────────────────────────────────────────
ROBOTS_TXT = "User-agent: *\nDisallow: /\n"


# ══════════════════════════════════════════════════════════════════════════════
#  PYTHON UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

RESET = "\033[0m"
_COLOURS = {"INFO": "\033[94m", "OK": "\033[92m", "WARN": "\033[93m", "ERR": "\033[91m"}


def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    colour = _COLOURS.get(level, "")
    label = f"[{level:4s}]"
    print(f"{colour}{ts} {label}{RESET} {msg}")


def die(msg: str) -> None:
    log(msg, "ERR")
    sys.exit(1)


def run(cmd: str, dry_run: bool = False, check: bool = True,
        capture: bool = False, env: dict = None) -> subprocess.CompletedProcess:
    """Run a shell command. Logs the command. Respects dry_run."""
    log(f"$ {cmd}")
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")
    kwargs: dict = {
        "shell": True,
        "check": check,
        "capture_output": capture,
    }
    if env is not None:
        kwargs["env"] = {**os.environ, **env}
    return subprocess.run(cmd, **kwargs)  # noqa: S602


def write_file(path: str, content: str, mode: int = 0o644,
               dry_run: bool = False, force: bool = False) -> bool:
    """Write *content* to *path*.  Returns True if file was written."""
    p = pathlib.Path(path)
    if p.exists() and not force:
        log(f"  skipping (exists): {path}", "INFO")
        return False
    log(f"  writing: {path}")
    if dry_run:
        return True
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    os.chmod(path, mode)
    return True


def ensure_dir(path: str, mode: int = 0o755, owner: str = None,
               dry_run: bool = False) -> None:
    """Create directory (and parents) if it does not exist."""
    if not os.path.isdir(path):
        log(f"  mkdir: {path}")
        if not dry_run:
            pathlib.Path(path).mkdir(parents=True, exist_ok=True)
            os.chmod(path, mode)
    if owner and not dry_run and os.path.isdir(path):
        run(f"chown {owner} {path}", dry_run=dry_run)


def backup_file(path: str, bak: str, dry_run: bool = False) -> None:
    """Copy *path* → *bak* if *bak* does not already exist."""
    if os.path.isfile(path) and not os.path.isfile(bak):
        log(f"  backup: {path} → {bak}")
        if not dry_run:
            shutil.copy2(path, bak)


# ══════════════════════════════════════════════════════════════════════════════
#  DEPLOYMENT STEPS
# ══════════════════════════════════════════════════════════════════════════════

def step_check_prerequisites() -> None:
    """Step 1 — Verify root and Ubuntu 20.04."""
    log("═" * 60, "INFO")
    log("Step 1/10 — Checking prerequisites", "INFO")

    if os.geteuid() != 0:
        die("This script must be run as root (sudo).")

    try:
        with open("/etc/os-release") as fh:
            content = fh.read()
        if "Ubuntu" not in content or "20.04" not in content:
            log("WARNING: This script targets Ubuntu 20.04. Detected OS may differ.", "WARN")
        else:
            log("  Ubuntu 20.04 confirmed.", "OK")
    except FileNotFoundError:
        log("  /etc/os-release not found — cannot verify OS.", "WARN")


def step_install_packages(dry_run: bool) -> None:
    """Step 2 — Install required packages via apt-get."""
    log("═" * 60)
    log("Step 2/10 — Installing system packages")

    packages = [
        "apache2",
        "php7.4",
        "libapache2-mod-php7.4",
        "php7.4-curl",
        "php7.4-json",
        "php7.4-mbstring",
        "tor",
        "openssl",
        "git",
        "curl",
        "ca-certificates",
        "gnupg",
        "lsb-release",
    ]

    env = {"DEBIAN_FRONTEND": "noninteractive"}
    run("apt-get update -qq", dry_run=dry_run, env=env)
    pkg_str = " ".join(packages)
    run(
        f"apt-get install -y -qq --no-install-recommends {pkg_str}",
        dry_run=dry_run,
        env=env,
    )
    log("  Packages installed.", "OK")

    # Install Docker if not already present
    if not shutil.which("docker"):
        log("  Docker not found — installing via convenience script.")
        run("curl -fsSL https://get.docker.com | sh", dry_run=dry_run)
        run("systemctl enable docker --now", dry_run=dry_run)
    else:
        log("  Docker already installed — skipping.", "OK")


def step_enable_apache_modules(dry_run: bool) -> None:
    """Step 3 — Enable required Apache modules."""
    log("═" * 60)
    log("Step 3/10 — Enabling Apache modules")

    mods = ["rewrite", "headers", "php7.4"]
    for mod in mods:
        run(f"a2enmod {mod}", dry_run=dry_run, check=False)
    log("  Apache modules enabled.", "OK")


def step_configure_apache_port(port: int, dry_run: bool) -> None:
    """Step 4 — Add 'Listen 127.0.0.1:<port>' to ports.conf if missing."""
    log("═" * 60)
    log(f"Step 4/10 — Configuring Apache listen port {port}")

    listen_line = f"Listen 127.0.0.1:{port}"

    try:
        content = pathlib.Path(APACHE_PORTS_CONF).read_text(encoding="utf-8")
    except FileNotFoundError:
        content = ""

    if listen_line in content:
        log(f"  {listen_line} already present in ports.conf.", "OK")
        return

    log(f"  Appending: {listen_line}")
    new_block = textwrap.dedent(f"""
        {IDEMPOTENCY_TAG} — BEGIN investment_site
        {listen_line}
        {IDEMPOTENCY_TAG} — END investment_site
    """)
    if not dry_run:
        with open(APACHE_PORTS_CONF, "a", encoding="utf-8") as fh:
            fh.write(new_block)
    log("  Apache port configured.", "OK")


def step_write_site_files(cfg: dict, api_token: str, dry_run: bool, force: bool) -> None:
    """Step 5 — Write all PHP / CSS / configuration files for the site."""
    log("═" * 60)
    log("Step 5/10 — Writing website files")

    site_dir = cfg["site_dir"]
    ensure_dir(site_dir, mode=0o755, owner="www-data:www-data", dry_run=dry_run)
    ensure_dir(f"{site_dir}/inc",    mode=0o750, owner="www-data:www-data", dry_run=dry_run)
    ensure_dir(f"{site_dir}/css",    mode=0o755, owner="www-data:www-data", dry_run=dry_run)
    ensure_dir(f"{site_dir}/images", mode=0o755, owner="www-data:www-data", dry_run=dry_run)

    # ── Substitute placeholders into config.php ──────────────────────────────
    onion_url = cfg.get("onion_url", "http://pending.onion")
    config_php = (
        PHP_CONFIG
        .replace("PLACEHOLDER_SITE_NAME",    cfg["site_name"])
        .replace("PLACEHOLDER_TAGLINE",      cfg["tagline"])
        .replace("PLACEHOLDER_SITE_URL",     onion_url)
        .replace("PLACEHOLDER_CONTACT_EMAIL", cfg["contact_email"])
        .replace("PLACEHOLDER_INT_PORT",     str(ACCEPTXMR_INT_PORT))
        .replace("PLACEHOLDER_EXT_PORT",     str(ACCEPTXMR_EXT_PORT))
        .replace("PLACEHOLDER_API_TOKEN",    api_token)
    )

    files = {
        f"{site_dir}/inc/config.php":   (config_php,  0o640),
        f"{site_dir}/inc/header.php":   (PHP_HEADER,  0o644),
        f"{site_dir}/inc/footer.php":   (PHP_FOOTER,  0o644),
        f"{site_dir}/index.php":        (PHP_INDEX,   0o644),
        f"{site_dir}/about.php":        (PHP_ABOUT,   0o644),
        f"{site_dir}/portfolio.php":    (PHP_PORTFOLIO, 0o644),
        f"{site_dir}/team.php":         (PHP_TEAM,    0o644),
        f"{site_dir}/invest.php":       (PHP_INVEST,  0o644),
        f"{site_dir}/payment.php":      (PHP_PAYMENT, 0o644),
        f"{site_dir}/contact.php":      (PHP_CONTACT, 0o644),
        f"{site_dir}/css/style.css":    (SITE_CSS,    0o644),
        f"{site_dir}/.htaccess":        (HTACCESS,    0o644),
        f"{site_dir}/robots.txt":       (ROBOTS_TXT,  0o644),
    }

    for path, (content, mode) in files.items():
        write_file(path, content, mode=mode, dry_run=dry_run, force=force)

    # Set ownership of all site files to www-data
    if not dry_run:
        run(f"chown -R www-data:www-data {site_dir}", dry_run=dry_run)

    log("  Website files written.", "OK")


def step_create_vhost(cfg: dict, dry_run: bool, force: bool) -> None:
    """Step 6 — Create and enable the Apache vhost."""
    log("═" * 60)
    log("Step 6/10 — Creating Apache virtual host")

    port = cfg["apache_port"]
    site_dir = cfg["site_dir"]

    vhost_content = textwrap.dedent(f"""\
        {IDEMPOTENCY_TAG}
        <VirtualHost 127.0.0.1:{port}>
            ServerName  investment_site.local
            DocumentRoot {site_dir}

            <Directory {site_dir}>
                Options -Indexes -Includes +FollowSymLinks
                AllowOverride All
                Require all granted
            </Directory>

            # Deny access to inc/ directory via Apache (belt-and-suspenders)
            <Directory {site_dir}/inc>
                Require all denied
            </Directory>

            # PHP settings
            php_flag  display_errors Off
            php_flag  expose_php     Off
            php_value upload_max_filesize 2M
            php_value post_max_size       4M

            ErrorLog  ${{APACHE_LOG_DIR}}/investment_site_error.log
            CustomLog ${{APACHE_LOG_DIR}}/investment_site_access.log combined
        </VirtualHost>
    """)

    write_file(VHOST_CONF, vhost_content, mode=0o644, dry_run=dry_run, force=force)

    enabled_link = f"/etc/apache2/sites-enabled/investment_site.conf"
    if not os.path.islink(enabled_link):
        run("a2ensite investment_site", dry_run=dry_run)
    else:
        log("  Vhost already enabled.", "OK")

    log("  Apache vhost configured.", "OK")


def step_configure_tor(port: int, dry_run: bool) -> None:
    """Step 7 — Set up Tor v3 hidden service safely via torrc.d."""
    log("═" * 60)
    log("Step 7/10 — Configuring Tor hidden service")

    # 7a. Always back up torrc (once)
    backup_file(TORRC_PATH, TORRC_BAK_PATH, dry_run=dry_run)

    # 7b. Create /etc/tor/torrc.d/ if it does not exist
    ensure_dir(TORRC_D_DIR, mode=0o755, dry_run=dry_run)

    # 7c. Ensure %include line is in main torrc
    include_line = f"%include {TORRC_D_DIR}/*.conf"
    try:
        torrc_content = pathlib.Path(TORRC_PATH).read_text(encoding="utf-8")
    except FileNotFoundError:
        torrc_content = ""

    if include_line not in torrc_content:
        log(f"  Appending include directive to {TORRC_PATH}")
        append_block = textwrap.dedent(f"""

            {IDEMPOTENCY_TAG} — BEGIN
            # Load per-service Tor configuration fragments
            {include_line}
            {IDEMPOTENCY_TAG} — END
        """)
        if not dry_run:
            with open(TORRC_PATH, "a", encoding="utf-8") as fh:
                fh.write(append_block)
    else:
        log(f"  Include directive already present in {TORRC_PATH}.", "OK")

    # 7d. Write the hidden service config into torrc.d/
    tor_conf = textwrap.dedent(f"""\
        {IDEMPOTENCY_TAG}
        # Investment site hidden service — generated by deploy_investment_site.py
        HiddenServiceDir  {HIDDEN_SVC_DIR}
        HiddenServicePort 80 127.0.0.1:{port}
    """)

    if os.path.isfile(TOR_CONF_FILE) and not dry_run:
        existing = pathlib.Path(TOR_CONF_FILE).read_text(encoding="utf-8")
        if HIDDEN_SVC_DIR in existing:
            log(f"  Tor hidden service config already exists: {TOR_CONF_FILE}", "OK")
            return

    write_file(TOR_CONF_FILE, tor_conf, mode=0o644, dry_run=dry_run, force=True)

    # 7e. Create the hidden service directory with correct Tor ownership
    ensure_dir(HIDDEN_SVC_DIR, mode=0o700, dry_run=dry_run)
    if not dry_run:
        run(f"chown debian-tor:debian-tor {HIDDEN_SVC_DIR}", dry_run=dry_run, check=False)

    log("  Tor hidden service configured.", "OK")


def step_deploy_acceptxmr(cfg: dict, viewkey: str, api_token: str, dry_run: bool) -> None:
    """Step 8 — Deploy AcceptXMR-Server via Docker."""
    log("═" * 60)
    log("Step 8/10 — Deploying AcceptXMR-Server (Docker)")

    if cfg.get("skip_acceptxmr"):
        log("  --skip-acceptxmr set — skipping.", "WARN")
        return

    if not cfg.get("wallet_address"):
        log("  No --wallet-address provided — skipping AcceptXMR deployment.", "WARN")
        log("  Run again with --wallet-address and --viewkey to enable payments.", "WARN")
        return

    # 8a. Create config directory
    ensure_dir("/etc/xmrgateway",     mode=0o750, dry_run=dry_run)
    ensure_dir(ACCEPTXMR_DB_DIR,      mode=0o750, dry_run=dry_run)
    ensure_dir(ACCEPTXMR_CERT_DIR,    mode=0o750, dry_run=dry_run)

    # 8b. Write acceptxmr.yaml (non-secret configuration)
    restore_h = cfg.get("restore_height") or "null"
    yaml_content = textwrap.dedent(f"""\
        # AcceptXMR-Server configuration — generated by deploy_investment_site.py
        external-api:
          port: {ACCEPTXMR_EXT_PORT}
          ipv4: 127.0.0.1
          tls: null

        internal-api:
          port: {ACCEPTXMR_INT_PORT}
          ipv4: 127.0.0.1
          tls:
            cert: /cert/certificate.pem
            key:  /cert/privatekey.pem

        callback:
          queue-size: 1000
          max-retries: 50

        wallet:
          primary-address: {cfg['wallet_address']}
          account-index: 0
          restore-height: {restore_h}

        daemon:
          url: {cfg['xmr_daemon']}
          login: null
          rpc-timeout: 30
          connection-timeout: 20

        database:
          path: /AcceptXMR_DB/
          delete-expired: true

        logging:
          verbosity: INFO
    """)
    write_file(ACCEPTXMR_CONF, yaml_content, mode=0o640, dry_run=dry_run, force=True)

    # 8c. Write .env file with secrets (mode 0o600 — readable only by root)
    # NOTE: the Monero view key and API token must be persisted to disk for the
    # Docker container to access them.  The file is created with 0600 permissions.
    env_lines = [
        f"PRIVATE_VIEWKEY={viewkey}",
        f"INTERNAL_API_TOKEN={api_token}",
        "",
    ]
    env_text = "\n".join(env_lines)
    write_file(ACCEPTXMR_ENV, env_text, mode=0o600, dry_run=dry_run, force=True)

    # 8d. Generate a self-signed cert for the internal API if none exists
    cert_file = f"{ACCEPTXMR_CERT_DIR}/certificate.pem"
    key_file  = f"{ACCEPTXMR_CERT_DIR}/privatekey.pem"
    if not os.path.isfile(cert_file):
        log("  Generating self-signed TLS certificate for internal API.")
        run(
            f'openssl req -x509 -newkey rsa:4096 -keyout {key_file} '
            f'-out {cert_file} -days 3650 -nodes '
            f'-subj "/CN=acceptxmr.localhost" '
            f'-addext "subjectAltName=IP:127.0.0.1"',
            dry_run=dry_run,
        )
    else:
        log("  TLS certificate already exists — skipping.", "OK")

    # 8e. Write docker-compose.yml
    compose_content = textwrap.dedent(f"""\
        # AcceptXMR-Server — generated by deploy_investment_site.py
        services:
          acceptxmr:
            image: busyboredom/acceptxmr:latest
            restart: always
            network_mode: "host"
            volumes:
              - {ACCEPTXMR_DB_DIR}:/AcceptXMR_DB
              - {ACCEPTXMR_CERT_DIR}:/cert
              - {ACCEPTXMR_CONF}:/acceptxmr.yaml
            env_file: {ACCEPTXMR_ENV}
    """)
    write_file("/etc/xmrgateway/docker-compose.yml", compose_content,
               mode=0o640, dry_run=dry_run, force=True)

    # 8f. Write systemd service for AcceptXMR
    service_content = textwrap.dedent("""\
        [Unit]
        Description=AcceptXMR Monero Payment Gateway
        After=network-online.target docker.service
        Wants=network-online.target
        Requires=docker.service

        [Service]
        Type=simple
        WorkingDirectory=/etc/xmrgateway
        ExecStartPre=-/usr/bin/docker compose pull
        ExecStart=/usr/bin/docker compose up
        ExecStop=/usr/bin/docker compose down
        Restart=on-failure
        RestartSec=10

        [Install]
        WantedBy=multi-user.target
    """)
    write_file(ACCEPTXMR_SERVICE, service_content, mode=0o644, dry_run=dry_run, force=True)

    if not dry_run:
        run("systemctl daemon-reload")
        run("systemctl enable acceptxmr")
        run("systemctl restart acceptxmr", check=False)

    log("  AcceptXMR deployed.", "OK")


def step_start_services(dry_run: bool) -> None:
    """Step 9 — Reload / restart Apache and Tor."""
    log("═" * 60)
    log("Step 9/10 — Starting / reloading services")

    run("systemctl enable apache2", dry_run=dry_run)
    run("apache2ctl configtest",    dry_run=dry_run, check=False)
    run("systemctl restart apache2", dry_run=dry_run)
    log("  Apache restarted.", "OK")

    run("systemctl enable tor",     dry_run=dry_run)
    run("systemctl restart tor",    dry_run=dry_run)
    log("  Tor restarted.", "OK")


def step_get_onion_address(dry_run: bool) -> str:
    """Step 10 — Wait for Tor to generate the .onion hostname and return it."""
    log("═" * 60)
    log("Step 10/10 — Retrieving Tor .onion address")

    hostname_file = f"{HIDDEN_SVC_DIR}/hostname"

    if dry_run:
        return "<dry-run — .onion not available>"

    log("  Waiting for Tor to generate hidden service keys (up to 60 s)…")
    for _ in range(60):
        if os.path.isfile(hostname_file):
            try:
                onion = pathlib.Path(hostname_file).read_text(encoding="utf-8").strip()
                log(f"  .onion address: {onion}", "OK")
                return onion
            except OSError:
                pass
        time.sleep(1)

    log("  .onion hostname not yet available. Check /var/lib/tor/investment_site/hostname later.", "WARN")
    return "pending"


def print_summary(cfg: dict, onion: str) -> None:
    """Print a final deployment summary."""
    line = "═" * 60
    print(f"\n{line}")
    print("  DEPLOYMENT COMPLETE")
    print(line)
    print(f"  Site name    : {cfg['site_name']}")
    print(f"  Tagline      : {cfg['tagline']}")
    print(f"  Document root: {cfg['site_dir']}")
    print(f"  Apache port  : 127.0.0.1:{cfg['apache_port']}")
    print(f"  Onion address: http://{onion}")
    print(f"  AcceptXMR ext: http://127.0.0.1:{ACCEPTXMR_EXT_PORT}")
    print(f"  AcceptXMR int: https://127.0.0.1:{ACCEPTXMR_INT_PORT}")
    if cfg.get("wallet_address"):
        print(f"  XMR wallet   : {cfg['wallet_address'][:20]}…")
    print(f"  torrc backup : {TORRC_BAK_PATH}")
    print(f"  Tor conf     : {TOR_CONF_FILE}")
    print(f"  Vhost conf   : {VHOST_CONF}")
    print(line)
    print("  NEXT STEPS")
    print(line)
    print("  1. Visit your site over Tor: http://" + onion)
    print("  2. Set SITE_NAME and TAGLINE in " + cfg["site_dir"] + "/inc/config.php")
    print("  3. Update CONTACT_EMAIL in config.php with your real .onion email")
    if not cfg.get("wallet_address"):
        print("  4. Re-run with --wallet-address and --viewkey to enable payments")
    print("  5. Review Apache logs: /var/log/apache2/investment_site_*.log")
    print("  6. Review AcceptXMR logs: journalctl -u acceptxmr -f")
    print(line + "\n")


# ══════════════════════════════════════════════════════════════════════════════
#  ARGUMENT PARSING & MAIN
# ══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"deploy_investment_site.py v{SCRIPT_VERSION} — "
                    "Deploy a PHP crypto investment site on Ubuntu 20.04.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--wallet-address", metavar="ADDR",
                        help="Monero primary address")
    parser.add_argument("--viewkey", metavar="KEY",
                        help="Monero private view key",
                        default="")
    parser.add_argument("--api-token", metavar="TOKEN",
                        help="AcceptXMR internal API bearer token (auto-generated if omitted)")
    parser.add_argument("--site-name",    default=DEFAULT_SITE_NAME,
                        help=f"Investment firm name (default: {DEFAULT_SITE_NAME!r})")
    parser.add_argument("--tagline",      default=DEFAULT_TAGLINE,
                        help=f"Hero tagline (default: {DEFAULT_TAGLINE!r})")
    parser.add_argument("--apache-port",  type=int, default=DEFAULT_APACHE_PORT,
                        help=f"127.0.0.1 Apache listen port (default: {DEFAULT_APACHE_PORT})")
    parser.add_argument("--site-dir",     default=DEFAULT_SITE_DIR,
                        help=f"Apache DocumentRoot (default: {DEFAULT_SITE_DIR})")
    parser.add_argument("--contact-email", default=DEFAULT_CONTACT_EMAIL,
                        help="Contact e-mail shown on the site")
    parser.add_argument("--xmr-daemon",  default=DEFAULT_XMR_DAEMON,
                        help=f"Monero daemon URL (default: {DEFAULT_XMR_DAEMON})")
    parser.add_argument("--restore-height", type=int, default=None,
                        help="Wallet restore height for AcceptXMR (default: null)")
    parser.add_argument("--skip-acceptxmr", action="store_true",
                        help="Skip AcceptXMR Docker deployment")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Print every action without executing")
    parser.add_argument("--force",    action="store_true",
                        help="Re-create website files even if they already exist")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.dry_run:
        log("DRY-RUN mode — no changes will be made.", "WARN")

    # ── Separate non-secret config from credentials ────────────────────────────
    # api_token and viewkey are never placed in cfg to prevent them from
    # inadvertently being logged through generic cfg access patterns.
    api_token = args.api_token or secrets.token_hex(32)
    viewkey   = args.viewkey  # may be empty string if not provided

    cfg = {
        "site_name":      args.site_name,
        "tagline":        args.tagline,
        "apache_port":    args.apache_port,
        "site_dir":       args.site_dir,
        "contact_email":  args.contact_email,
        "xmr_daemon":     args.xmr_daemon,
        "wallet_address": args.wallet_address or "",
        "restore_height": args.restore_height,
        "skip_acceptxmr": args.skip_acceptxmr,
    }

    dry = args.dry_run
    force = args.force

    log(f"deploy_investment_site.py v{SCRIPT_VERSION} starting …", "INFO")
    log(f"  Site: {cfg['site_name']}  |  Port: {cfg['apache_port']}  |  Dir: {cfg['site_dir']}")

    step_check_prerequisites()
    step_install_packages(dry)
    step_enable_apache_modules(dry)
    step_configure_apache_port(cfg["apache_port"], dry)
    step_write_site_files(cfg, api_token, dry, force)
    step_create_vhost(cfg, dry, force)
    step_configure_tor(cfg["apache_port"], dry)
    step_deploy_acceptxmr(cfg, viewkey, api_token, dry)
    step_start_services(dry)
    onion = step_get_onion_address(dry)

    # Update config.php with the discovered .onion URL (idempotent re-write)
    if onion not in ("pending", "<dry-run — .onion not available>"):
        cfg["onion_url"] = f"http://{onion}"
        log("  Updating config.php with .onion URL …")
        step_write_site_files(cfg, api_token, dry, force=True)

    print_summary(cfg, onion)


if __name__ == "__main__":
    main()
