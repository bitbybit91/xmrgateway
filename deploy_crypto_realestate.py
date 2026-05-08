#!/usr/bin/env python3
"""
deploy_crypto_realestate.py — Production-ready deployment script for Crypto Real Estate Emporium
Deploys a PHP/SQLite website backed by the AcceptXMR (xmrgateway) Monero payment processor.

Usage:
    sudo python3 deploy_crypto_realestate.py [--view-key KEY] [--address ADDR]
        [--daemon-url URL] [--port PORT] [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import configparser
import logging
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_VERSION = "1.0.0"
LOG_FILE = "/var/log/crypto_realestate_deploy.log"
SITE_ROOT = "/var/www/crypto_realestate"
APACHE_CONF = "/etc/apache2/sites-available/crypto_realestate.conf"
APACHE_PORTS = "/etc/apache2/ports.conf"
TOR_TORRC = "/etc/tor/torrc"
TOR_HS_DIR = "/var/lib/tor/crypto_realestate"
TOR_HS_HOSTNAME = f"{TOR_HS_DIR}/hostname"
XMR_GATEWAY_DIR = "/opt/xmrgateway"
XMR_GATEWAY_REPO = "https://github.com/bitbybit91/xmrgateway"
XMR_GATEWAY_BRANCH = "copilot/update-website-updater-script"
XMR_YAML = f"{XMR_GATEWAY_DIR}/acceptxmr_site.yaml"
SYSTEMD_SERVICE = "/etc/systemd/system/acceptxmr.service"
CONFIG_DIR = "/etc/crypto_realestate"
CONFIG_FILE = f"{CONFIG_DIR}/config.ini"
DB_PATH = f"{SITE_ROOT}/data/properties.db"
DEFAULT_PORT = 8090
DEFAULT_DAEMON_URL = "http://node.xmr.to:18081"
DEFAULT_ADDRESS = (
    "4613YiHLM6JMH4zejMB2zJY5TwQCxL8p65ufw8kBP5yxX9itmuGLqp1dS4tkVoTxjyH3aYhYNrtGHbQzJQP5bFus3KHVdmf"
)
INTERNAL_API_PORT = 8082
EXTERNAL_API_PORT = 8083

REQUIRED_PACKAGES = [
    "apache2",
    "libapache2-mod-php",
    "php7.4",
    "php7.4-curl",
    "php7.4-gd",
    "php7.4-mbstring",
    "php7.4-xml",
    "php7.4-sqlite3",
    "tor",
    "git",
    "curl",
    "python3-pip",
    "sqlite3",
]

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logger = logging.getLogger("deploy_crypto_realestate")


def setup_logging(verbose: bool = False) -> None:
    """Configure file + console logging."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)

    try:
        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE)
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        logger.addHandler(fh)
    except PermissionError:
        logger.warning("Cannot write to %s — file logging disabled.", LOG_FILE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], *, check: bool = True, capture: bool = False,
        dry_run: bool = False, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Run a shell command with logging."""
    display = " ".join(cmd)
    logger.debug("RUN: %s", display)
    if dry_run:
        logger.info("[DRY-RUN] Would run: %s", display)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    result = subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        env={**os.environ, **(env or {})},
    )
    if capture and result.stdout:
        logger.debug("STDOUT: %s", result.stdout.strip())
    return result


def write_file(path: str, content: str, *, dry_run: bool = False) -> None:
    """Write content to a file, creating parent directories as needed."""
    logger.debug("WRITE: %s (%d bytes)", path, len(content))
    if dry_run:
        logger.info("[DRY-RUN] Would write %d bytes to %s", len(content), path)
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


# ---------------------------------------------------------------------------
# Phase 1: Pre-flight Checks
# ---------------------------------------------------------------------------

class SystemChecker:
    def __init__(self, port: int, dry_run: bool = False) -> None:
        self.port = port
        self.dry_run = dry_run
        self.tor_backup: Optional[str] = None

    def check_root(self) -> None:
        logger.info("Checking for root/sudo privileges…")
        if os.geteuid() != 0:
            logger.error("This script must be run as root (use sudo).")
            sys.exit(1)
        logger.info("Root check passed.")

    def check_ubuntu(self) -> None:
        logger.info("Checking Ubuntu version…")
        try:
            with open("/etc/os-release") as f:
                data = f.read()
            if "Ubuntu" not in data:
                logger.warning("Not running on Ubuntu — proceeding anyway.")
                return
            if "20.04" not in data and "22.04" not in data:
                logger.warning(
                    "Expected Ubuntu 20.04/22.04; detected different version — proceeding."
                )
                return
            logger.info("Ubuntu version check passed.")
        except FileNotFoundError:
            logger.warning("/etc/os-release not found — skipping OS check.")

    def detect_apache_vhosts(self) -> list[str]:
        logger.info("Detecting existing Apache vhosts…")
        sites_path = Path("/etc/apache2/sites-enabled")
        if not sites_path.exists():
            logger.info("Apache sites-enabled directory not found (Apache may not be installed yet).")
            return []
        vhosts = [p.name for p in sites_path.iterdir()]
        logger.info("Existing enabled vhosts: %s", vhosts or "(none)")
        return vhosts

    def backup_torrc(self) -> None:
        torrc = Path(TOR_TORRC)
        if not torrc.exists():
            logger.info("torrc not found — skipping backup.")
            return
        backup = f"{TOR_TORRC}.backup.{timestamp()}"
        logger.info("Backing up torrc → %s", backup)
        if not self.dry_run:
            shutil.copy2(TOR_TORRC, backup)
        self.tor_backup = backup
        logger.info("torrc backup created: %s", backup)

    def check_port_conflict(self) -> None:
        logger.info("Scanning for port conflicts on %d…", self.port)
        result = run(
            ["ss", "-tlnp", f"sport = :{self.port}"],
            check=False, capture=True, dry_run=self.dry_run,
        )
        if result.stdout and str(self.port) in result.stdout:
            logger.warning("Port %d appears to be in use:\n%s", self.port, result.stdout)
        else:
            logger.info("Port %d is available.", self.port)

    def check_internet(self) -> None:
        logger.info("Verifying internet connectivity…")
        try:
            urllib.request.urlopen("https://example.com", timeout=10)
            logger.info("Internet connectivity confirmed.")
        except Exception as exc:
            logger.warning("Internet check failed: %s — proceeding anyway.", exc)

    def run_all(self) -> None:
        self.check_root()
        self.check_ubuntu()
        self.detect_apache_vhosts()
        self.backup_torrc()
        self.check_port_conflict()
        self.check_internet()


# ---------------------------------------------------------------------------
# Phase 2: Dependency Installation
# ---------------------------------------------------------------------------

class DependencyInstaller:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def _is_installed(self, pkg: str) -> bool:
        result = run(
            ["dpkg", "-s", pkg], check=False, capture=True, dry_run=False
        )
        return result.returncode == 0

    def install_packages(self) -> None:
        logger.info("Updating apt package lists…")
        run(["apt-get", "update", "-qq"], dry_run=self.dry_run)

        missing = [p for p in REQUIRED_PACKAGES if not self._is_installed(p)]
        if not missing:
            logger.info("All required apt packages are already installed.")
        else:
            logger.info("Installing missing packages: %s", missing)
            run(
                ["apt-get", "install", "-y", "-qq"] + missing,
                dry_run=self.dry_run,
            )

    def install_rust(self) -> None:
        logger.info("Checking Rust toolchain…")
        result = run(["which", "cargo"], check=False, capture=True, dry_run=False)
        if result.returncode == 0:
            logger.info("Rust/cargo already installed: %s", result.stdout.strip())
            return
        logger.info("Installing Rust via rustup…")
        if not self.dry_run:
            rs = subprocess.run(
                ["curl", "--proto", "=https", "--tlsv1.2", "-sSf",
                 "https://sh.rustup.rs"],
                capture_output=True, text=True, check=True,
            )
            subprocess.run(
                ["sh", "-s", "--", "-y", "--no-modify-path"],
                input=rs.stdout, text=True, check=True,
            )
        logger.info("Rust installed.")

    def run_all(self) -> None:
        self.install_packages()
        self.install_rust()


# ---------------------------------------------------------------------------
# Phase 3: Clone & Setup xmrgateway
# ---------------------------------------------------------------------------

class XMRGatewaySetup:
    def __init__(
        self,
        view_key: str,
        address: str,
        daemon_url: str,
        dry_run: bool = False,
    ) -> None:
        self.view_key = view_key
        self.address = address
        self.daemon_url = daemon_url
        self.dry_run = dry_run

    def clone_repo(self) -> None:
        gw = Path(XMR_GATEWAY_DIR)
        if gw.exists():
            logger.info("xmrgateway directory already exists at %s — skipping clone.", XMR_GATEWAY_DIR)
            run(["git", "-C", XMR_GATEWAY_DIR, "fetch", "--all"],
                dry_run=self.dry_run)
        else:
            logger.info("Cloning xmrgateway → %s", XMR_GATEWAY_DIR)
            run(
                ["git", "clone", XMR_GATEWAY_REPO, XMR_GATEWAY_DIR],
                dry_run=self.dry_run,
            )
        logger.info("Checking out branch %s…", XMR_GATEWAY_BRANCH)
        run(
            ["git", "-C", XMR_GATEWAY_DIR, "checkout", XMR_GATEWAY_BRANCH],
            dry_run=self.dry_run,
        )

    def build(self) -> None:
        logger.info("Building xmrgateway with cargo build --release (this may take a while)…")
        cargo_home = os.path.expanduser("~/.cargo/bin")
        env_path = f"{cargo_home}:{os.environ.get('PATH', '')}"
        run(
            ["cargo", "build", "--release"],
            dry_run=self.dry_run,
            env={"PATH": env_path, "HOME": os.environ.get("HOME", "/root")},
        )
        logger.info("Build complete.")

    def write_yaml(self) -> None:
        logger.info("Writing acceptxmr_site.yaml…")
        yaml_content = f"""# AcceptXMR configuration for Crypto Real Estate Emporium
# Generated by deploy_crypto_realestate.py on {datetime.now().isoformat()}

external-api:
  port: {EXTERNAL_API_PORT}
  ipv4: 127.0.0.1
  tls: null
  static_dir: server/static/

internal-api:
  port: {INTERNAL_API_PORT}
  ipv4: 127.0.0.1
  tls: null
  static_dir: server/static/

callback:
  queue-size: 1000
  max-retries: 50

wallet:
  primary-address: {self.address}
  account-index: 0
  restore-height: null

daemon:
  url: {self.daemon_url}
  login: null
  rpc-timeout: 30
  connection-timeout: 20

database:
  path: {XMR_GATEWAY_DIR}/AcceptXMR_DB/
  delete-expired: true

logging:
  verbosity: INFO
"""
        write_file(XMR_YAML, yaml_content, dry_run=self.dry_run)

    def write_systemd_service(self) -> None:
        logger.info("Writing systemd acceptxmr.service…")
        view_key_value = self.view_key if self.view_key else "REPLACE_WITH_VIEW_KEY"
        service_content = f"""[Unit]
Description=AcceptXMR Monero Payment Gateway
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=acceptxmr
Group=acceptxmr
WorkingDirectory={XMR_GATEWAY_DIR}
ExecStart={XMR_GATEWAY_DIR}/target/release/acceptxmr-server --config {XMR_YAML}
Environment=PRIVATE_VIEWKEY={view_key_value}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=acceptxmr
ProtectSystem=strict
ReadWritePaths={XMR_GATEWAY_DIR}/AcceptXMR_DB
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
"""
        write_file(SYSTEMD_SERVICE, service_content, dry_run=self.dry_run)

        if not self.dry_run:
            # Create dedicated system user if absent
            run(
                ["id", "acceptxmr"],
                check=False, capture=True, dry_run=False,
            )
            result = run(["id", "acceptxmr"], check=False, capture=True)
            if result.returncode != 0:
                run(
                    ["useradd", "--system", "--no-create-home",
                     "--shell", "/usr/sbin/nologin", "acceptxmr"],
                    dry_run=False,
                )
            run(["chown", "-R", "acceptxmr:acceptxmr", XMR_GATEWAY_DIR],
                dry_run=self.dry_run)
            run(["systemctl", "daemon-reload"], dry_run=self.dry_run)
            run(["systemctl", "enable", "acceptxmr"], dry_run=self.dry_run)

    def run_all(self) -> None:
        self.clone_repo()
        self.build()
        self.write_yaml()
        self.write_systemd_service()


# ---------------------------------------------------------------------------
# Phase 4-6: Website Builder
# ---------------------------------------------------------------------------

CSS_CONTENT = """\
/* Crypto Real Estate Emporium — Main Stylesheet */
/* Dark theme: bg #1a1a2e, sidebar #16213e, accent gold #D4AF37 */

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg:        #1a1a2e;
  --surface:   #16213e;
  --surface2:  #0f3460;
  --accent:    #D4AF37;
  --accent2:   #e8c84a;
  --text:      #e0e0e0;
  --text-muted:#9e9e9e;
  --danger:    #e74c3c;
  --success:   #2ecc71;
  --warning:   #f39c12;
  --radius:    8px;
  --shadow:    0 4px 20px rgba(0,0,0,0.4);
}

html { scroll-behavior: smooth; }

body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Segoe UI', system-ui, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

a { color: var(--accent); text-decoration: none; }
a:hover { color: var(--accent2); text-decoration: underline; }

/* ── Header ── */
header {
  background: var(--surface);
  border-bottom: 2px solid var(--accent);
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow);
}

.header-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.logo {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: .03em;
  white-space: nowrap;
}
.logo:hover { text-decoration: none; color: var(--accent2); }

nav { display: flex; flex-wrap: wrap; gap: .25rem; }
nav a {
  color: var(--text);
  padding: .4rem .75rem;
  border-radius: var(--radius);
  font-size: .9rem;
  transition: background .2s, color .2s;
}
nav a:hover { background: var(--surface2); color: var(--accent); text-decoration: none; }

/* ── Hero ── */
.hero {
  background: linear-gradient(135deg, #0f3460 0%, #16213e 50%, #1a1a2e 100%);
  padding: 5rem 1.5rem;
  text-align: center;
  border-bottom: 1px solid var(--surface2);
}
.hero h1 {
  font-size: clamp(2rem, 5vw, 3.5rem);
  color: var(--accent);
  margin-bottom: 1rem;
  font-weight: 800;
  text-shadow: 0 2px 8px rgba(0,0,0,.5);
}
.hero p {
  font-size: 1.15rem;
  color: var(--text-muted);
  max-width: 600px;
  margin: 0 auto 2rem;
}
.btn {
  display: inline-block;
  padding: .75rem 2rem;
  border-radius: var(--radius);
  font-weight: 600;
  transition: transform .15s, box-shadow .15s;
  cursor: pointer;
  border: none;
  font-size: 1rem;
}
.btn:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,.4); text-decoration: none; }
.btn-primary { background: var(--accent); color: #1a1a2e; }
.btn-primary:hover { background: var(--accent2); color: #1a1a2e; }
.btn-outline { background: transparent; color: var(--accent); border: 2px solid var(--accent); }
.btn-outline:hover { background: var(--accent); color: #1a1a2e; }
.btn-danger { background: var(--danger); color: #fff; }

/* ── Main layout ── */
main { flex: 1; max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; width: 100%; }

/* ── Section headings ── */
.section-title {
  font-size: 1.75rem;
  color: var(--accent);
  margin-bottom: 1.5rem;
  border-bottom: 2px solid var(--surface2);
  padding-bottom: .5rem;
}

/* ── Category pills ── */
.category-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 3rem;
}
.category-card {
  background: var(--surface);
  border: 1px solid var(--surface2);
  border-radius: var(--radius);
  padding: 1.5rem 1rem;
  text-align: center;
  transition: border-color .2s, transform .2s;
  display: block;
  color: var(--text);
}
.category-card:hover {
  border-color: var(--accent);
  transform: translateY(-3px);
  text-decoration: none;
  color: var(--accent);
}
.category-card .cat-icon { font-size: 2rem; margin-bottom: .5rem; }
.category-card .cat-name { font-weight: 600; font-size: .95rem; }

/* ── Property grid ── */
.property-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1.5rem;
  margin-bottom: 3rem;
}

.property-card {
  background: var(--surface);
  border: 1px solid var(--surface2);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow .2s, transform .2s;
  display: flex;
  flex-direction: column;
}
.property-card:hover {
  box-shadow: 0 8px 30px rgba(212,175,55,.15);
  transform: translateY(-4px);
}
.property-card img {
  width: 100%;
  height: 200px;
  object-fit: cover;
  background: var(--surface2);
}
.property-card .card-body {
  padding: 1.25rem;
  flex: 1;
  display: flex;
  flex-direction: column;
}
.property-card .card-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin-bottom: .35rem;
  color: var(--text);
}
.property-card .card-location {
  font-size: .85rem;
  color: var(--text-muted);
  margin-bottom: .75rem;
}
.property-card .card-price {
  margin-bottom: .75rem;
}
.price-xmr {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--accent);
}
.price-usd {
  font-size: .85rem;
  color: var(--text-muted);
  margin-left: .4rem;
}
.card-specs {
  display: flex;
  gap: 1rem;
  font-size: .82rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
  flex-wrap: wrap;
}
.card-specs span::before { margin-right: .25rem; }
.card-footer { margin-top: auto; padding-top: .75rem; }
.card-footer .btn { width: 100%; text-align: center; }

/* ── Badge ── */
.badge {
  display: inline-block;
  padding: .2rem .6rem;
  border-radius: 20px;
  font-size: .75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .05em;
}
.badge-category { background: var(--surface2); color: var(--accent); }
.badge-status-available { background: rgba(46,204,113,.15); color: var(--success); }
.badge-status-sold { background: rgba(231,76,60,.15); color: var(--danger); }
.badge-status-pending { background: rgba(243,156,18,.15); color: var(--warning); }

/* ── Property detail ── */
.property-detail { display: grid; grid-template-columns: 2fr 1fr; gap: 2rem; }
.property-detail img { width: 100%; border-radius: var(--radius); border: 1px solid var(--surface2); }
.detail-sidebar { background: var(--surface); border-radius: var(--radius); padding: 1.5rem; align-self: start; }
.detail-sidebar .price-xmr { font-size: 1.8rem; display: block; margin-bottom: .25rem; }
.specs-table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
.specs-table td { padding: .6rem .75rem; border-bottom: 1px solid var(--surface2); font-size: .9rem; }
.specs-table td:first-child { color: var(--text-muted); width: 45%; }

/* ── Forms ── */
.form-card {
  background: var(--surface);
  border: 1px solid var(--surface2);
  border-radius: var(--radius);
  padding: 2rem;
  max-width: 560px;
}
.form-group { margin-bottom: 1.25rem; }
.form-group label { display: block; margin-bottom: .4rem; font-size: .9rem; color: var(--text-muted); }
.form-group input, .form-group textarea, .form-group select {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--surface2);
  color: var(--text);
  border-radius: var(--radius);
  padding: .65rem .9rem;
  font-size: 1rem;
  font-family: inherit;
}
.form-group input:focus, .form-group textarea:focus {
  outline: none;
  border-color: var(--accent);
}

/* ── Checkout / QR ── */
.checkout-box {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 2rem;
  max-width: 640px;
  margin: 0 auto;
  border: 1px solid var(--surface2);
}
.checkout-box .qr-code { text-align: center; margin: 1.5rem 0; }
.checkout-box .qr-code img { border: 6px solid #fff; border-radius: 4px; }
.address-box {
  background: var(--bg);
  border: 1px solid var(--surface2);
  border-radius: var(--radius);
  padding: .75rem 1rem;
  font-family: monospace;
  font-size: .82rem;
  word-break: break-all;
  color: var(--accent);
  margin: .75rem 0;
}

/* ── Status indicator ── */
.status-box { text-align: center; padding: 3rem 1.5rem; }
.status-icon { font-size: 4rem; margin-bottom: 1rem; }
.status-pending .status-icon::before { content: '⏳'; }
.status-confirming .status-icon::before { content: '🔄'; }
.status-paid .status-icon::before { content: '✅'; }
.status-expired .status-icon::before { content: '❌'; }

/* ── FAQ / Details ── */
details { border: 1px solid var(--surface2); border-radius: var(--radius); margin-bottom: .75rem; }
summary {
  padding: 1rem 1.25rem;
  cursor: pointer;
  font-weight: 600;
  color: var(--accent);
  list-style: none;
  user-select: none;
}
summary::before { content: '+ '; }
details[open] summary::before { content: '− '; }
details .faq-answer { padding: 0 1.25rem 1.25rem; color: var(--text-muted); line-height: 1.7; }

/* ── Alert boxes ── */
.alert { padding: 1rem 1.25rem; border-radius: var(--radius); margin-bottom: 1rem; }
.alert-info { background: rgba(15,52,96,.6); border: 1px solid var(--surface2); }
.alert-success { background: rgba(46,204,113,.1); border: 1px solid var(--success); color: var(--success); }
.alert-warning { background: rgba(243,156,18,.1); border: 1px solid var(--warning); color: var(--warning); }
.alert-danger { background: rgba(231,76,60,.1); border: 1px solid var(--danger); color: var(--danger); }

/* ── Footer ── */
footer {
  background: var(--surface);
  border-top: 2px solid var(--accent);
  padding: 2rem 1.5rem;
  text-align: center;
  color: var(--text-muted);
  font-size: .9rem;
}
.footer-inner { max-width: 1200px; margin: 0 auto; }
.xmr-badge {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  background: rgba(212,175,55,.1);
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: .3rem .75rem;
  border-radius: 20px;
  font-size: .82rem;
  font-weight: 600;
  margin-bottom: .75rem;
}
.footer-links { margin: .75rem 0; display: flex; justify-content: center; gap: 1.5rem; flex-wrap: wrap; }
.footer-links a { color: var(--text-muted); font-size: .88rem; }
.footer-links a:hover { color: var(--accent); }

/* ── Blog ── */
.blog-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; }
.blog-card { background: var(--surface); border: 1px solid var(--surface2); border-radius: var(--radius); padding: 1.5rem; }
.blog-card h3 { color: var(--accent); margin-bottom: .5rem; }
.blog-card .blog-meta { font-size: .82rem; color: var(--text-muted); margin-bottom: .75rem; }
.blog-card p { color: var(--text-muted); font-size: .92rem; line-height: 1.6; }

/* ── About / Content pages ── */
.content-page { max-width: 800px; }
.content-page h2 { color: var(--accent); margin: 1.5rem 0 .75rem; }
.content-page p { color: var(--text-muted); margin-bottom: 1rem; line-height: 1.75; }
.content-page ul { margin: .5rem 0 1rem 1.5rem; color: var(--text-muted); line-height: 1.75; }

/* ── Responsive ── */
@media (max-width: 900px) {
  .property-grid { grid-template-columns: repeat(2, 1fr); }
  .property-detail { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
  .property-grid { grid-template-columns: 1fr; }
  .category-grid { grid-template-columns: repeat(2, 1fr); }
  nav { display: none; }
}
"""

HEADER_PHP = """\
<?php
// Reusable header — includes nav links
$site_name = 'Crypto Real Estate Emporium';
$nav_links = [
    'Home'       => '/index.php',
    'Properties' => '/index.php?view=all',
    'Categories' => '#categories',
    'About'      => '/about.php',
    'FAQ'        => '/faq.php',
    'Contact'    => '/contact.php',
];
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title><?= htmlspecialchars($page_title ?? $site_name) ?></title>
  <link rel="stylesheet" href="/assets/css/style.css">
</head>
<body>
<header>
  <div class="header-inner">
    <a href="/index.php" class="logo"><?= htmlspecialchars($site_name) ?></a>
    <nav>
      <?php foreach ($nav_links as $label => $href): ?>
        <a href="<?= htmlspecialchars($href) ?>"><?= htmlspecialchars($label) ?></a>
      <?php endforeach; ?>
    </nav>
  </div>
</header>
"""

FOOTER_PHP = """\
<?php
// Reusable footer
$current_year = date('Y');
?>
<footer>
  <div class="footer-inner">
    <div class="xmr-badge">&#9679; Powered by Monero (XMR)</div>
    <div class="footer-links">
      <a href="/index.php">Home</a>
      <a href="/about.php">About</a>
      <a href="/faq.php">FAQ</a>
      <a href="/sell.php">Sell Property</a>
      <a href="/contact.php">Contact</a>
      <a href="/blog.php">Blog</a>
    </div>
    <p class="privacy-notice">
      Your privacy is protected. All transactions are processed via Monero for
      maximum financial privacy. No personal data is stored beyond your invoice email.
    </p>
    <p>&copy; <?= $current_year ?> Crypto Real Estate Emporium. All rights reserved.</p>
  </div>
</footer>
</body>
</html>
"""

CONFIG_PHP = f"""\
<?php
define('DB_PATH',                 dirname(__DIR__) . '/data/properties.db');
define('XMR_INTERNAL_API',        'http://127.0.0.1:{INTERNAL_API_PORT}');
define('XMR_EXTERNAL_API',        'http://127.0.0.1:{EXTERNAL_API_PORT}');
define('SITE_NAME',               'Crypto Real Estate Emporium');
define('CONFIRMATIONS_REQUIRED',  1);
define('INVOICE_EXPIRY_SECONDS',  3600);
define('LOG_PATH',                dirname(__DIR__) . '/logs/app.log');
"""

DB_PHP = """\
<?php
require_once __DIR__ . '/config.php';

function get_db(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $pdo = new PDO('sqlite:' . DB_PATH);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    }
    return $pdo;
}

function get_properties(string $category = '', int $limit = 0): array {
    $db = get_db();
    $sql = "SELECT p.*, c.name AS category_name FROM properties p
            LEFT JOIN categories c ON p.category = c.slug
            WHERE p.status = 'available'";
    $params = [];
    if ($category !== '') {
        $sql .= " AND p.category = :cat";
        $params[':cat'] = $category;
    }
    $sql .= " ORDER BY p.created_at DESC";
    if ($limit > 0) {
        $sql .= " LIMIT :lim";
    }
    $stmt = $db->prepare($sql);
    if ($limit > 0) {
        $stmt->bindValue(':lim', $limit, PDO::PARAM_INT);
    }
    foreach ($params as $k => $v) {
        $stmt->bindValue($k, $v);
    }
    $stmt->execute();
    return $stmt->fetchAll();
}

function get_property(int $id): ?array {
    $db = get_db();
    $stmt = $db->prepare(
        "SELECT p.*, c.name AS category_name FROM properties p
         LEFT JOIN categories c ON p.category = c.slug
         WHERE p.id = :id LIMIT 1"
    );
    $stmt->execute([':id' => $id]);
    $row = $stmt->fetch();
    return $row !== false ? $row : null;
}

function get_categories(): array {
    $db = get_db();
    return $db->query("SELECT * FROM categories ORDER BY name")->fetchAll();
}

function create_investment(int $property_id, string $email,
                            float $amount_xmr, string $invoice_id): int {
    $db = get_db();
    $stmt = $db->prepare(
        "INSERT INTO investments (property_id, investor_email, amount_xmr, invoice_id, status, created_at)
         VALUES (:pid, :email, :amt, :inv, 'pending', datetime('now'))"
    );
    $stmt->execute([
        ':pid'   => $property_id,
        ':email' => $email,
        ':amt'   => $amount_xmr,
        ':inv'   => $invoice_id,
    ]);
    return (int)$db->lastInsertId();
}

function create_invoice_record(string $xmr_invoice_id, string $address,
                                int $piconeros, string $expires_at): int {
    $db = get_db();
    $stmt = $db->prepare(
        "INSERT INTO invoices (xmr_invoice_id, address, amount, confirmations_required,
                               status, created_at, expires_at)
         VALUES (:inv, :addr, :amt, :conf, 'pending', datetime('now'), :exp)"
    );
    $stmt->execute([
        ':inv'  => $xmr_invoice_id,
        ':addr' => $address,
        ':amt'  => $piconeros,
        ':conf' => CONFIRMATIONS_REQUIRED,
        ':exp'  => $expires_at,
    ]);
    return (int)$db->lastInsertId();
}

function get_invoice_record(string $invoice_id): ?array {
    $db = get_db();
    $stmt = $db->prepare(
        "SELECT * FROM invoices WHERE xmr_invoice_id = :id LIMIT 1"
    );
    $stmt->execute([':id' => $invoice_id]);
    $row = $stmt->fetch();
    return $row !== false ? $row : null;
}

function update_invoice_status(string $invoice_id, string $status): void {
    $db = get_db();
    $stmt = $db->prepare(
        "UPDATE invoices SET status = :s WHERE xmr_invoice_id = :id"
    );
    $stmt->execute([':s' => $status, ':id' => $invoice_id]);
}
"""

XMR_API_PHP = """\
<?php
require_once __DIR__ . '/config.php';

function xmr_curl(string $method, string $endpoint, ?array $body = null): ?array {
    $url = XMR_INTERNAL_API . $endpoint;
    $ch  = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 10,
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json', 'Accept: application/json'],
    ]);
    if ($method === 'POST') {
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($body));
    }
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($response === false || $http_code < 200 || $http_code >= 300) {
        error_log('[xmr_api] Request failed: ' . $method . ' ' . $url .
                  ' HTTP ' . $http_code);
        return null;
    }
    return json_decode($response, true);
}

/**
 * Create a new XMR invoice.
 * AcceptXMR internal API: POST /invoice
 * Body: {"piconeros": INT, "description": "...", "callback_url": "..."}
 *
 * @param  int    $piconeros        Amount in piconeros (1 XMR = 1e12 piconeros).
 * @param  string $description      Human-readable description.
 * @param  string $callback_url     Optional webhook URL.
 * @return array|null               Decoded JSON response or null on failure.
 */
function create_invoice(int $piconeros, string $description,
                         string $callback_url = ''): ?array {
    return xmr_curl('POST', '/invoice', [
        'piconeros'    => $piconeros,
        'description'  => $description,
        'callback_url' => $callback_url,
    ]);
}

/**
 * Fetch current invoice status.
 * AcceptXMR internal API: GET /invoice/{id}
 *
 * @param  string $invoice_id  Invoice ID returned by create_invoice().
 * @return array|null
 */
function get_invoice_status(string $invoice_id): ?array {
    return xmr_curl('GET', '/invoice/' . urlencode($invoice_id));
}

/**
 * List all invoices (admin use).
 * AcceptXMR internal API: GET /invoices
 */
function list_invoices(): ?array {
    return xmr_curl('GET', '/invoices');
}
"""

FUNCTIONS_PHP = """\
<?php
/**
 * Convert XMR to piconeros (1 XMR = 1,000,000,000,000 piconeros).
 */
function xmr_to_piconeros(float $xmr): int {
    return (int)round($xmr * 1e12);
}

/**
 * Format piconeros as human-readable XMR string.
 */
function format_xmr(int $piconeros): string {
    return number_format($piconeros / 1e12, 4) . ' XMR';
}

/**
 * Format USD price.
 */
function format_price_usd(float $usd): string {
    return '$' . number_format($usd, 0);
}

/**
 * Sanitize user input for output.
 */
function sanitize(string $input): string {
    return htmlspecialchars(strip_tags(trim($input)), ENT_QUOTES, 'UTF-8');
}

/**
 * Redirect and exit.
 */
function redirect(string $url): void {
    header('Location: ' . $url);
    exit;
}

/**
 * Return a placeholder image URL for a property.
 */
function property_image(string $image_url): string {
    if ($image_url && filter_var($image_url, FILTER_VALIDATE_URL)) {
        return htmlspecialchars($image_url);
    }
    return 'https://via.placeholder.com/600x400/16213e/D4AF37?text=Property';
}

/**
 * Log an application event.
 */
function app_log(string $message, string $level = 'INFO'): void {
    $line = '[' . date('Y-m-d H:i:s') . '] [' . $level . '] ' . $message . PHP_EOL;
    @file_put_contents(LOG_PATH, $line, FILE_APPEND | LOCK_EX);
}

/**
 * Return CSS class for invoice status.
 */
function status_class(string $status): string {
    $map = [
        'pending'    => 'warning',
        'confirming' => 'info',
        'paid'       => 'success',
        'expired'    => 'danger',
    ];
    return 'alert-' . ($map[$status] ?? 'info');
}
"""

INDEX_PHP = """\
<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/functions.php';

$page_title = 'Home — Crypto Real Estate Emporium';
$filter_cat = isset($_GET['category']) ? trim($_GET['category']) : '';
$view_all   = isset($_GET['view']) && $_GET['view'] === 'all';

$categories = get_categories();
$properties = get_properties($filter_cat);
$recent     = get_properties('', 4);

include __DIR__ . '/../includes/header.php';
?>

<?php if (!$view_all && $filter_cat === ''): ?>
<section class="hero">
  <h1>Invest in Real Estate with Monero</h1>
  <p>Browse exclusive properties worldwide and purchase with complete financial
     privacy using the Monero (XMR) cryptocurrency.</p>
  <a href="/index.php?view=all" class="btn btn-primary">Browse All Properties</a>
  &nbsp;
  <a href="/about.php" class="btn btn-outline">Learn More</a>
</section>
<?php endif; ?>

<main>

<?php if (!$view_all && $filter_cat === ''): ?>
<!-- Category pills -->
<section id="categories">
  <h2 class="section-title">Browse by Category</h2>
  <div class="category-grid">
    <a href="/index.php?category=mansion" class="category-card">
      <div class="cat-icon">🏛️</div>
      <div class="cat-name">Mansions</div>
    </a>
    <a href="/index.php?category=apartment" class="category-card">
      <div class="cat-icon">🏢</div>
      <div class="cat-name">Apartments</div>
    </a>
    <a href="/index.php?category=villa" class="category-card">
      <div class="cat-icon">🏖️</div>
      <div class="cat-name">Villas</div>
    </a>
    <a href="/index.php?category=land" class="category-card">
      <div class="cat-icon">🌿</div>
      <div class="cat-name">Land</div>
    </a>
    <a href="/index.php?category=commercial" class="category-card">
      <div class="cat-icon">🏗️</div>
      <div class="cat-name">Commercial</div>
    </a>
  </div>
</section>

<!-- Recently Added -->
<section>
  <h2 class="section-title">Recently Added</h2>
  <div class="property-grid">
    <?php foreach ($recent as $prop): ?>
    <div class="property-card">
      <img src="<?= property_image($prop['image_url']) ?>"
           alt="<?= sanitize($prop['title']) ?>">
      <div class="card-body">
        <div>
          <span class="badge badge-category"><?= sanitize($prop['category_name'] ?? $prop['category']) ?></span>
        </div>
        <div class="card-title"><?= sanitize($prop['title']) ?></div>
        <div class="card-location">📍 <?= sanitize($prop['location']) ?></div>
        <div class="card-price">
          <span class="price-xmr"><?= format_xmr(xmr_to_piconeros((float)$prop['price_xmr'])) ?></span>
          <span class="price-usd"><?= format_price_usd((float)$prop['price_usd']) ?></span>
        </div>
        <div class="card-specs">
          <span>🛏 <?= (int)$prop['bedrooms'] ?> bd</span>
          <span>🚿 <?= (int)$prop['bathrooms'] ?> ba</span>
          <span>📐 <?= number_format((int)$prop['sqft']) ?> sqft</span>
        </div>
        <div class="card-footer">
          <a href="/property.php?id=<?= (int)$prop['id'] ?>" class="btn btn-primary">View Property</a>
        </div>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
</section>
<?php endif; ?>

<!-- All / filtered properties -->
<section>
  <h2 class="section-title">
    <?php if ($filter_cat !== ''): ?>
      <?php foreach ($categories as $cat): if ($cat['slug'] === $filter_cat): ?>
        <?= sanitize($cat['name']) ?> Properties
      <?php endif; endforeach; ?>
    <?php else: ?>
      All Properties
    <?php endif; ?>
    <a href="/index.php" style="font-size:.75rem;margin-left:1rem;">← Back to Home</a>
  </h2>
  <?php if (empty($properties)): ?>
    <div class="alert alert-info">No properties found in this category.</div>
  <?php else: ?>
  <div class="property-grid">
    <?php foreach ($properties as $prop): ?>
    <div class="property-card">
      <img src="<?= property_image($prop['image_url']) ?>"
           alt="<?= sanitize($prop['title']) ?>">
      <div class="card-body">
        <div>
          <span class="badge badge-category"><?= sanitize($prop['category_name'] ?? $prop['category']) ?></span>
          <span class="badge badge-status-<?= sanitize($prop['status']) ?>"><?= sanitize($prop['status']) ?></span>
        </div>
        <div class="card-title"><?= sanitize($prop['title']) ?></div>
        <div class="card-location">📍 <?= sanitize($prop['location']) ?></div>
        <div class="card-price">
          <span class="price-xmr"><?= format_xmr(xmr_to_piconeros((float)$prop['price_xmr'])) ?></span>
          <span class="price-usd"><?= format_price_usd((float)$prop['price_usd']) ?></span>
        </div>
        <div class="card-specs">
          <span>🛏 <?= (int)$prop['bedrooms'] ?> bd</span>
          <span>🚿 <?= (int)$prop['bathrooms'] ?> ba</span>
          <span>📐 <?= number_format((int)$prop['sqft']) ?> sqft</span>
        </div>
        <div class="card-footer">
          <a href="/property.php?id=<?= (int)$prop['id'] ?>" class="btn btn-primary">View Property</a>
        </div>
      </div>
    </div>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>
</section>

</main>

<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

PROPERTY_PHP = """\
<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/functions.php';

$id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
$property = $id > 0 ? get_property($id) : null;

if ($property === null) {
    http_response_code(404);
    $page_title = 'Property Not Found';
    include __DIR__ . '/../includes/header.php';
    echo '<main><div class="alert alert-danger">Property not found. '
       . '<a href="/index.php">Back to listings</a></div></main>';
    include __DIR__ . '/../includes/footer.php';
    exit;
}

$page_title = sanitize($property['title']) . ' — Crypto Real Estate Emporium';
include __DIR__ . '/../includes/header.php';
?>
<main>
  <div class="property-detail">
    <div class="detail-main">
      <img src="<?= property_image($property['image_url']) ?>"
           alt="<?= sanitize($property['title']) ?>">
      <h1 style="margin:1.5rem 0 .5rem;font-size:1.75rem;color:var(--accent)">
        <?= sanitize($property['title']) ?>
      </h1>
      <div style="color:var(--text-muted);margin-bottom:1rem">
        📍 <?= sanitize($property['location']) ?>
        &nbsp;|&nbsp;
        <span class="badge badge-category"><?= sanitize($property['category_name'] ?? $property['category']) ?></span>
        &nbsp;
        <span class="badge badge-status-<?= sanitize($property['status']) ?>"><?= sanitize($property['status']) ?></span>
      </div>
      <p style="color:var(--text-muted);line-height:1.75;margin-bottom:1.5rem">
        <?= nl2br(sanitize($property['description'])) ?>
      </p>
      <h2 class="section-title">Property Specifications</h2>
      <table class="specs-table">
        <tr><td>Bedrooms</td><td><?= (int)$property['bedrooms'] ?></td></tr>
        <tr><td>Bathrooms</td><td><?= (int)$property['bathrooms'] ?></td></tr>
        <tr><td>Size</td><td><?= number_format((int)$property['sqft']) ?> sqft</td></tr>
        <tr><td>Category</td><td><?= sanitize($property['category_name'] ?? $property['category']) ?></td></tr>
        <tr><td>Status</td><td><?= sanitize($property['status']) ?></td></tr>
        <tr><td>Listed</td><td><?= sanitize($property['created_at']) ?></td></tr>
      </table>
    </div>
    <div class="detail-sidebar">
      <span class="price-xmr"><?= format_xmr(xmr_to_piconeros((float)$property['price_xmr'])) ?></span>
      <div style="color:var(--text-muted);margin-bottom:1.5rem">
        <?= format_price_usd((float)$property['price_usd']) ?> USD
      </div>
      <?php if ($property['status'] === 'available'): ?>
        <a href="/invest.php?id=<?= $id ?>" class="btn btn-primary" style="display:block;text-align:center;margin-bottom:.75rem">
          Invest Now with XMR
        </a>
      <?php else: ?>
        <div class="alert alert-warning">This property is no longer available.</div>
      <?php endif; ?>
      <a href="/index.php?view=all" class="btn btn-outline" style="display:block;text-align:center">
        ← Back to Listings
      </a>
      <div class="alert alert-info" style="margin-top:1.5rem;font-size:.85rem">
        <strong>Private Payments</strong><br>
        All transactions are processed via Monero for complete financial privacy.
        Payments are non-reversible once confirmed on-chain.
      </div>
    </div>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

INVEST_PHP = """\
<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/xmr_api.php';
require_once __DIR__ . '/../includes/functions.php';

$id = isset($_GET['id']) ? (int)$_GET['id'] : 0;
$property = $id > 0 ? get_property($id) : null;

if ($property === null) {
    http_response_code(404);
    $page_title = 'Property Not Found';
    include __DIR__ . '/../includes/header.php';
    echo '<main><div class="alert alert-danger">Property not found.</div></main>';
    include __DIR__ . '/../includes/footer.php';
    exit;
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email     = trim($_POST['investor_email'] ?? '');
    $confirmed = isset($_POST['confirm_invest']);

    if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        $error = 'Please enter a valid email address.';
    } elseif (!$confirmed) {
        $error = 'Please confirm you wish to invest.';
    } else {
        $piconeros  = xmr_to_piconeros((float)$property['price_xmr']);
        $desc       = 'Investment: ' . $property['title'];
        $callback   = '';
        $invoice    = create_invoice($piconeros, $desc, $callback);

        if ($invoice === null || empty($invoice['id'])) {
            $error = 'Payment gateway unavailable. Please try again later.';
            app_log('create_invoice failed for property ' . $id, 'ERROR');
        } else {
            $invoice_id  = $invoice['id'];
            $address     = $invoice['address'] ?? '';
            $expires_ts  = date('Y-m-d H:i:s', time() + INVOICE_EXPIRY_SECONDS);
            create_invoice_record($invoice_id, $address, $piconeros, $expires_ts);
            create_investment($id, $email, (float)$property['price_xmr'], $invoice_id);
            app_log("Invoice $invoice_id created for property $id, email: $email");
            redirect('/checkout.php?invoice_id=' . urlencode($invoice_id));
        }
    }
}

$page_title = 'Invest — ' . sanitize($property['title']);
include __DIR__ . '/../includes/header.php';
?>
<main>
  <div style="max-width:640px">
    <h1 class="section-title">Invest in This Property</h1>
    <div style="background:var(--surface);border:1px solid var(--surface2);border-radius:8px;padding:1.25rem;margin-bottom:1.5rem">
      <strong><?= sanitize($property['title']) ?></strong><br>
      <span style="color:var(--text-muted)">📍 <?= sanitize($property['location']) ?></span><br>
      <span class="price-xmr" style="font-size:1.4rem">
        <?= format_xmr(xmr_to_piconeros((float)$property['price_xmr'])) ?>
      </span>
      <span class="price-usd"><?= format_price_usd((float)$property['price_usd']) ?></span>
    </div>

    <?php if ($error !== ''): ?>
      <div class="alert alert-danger"><?= sanitize($error) ?></div>
    <?php endif; ?>

    <form method="POST" action="/invest.php?id=<?= $id ?>">
      <div class="form-card">
        <div class="form-group">
          <label for="investor_email">Your Email Address</label>
          <input type="email" id="investor_email" name="investor_email"
                 value="<?= sanitize($_POST['investor_email'] ?? '') ?>"
                 placeholder="you@example.com" required>
          <small style="color:var(--text-muted)">Used for payment confirmation only. Not stored publicly.</small>
        </div>
        <div class="form-group">
          <label>
            <input type="checkbox" name="confirm_invest" value="1"
                   <?= isset($_POST['confirm_invest']) ? 'checked' : '' ?>>
            I confirm I wish to invest <strong><?= format_xmr(xmr_to_piconeros((float)$property['price_xmr'])) ?></strong>
            in <em><?= sanitize($property['title']) ?></em>
          </label>
        </div>
        <button type="submit" class="btn btn-primary">Generate XMR Payment Address</button>
        <a href="/property.php?id=<?= $id ?>" style="margin-left:1rem;color:var(--text-muted)">Cancel</a>
      </div>
    </form>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

CHECKOUT_PHP = """\
<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/functions.php';

$invoice_id = trim($_GET['invoice_id'] ?? '');
if ($invoice_id === '') {
    redirect('/index.php');
}

$record = get_invoice_record($invoice_id);
if ($record === null) {
    http_response_code(404);
    $page_title = 'Invoice Not Found';
    include __DIR__ . '/../includes/header.php';
    echo '<main><div class="alert alert-danger">Invoice not found. <a href="/index.php">Go home</a></div></main>';
    include __DIR__ . '/../includes/footer.php';
    exit;
}

$amount_xmr  = (float)$record['amount'] / 1e12;
$address     = $record['address'];
$expires_at  = $record['expires_at'];
$page_title  = 'Checkout — Pay with XMR';

$qr_data    = 'monero:' . $address . '?tx_amount=' . number_format($amount_xmr, 12, '.', '');
$qr_url     = 'https://chart.googleapis.com/chart?chs=250x250&cht=qr&chl=' . urlencode($qr_data);
$status_url = '/status.php?invoice_id=' . urlencode($invoice_id);

include __DIR__ . '/../includes/header.php';
?>
<meta http-equiv="refresh" content="15;url=<?= htmlspecialchars($status_url) ?>">
<main>
  <div class="checkout-box">
    <h1 style="color:var(--accent);margin-bottom:1.5rem;font-size:1.5rem">
      Complete Your XMR Payment
    </h1>
    <div class="alert alert-info">
      Send <strong><?= format_xmr((int)$record['amount']) ?></strong> to the
      address below within 60 minutes to complete your investment.
    </div>
    <div class="qr-code">
      <img src="<?= htmlspecialchars($qr_url) ?>" alt="XMR QR Code" width="250" height="250">
    </div>
    <label style="font-size:.85rem;color:var(--text-muted)">Payment Address:</label>
    <div class="address-box"><?= sanitize($address) ?></div>
    <label style="font-size:.85rem;color:var(--text-muted)">Amount (XMR):</label>
    <div class="address-box"><?= number_format($amount_xmr, 12, '.', '') ?></div>
    <label style="font-size:.85rem;color:var(--text-muted)">Invoice ID:</label>
    <div class="address-box" style="font-size:.75rem"><?= sanitize($invoice_id) ?></div>
    <p style="color:var(--text-muted);font-size:.85rem;margin-top:1rem">
      ⏰ Payment expires: <strong><?= sanitize($expires_at) ?></strong>
    </p>
    <p style="color:var(--text-muted);font-size:.82rem;margin-top:.5rem">
      This page will refresh automatically in 15 seconds to check payment status.
    </p>
    <div style="margin-top:1.5rem;display:flex;gap:1rem">
      <a href="<?= htmlspecialchars($status_url) ?>" class="btn btn-primary">Check Status</a>
      <a href="/index.php" class="btn btn-outline">Back to Home</a>
    </div>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

STATUS_PHP = """\
<?php
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/db.php';
require_once __DIR__ . '/../includes/xmr_api.php';
require_once __DIR__ . '/../includes/functions.php';

$invoice_id = trim($_GET['invoice_id'] ?? '');
if ($invoice_id === '') {
    redirect('/index.php');
}

$local = get_invoice_record($invoice_id);
if ($local === null) {
    http_response_code(404);
    $page_title = 'Invoice Not Found';
    include __DIR__ . '/../includes/header.php';
    echo '<main><div class="alert alert-danger">Invoice not found. <a href="/index.php">Go home</a></div></main>';
    include __DIR__ . '/../includes/footer.php';
    exit;
}

// Fetch live status from AcceptXMR
$live = get_invoice_status($invoice_id);
$status = $local['status'];
if ($live !== null && isset($live['status'])) {
    $status = strtolower($live['status']);
    if ($status !== $local['status']) {
        update_invoice_status($invoice_id, $status);
    }
}

$page_title = 'Payment Status — Crypto Real Estate Emporium';
$status_url = '/status.php?invoice_id=' . urlencode($invoice_id);
include __DIR__ . '/../includes/header.php';

if (in_array($status, ['pending', 'confirming'])):
?>
<meta http-equiv="refresh" content="15;url=<?= htmlspecialchars($status_url) ?>">
<?php endif; ?>
<main>
  <div class="status-box status-<?= sanitize($status) ?>">
    <div class="status-icon"></div>
    <?php if ($status === 'paid'): ?>
      <h1 style="color:var(--success);font-size:2rem;margin-bottom:1rem">Payment Confirmed!</h1>
      <p style="color:var(--text-muted);max-width:480px;margin:0 auto 1.5rem">
        Your Monero payment has been received and confirmed on the blockchain.
        A confirmation will be sent to your email address. Thank you for investing!
      </p>
      <a href="/index.php" class="btn btn-primary">Back to Home</a>

    <?php elseif ($status === 'expired'): ?>
      <h1 style="color:var(--danger);font-size:2rem;margin-bottom:1rem">Invoice Expired</h1>
      <p style="color:var(--text-muted);max-width:480px;margin:0 auto 1.5rem">
        Your payment window has expired. If you still wish to invest, please
        generate a new invoice from the property page.
      </p>
      <a href="/index.php?view=all" class="btn btn-outline">Browse Properties</a>

    <?php elseif ($status === 'confirming'): ?>
      <h1 style="color:var(--accent);font-size:2rem;margin-bottom:1rem">Confirming…</h1>
      <p style="color:var(--text-muted);max-width:480px;margin:0 auto 1.5rem">
        Your payment has been received on the network and is awaiting blockchain
        confirmation. This page refreshes every 15 seconds.
      </p>
      <div class="alert alert-info" style="max-width:480px;margin:0 auto 1.5rem">
        Invoice ID: <code><?= sanitize($invoice_id) ?></code>
      </div>

    <?php else: ?>
      <h1 style="color:var(--warning);font-size:2rem;margin-bottom:1rem">Awaiting Payment</h1>
      <p style="color:var(--text-muted);max-width:480px;margin:0 auto 1.5rem">
        We are waiting for your XMR transaction to appear on the network.
        This page refreshes every 15 seconds.
      </p>
      <a href="/checkout.php?invoice_id=<?= urlencode($invoice_id) ?>" class="btn btn-outline">
        View Payment Details
      </a>
    <?php endif; ?>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

ABOUT_PHP = """\
<?php
$page_title = 'About — Crypto Real Estate Emporium';
include __DIR__ . '/../includes/header.php';
?>
<main>
  <div class="content-page">
    <h1 class="section-title">About Crypto Real Estate Emporium</h1>

    <p>Crypto Real Estate Emporium is a privacy-first real estate marketplace
       that accepts exclusively Monero (XMR) for property investments. We believe
       that financial privacy is a fundamental human right, and we have built
       this platform to reflect that belief.</p>

    <h2>Why Monero?</h2>
    <p>Monero is the leading privacy-preserving cryptocurrency. Unlike Bitcoin,
       Monero transactions are private by default using ring signatures, stealth
       addresses, and RingCT technology. When you invest through our platform:</p>
    <ul>
      <li>Transaction amounts are hidden from blockchain observers.</li>
      <li>Sender and receiver addresses are unlinkable.</li>
      <li>No third-party payment processor sees your financial data.</li>
      <li>Payments are final and censorship-resistant.</li>
    </ul>

    <h2>Our Technology Stack</h2>
    <p>Our payment gateway is powered by
       <a href="https://github.com/busyboredom/acceptxmr">AcceptXMR</a>, a
       production-grade, open-source Monero payment processor written in Rust.
       AcceptXMR scans the blockchain directly without relying on third-party
       services, giving you and your investors maximum security and uptime.</p>

    <h2>Privacy Commitment</h2>
    <p>We store only the minimum information required to process your investment:
       your email address for confirmation, and the on-chain invoice data needed
       to verify payment. We do not share, sell, or analyse your personal data.</p>

    <h2>About the Platform</h2>
    <p>This site is also available as a Tor hidden service (.onion address), ensuring
       that even your IP address remains private when browsing our listings.</p>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

FAQ_PHP = """\
<?php
$page_title = 'FAQ — Crypto Real Estate Emporium';
include __DIR__ . '/../includes/header.php';
?>
<main>
  <div class="content-page">
    <h1 class="section-title">Frequently Asked Questions</h1>

    <details>
      <summary>How do I buy a property with XMR?</summary>
      <div class="faq-answer">
        <p>Browse our listings, click "View Property", then "Invest Now with XMR".
           Enter your email, confirm the investment, and you will be given a unique
           Monero payment address and amount. Send the exact XMR amount from your
           wallet within 60 minutes to complete the purchase.</p>
      </div>
    </details>

    <details>
      <summary>What is Monero (XMR)?</summary>
      <div class="faq-answer">
        <p>Monero is a decentralised, open-source cryptocurrency that prioritises
           privacy and fungibility. Unlike Bitcoin, Monero uses advanced cryptography
           (ring signatures, stealth addresses, RingCT) to make all transactions
           private and untraceable by default.</p>
      </div>
    </details>

    <details>
      <summary>How long does payment confirmation take?</summary>
      <div class="faq-answer">
        <p>Monero transactions typically reach the mempool within 1-2 minutes.
           Our platform requires 1 on-chain confirmation (roughly 2 minutes)
           before marking a payment as complete. During high-traffic periods this
           may take slightly longer.</p>
      </div>
    </details>

    <details>
      <summary>Is my purchase anonymous?</summary>
      <div class="faq-answer">
        <p>Monero's protocol ensures your payment is private on-chain. We only
           collect your email address for investment confirmation. This site is
           also available over Tor for additional network-level privacy.</p>
      </div>
    </details>

    <details>
      <summary>What wallets can I use?</summary>
      <div class="faq-answer">
        <p>Any Monero wallet supports our payment addresses. Recommended wallets
           include the official Monero GUI/CLI wallet, Feather Wallet (desktop),
           Cake Wallet (mobile), and Monerujo (Android).</p>
      </div>
    </details>

    <details>
      <summary>Can I sell my property on this platform?</summary>
      <div class="faq-answer">
        <p>Yes! Navigate to the <a href="/sell.php">Sell Property</a> page and
           fill out the enquiry form. Our team will review your listing and contact
           you within 3 business days.</p>
      </div>
    </details>

    <details>
      <summary>Are property prices fixed in XMR?</summary>
      <div class="faq-answer">
        <p>Property prices are listed in both XMR and USD. The XMR price at the
           time of invoice creation is locked for the 60-minute payment window.
           USD prices are indicative only and are updated periodically.</p>
      </div>
    </details>

    <details>
      <summary>What happens if I send the wrong amount?</summary>
      <div class="faq-answer">
        <p>If you send a different amount than requested, the invoice will not
           be marked as paid. Please contact us immediately via the
           <a href="/contact.php">Contact</a> page with your invoice ID.</p>
      </div>
    </details>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

SELL_PHP = """\
<?php
$page_title = 'Sell Your Property — Crypto Real Estate Emporium';
include __DIR__ . '/../includes/header.php';
?>
<main>
  <div style="max-width:640px">
    <h1 class="section-title">List Your Property</h1>
    <p style="color:var(--text-muted);margin-bottom:1.5rem">
      Interested in listing your property on Crypto Real Estate Emporium?
      Fill in the form below and our team will get back to you within 3 business days.
    </p>
    <div class="alert alert-info">
      <strong>Note:</strong> This form is for enquiries only. Submissions are reviewed
      manually before listing. All prices must be quoted in XMR.
    </div>
    <form method="POST" action="/sell.php" style="margin-top:1.5rem">
      <div class="form-card">
        <div class="form-group">
          <label for="owner_name">Your Name</label>
          <input type="text" id="owner_name" name="owner_name" placeholder="Jane Doe" required>
        </div>
        <div class="form-group">
          <label for="owner_email">Email Address</label>
          <input type="email" id="owner_email" name="owner_email" placeholder="you@example.com" required>
        </div>
        <div class="form-group">
          <label for="prop_title">Property Title</label>
          <input type="text" id="prop_title" name="prop_title" placeholder="Luxury Villa in Marbella" required>
        </div>
        <div class="form-group">
          <label for="prop_location">Location</label>
          <input type="text" id="prop_location" name="prop_location" placeholder="City, Country" required>
        </div>
        <div class="form-group">
          <label for="prop_price_xmr">Asking Price (XMR)</label>
          <input type="number" id="prop_price_xmr" name="prop_price_xmr"
                 step="0.0001" min="0.0001" placeholder="500.0000" required>
        </div>
        <div class="form-group">
          <label for="prop_description">Property Description</label>
          <textarea id="prop_description" name="prop_description" rows="5"
                    placeholder="Describe your property…"></textarea>
        </div>
        <div class="form-group">
          <label for="prop_image_url">Image URL (optional)</label>
          <input type="url" id="prop_image_url" name="prop_image_url"
                 placeholder="https://example.com/photo.jpg">
        </div>
        <button type="submit" class="btn btn-primary">Submit Listing Enquiry</button>
      </div>
    </form>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

BLOG_PHP = """\
<?php
$page_title = 'Blog — Crypto Real Estate Emporium';
$posts = [
    [
        'title'   => 'Why Privacy Matters in Real Estate Transactions',
        'date'    => 'January 12, 2025',
        'excerpt' => 'Traditional real estate transactions leave a paper trail visible to governments, banks, and data brokers. We explain why privacy-preserving payments like Monero are the future of property investment.',
        'slug'    => '#privacy-matters',
    ],
    [
        'title'   => "Understanding Monero's Ring Signatures",
        'date'    => 'February 3, 2025',
        'excerpt' => 'A deep dive into the cryptographic primitives that make Monero the gold standard of financial privacy: ring signatures, stealth addresses, and RingCT explained in plain English.',
        'slug'    => '#ring-signatures',
    ],
    [
        'title'   => 'Top 5 Luxury Villas Accepting XMR in 2025',
        'date'    => 'March 18, 2025',
        'excerpt' => 'We round up the most exclusive villa listings currently available on our platform, from the Amalfi Coast to the Swiss Alps.',
        'slug'    => '#top-villas',
    ],
    [
        'title'   => 'How AcceptXMR Processes Payments Privately',
        'date'    => 'April 2, 2025',
        'excerpt' => 'A technical overview of our open-source Rust-based payment processor, AcceptXMR, and how it monitors the Monero blockchain without any third-party dependencies.',
        'slug'    => '#acceptxmr',
    ],
    [
        'title'   => 'Buying Real Estate Over Tor: A Complete Guide',
        'date'    => 'May 7, 2025',
        'excerpt' => 'Our platform is accessible over a Tor .onion address. Learn how to browse listings, generate invoices, and pay entirely over the Tor network for maximum anonymity.',
        'slug'    => '#tor-guide',
    ],
    [
        'title'   => 'XMR vs BTC for Real Estate: Which is Better?',
        'date'    => 'June 14, 2025',
        'excerpt' => 'We compare Bitcoin and Monero for large-value property transactions, examining privacy, fees, confirmation times, and regulatory considerations.',
        'slug'    => '#xmr-vs-btc',
    ],
];
include __DIR__ . '/../includes/header.php';
?>
<main>
  <h1 class="section-title">Blog</h1>
  <div class="blog-grid">
    <?php foreach ($posts as $post): ?>
    <div class="blog-card">
      <div class="blog-meta"><?= htmlspecialchars($post['date']) ?></div>
      <h3><?= htmlspecialchars($post['title']) ?></h3>
      <p><?= htmlspecialchars($post['excerpt']) ?></p>
      <a href="<?= htmlspecialchars($post['slug']) ?>" style="font-size:.88rem;margin-top:.75rem;display:inline-block">
        Read more →
      </a>
    </div>
    <?php endforeach; ?>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

CONTACT_PHP = """\
<?php
$page_title = 'Contact — Crypto Real Estate Emporium';
include __DIR__ . '/../includes/header.php';
?>
<main>
  <div class="content-page">
    <h1 class="section-title">Contact Us</h1>
    <p style="color:var(--text-muted)">
      Have a question about a listing, a payment issue, or a business enquiry?
      Use the details below or reach us on our Tor hidden service.
    </p>

    <h2>Email</h2>
    <p>contact@cryptorealestate.local
       &nbsp;<em style="color:var(--text-muted)">(placeholder — set your own address)</em></p>

    <h2>Tor Hidden Service</h2>
    <p style="color:var(--text-muted)">
      Our .onion address is generated during deployment and displayed in the
      deployment summary. Connect using the
      <a href="https://www.torproject.org/download/">Tor Browser</a>.
    </p>

    <h2>PGP Key</h2>
    <p style="color:var(--text-muted)">
      For sensitive enquiries, please request our PGP public key via email.
    </p>

    <h2>Response Time</h2>
    <p style="color:var(--text-muted)">We aim to respond within 2 business days.</p>

    <div class="alert alert-info" style="margin-top:2rem">
      <strong>Privacy Reminder:</strong> Please avoid sending sensitive personal or
      financial information over unencrypted email. Use our Tor address where possible.
    </div>
  </div>
</main>
<?php include __DIR__ . '/../includes/footer.php'; ?>
"""

SAMPLE_PROPERTIES = [
    ("Belgravia Grand Mansion", "An imposing Grade I listed mansion in the heart of London's Belgravia, featuring 8 bedrooms, a private cinema, wine cellar, and landscaped gardens.", "London, UK", 4800.0, 1200000, 8, 9, 12000, "mansion", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800"),
    ("Monaco Penthouse Royale", "Exclusive penthouse atop a sought-after tower with panoramic Mediterranean views, infinity pool, and private concierge service.", "Monaco", 6200.0, 1550000, 5, 6, 8500, "apartment", "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800"),
    ("Amalfi Coast Cliffside Villa", "Breathtaking cliffside villa on the Amalfi Coast with private sea access, terraced gardens, and authentic Italian décor.", "Ravello, Italy", 2100.0, 525000, 5, 5, 6200, "villa", "https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800"),
    ("Swiss Alpine Chalet Estate", "Luxury ski-in/ski-out chalet with direct piste access in the heart of Verbier, featuring a spa, cinema room, and heated outdoor pool.", "Verbier, Switzerland", 5500.0, 1375000, 7, 7, 9500, "mansion", "https://images.unsplash.com/photo-1449844908441-8829872d2607?w=800"),
    ("Ibiza Hilltop Finca", "Authentic converted finca on a private hilltop with 360-degree sunset views, pool house, helipad, and 5 hectares of land.", "Ibiza, Spain", 1800.0, 450000, 6, 6, 7800, "villa", "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?w=800"),
    ("Dubai Marina Sky Apartment", "Ultra-modern duplex apartment on the 62nd floor of a landmark Dubai Marina tower with chef's kitchen and private terrace.", "Dubai, UAE", 980.0, 245000, 3, 4, 4200, "apartment", "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800"),
    ("Malibu Oceanfront Compound", "Expansive oceanfront compound on Carbon Beach with private beach frontage, guest house, and stunning Pacific views.", "Malibu, CA, USA", 9800.0, 2450000, 7, 8, 14000, "mansion", "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=800"),
    ("Bali Jungle Retreat Villa", "Secluded luxury villa nestled in Ubud's jungle, featuring open-air pavilions, infinity pool, and traditional Balinese craftsmanship.", "Ubud, Bali, Indonesia", 420.0, 105000, 4, 4, 5200, "villa", "https://images.unsplash.com/photo-1537640538966-79f369143f8f?w=800"),
    ("Paris 7ème Haussmann Apartment", "Classic Haussmann-era apartment on the 4th floor with original parquet floors, ornate cornicing, and views of the Eiffel Tower.", "Paris, France", 1200.0, 300000, 3, 2, 2200, "apartment", "https://images.unsplash.com/photo-1555636222-cae831e670b3?w=800"),
    ("Tulum Eco-Luxury Retreat", "Off-grid jungle estate with solar panels, rainwater harvesting, private cenote, and four separate palapa structures.", "Tulum, Mexico", 620.0, 155000, 5, 5, 6800, "villa", "https://images.unsplash.com/photo-1582268611958-ebfd161ef9cf?w=800"),
    ("New York Tribeca Loft", "Vast converted cast-iron loft in the heart of Tribeca with 14-foot ceilings, exposed brick, and private rooftop terrace.", "New York, NY, USA", 2800.0, 700000, 4, 3, 4800, "apartment", "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800"),
    ("Santorini Caldera Mansion", "Iconic white-washed clifftop mansion in Oia with private plunge pool, butler service, and unrivalled caldera views at sunset.", "Oia, Santorini, Greece", 3400.0, 850000, 6, 6, 7000, "mansion", "https://images.unsplash.com/photo-1533105079780-92b9be482077?w=800"),
]


class WebsiteBuilder:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.base = SITE_ROOT

    def create_directories(self) -> None:
        logger.info("Creating website directory structure…")
        dirs = [
            f"{self.base}/public/assets/css",
            f"{self.base}/public/assets/images",
            f"{self.base}/includes",
            f"{self.base}/data/invoices",
            f"{self.base}/logs",
        ]
        for d in dirs:
            if not self.dry_run:
                Path(d).mkdir(parents=True, exist_ok=True)
            logger.debug("mkdir: %s", d)

    def create_database(self) -> None:
        logger.info("Creating SQLite database at %s…", DB_PATH)
        if self.dry_run:
            logger.info("[DRY-RUN] Would create SQLite database.")
            return

        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                slug       TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS properties (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                description TEXT NOT NULL,
                location    TEXT NOT NULL,
                price_xmr   REAL NOT NULL,
                price_usd   REAL NOT NULL,
                bedrooms    INTEGER NOT NULL DEFAULT 0,
                bathrooms   INTEGER NOT NULL DEFAULT 0,
                sqft        INTEGER NOT NULL DEFAULT 0,
                image_url   TEXT,
                category    TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'available',
                created_at  DATETIME DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS investments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                property_id    INTEGER NOT NULL,
                investor_email TEXT NOT NULL,
                amount_xmr     REAL NOT NULL,
                invoice_id     TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'pending',
                created_at     DATETIME DEFAULT (datetime('now')),
                FOREIGN KEY (property_id) REFERENCES properties(id)
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                xmr_invoice_id        TEXT NOT NULL UNIQUE,
                address               TEXT NOT NULL,
                amount                INTEGER NOT NULL,
                confirmations_required INTEGER NOT NULL DEFAULT 1,
                status                TEXT NOT NULL DEFAULT 'pending',
                created_at            DATETIME DEFAULT (datetime('now')),
                expires_at            DATETIME
            );
        """)

        # Seed categories
        categories = [
            ("Mansions", "mansion"),
            ("Apartments", "apartment"),
            ("Villas", "villa"),
            ("Land", "land"),
            ("Commercial", "commercial"),
        ]
        cur.executemany(
            "INSERT OR IGNORE INTO categories (name, slug) VALUES (?, ?)",
            categories,
        )

        # Seed sample properties
        for prop in SAMPLE_PROPERTIES:
            cur.execute(
                """INSERT OR IGNORE INTO properties
                   (title, description, location, price_xmr, price_usd,
                    bedrooms, bathrooms, sqft, image_url, category, status)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (*prop, "available"),
            )

        con.commit()
        con.close()
        logger.info("Database created with %d sample properties.", len(SAMPLE_PROPERTIES))

    def write_php_files(self) -> None:
        logger.info("Writing PHP website files…")
        files = {
            f"{self.base}/public/assets/css/style.css": CSS_CONTENT,
            f"{self.base}/includes/header.php": HEADER_PHP,
            f"{self.base}/includes/footer.php": FOOTER_PHP,
            f"{self.base}/includes/config.php": CONFIG_PHP,
            f"{self.base}/includes/db.php": DB_PHP,
            f"{self.base}/includes/xmr_api.php": XMR_API_PHP,
            f"{self.base}/includes/functions.php": FUNCTIONS_PHP,
            f"{self.base}/public/index.php": INDEX_PHP,
            f"{self.base}/public/property.php": PROPERTY_PHP,
            f"{self.base}/public/invest.php": INVEST_PHP,
            f"{self.base}/public/checkout.php": CHECKOUT_PHP,
            f"{self.base}/public/status.php": STATUS_PHP,
            f"{self.base}/public/about.php": ABOUT_PHP,
            f"{self.base}/public/faq.php": FAQ_PHP,
            f"{self.base}/public/sell.php": SELL_PHP,
            f"{self.base}/public/blog.php": BLOG_PHP,
            f"{self.base}/public/contact.php": CONTACT_PHP,
            f"{self.base}/logs/.gitkeep": "",
        }
        for path, content in files.items():
            write_file(path, content, dry_run=self.dry_run)
        logger.info("All PHP/CSS files written.")

    def run_all(self) -> None:
        self.create_directories()
        self.create_database()
        self.write_php_files()


# ---------------------------------------------------------------------------
# Phase 7: Apache Configuration
# ---------------------------------------------------------------------------

class ApacheConfigurator:
    def __init__(self, port: int, dry_run: bool = False) -> None:
        self.port = port
        self.dry_run = dry_run

    def write_vhost(self) -> None:
        logger.info("Writing Apache vhost config…")
        content = f"""\
<VirtualHost 127.0.0.1:{self.port}>
    ServerName cryptorealestate.local
    DocumentRoot /var/www/crypto_realestate/public

    <Directory /var/www/crypto_realestate/public>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog /var/www/crypto_realestate/logs/error.log
    CustomLog /var/www/crypto_realestate/logs/access.log combined

    php_flag display_errors Off
    php_flag log_errors On
    php_value error_log /var/www/crypto_realestate/logs/php_errors.log

    <FilesMatch "\\.php$">
        SetHandler application/x-httpd-php
    </FilesMatch>
</VirtualHost>
"""
        write_file(APACHE_CONF, content, dry_run=self.dry_run)

    def update_ports_conf(self) -> None:
        logger.info("Checking ports.conf for Listen 127.0.0.1:%d…", self.port)
        listen_line = f"Listen 127.0.0.1:{self.port}"
        if self.dry_run:
            logger.info("[DRY-RUN] Would add '%s' to %s if absent.", listen_line, APACHE_PORTS)
            return
        try:
            with open(APACHE_PORTS) as f:
                content = f.read()
        except FileNotFoundError:
            content = ""
        if listen_line not in content:
            logger.info("Adding '%s' to %s", listen_line, APACHE_PORTS)
            with open(APACHE_PORTS, "a") as f:
                f.write(f"\n{listen_line}\n")
        else:
            logger.info("ports.conf already contains '%s'", listen_line)

    def write_htaccess(self) -> None:
        for path in [
            f"{SITE_ROOT}/includes/.htaccess",
            f"{SITE_ROOT}/data/.htaccess",
        ]:
            write_file(path, "Require all denied\n", dry_run=self.dry_run)
        logger.info(".htaccess protection files written.")

    def enable_site(self) -> None:
        logger.info("Enabling Apache site and reloading…")
        run(["a2ensite", "crypto_realestate.conf"], dry_run=self.dry_run)
        run(["a2enmod", "php7.4"], check=False, dry_run=self.dry_run)
        run(["a2enmod", "rewrite"], dry_run=self.dry_run)
        run(["systemctl", "reload", "apache2"], dry_run=self.dry_run)

    def run_all(self) -> None:
        self.write_vhost()
        self.update_ports_conf()
        self.write_htaccess()
        self.enable_site()


# ---------------------------------------------------------------------------
# Phase 8: Tor Hidden Service
# ---------------------------------------------------------------------------

class TorConfigurator:
    def __init__(self, port: int, dry_run: bool = False) -> None:
        self.port = port
        self.dry_run = dry_run
        self.onion_address: Optional[str] = None

    def configure_hidden_service(self) -> None:
        logger.info("Configuring Tor hidden service…")
        hs_marker = f"HiddenServiceDir {TOR_HS_DIR}"

        torrc_path = Path(TOR_TORRC)
        if not torrc_path.exists():
            logger.warning("torrc not found at %s — skipping Tor configuration.", TOR_TORRC)
            return

        with open(TOR_TORRC) as f:
            existing = f.read()

        if hs_marker in existing:
            logger.info("Tor hidden service already configured in torrc — skipping.")
        else:
            append_block = (
                "\n# Crypto Real Estate Hidden Service - Added by deploy_crypto_realestate.py\n"
                f"HiddenServiceDir {TOR_HS_DIR}/\n"
                f"HiddenServicePort 80 127.0.0.1:{self.port}\n"
            )
            logger.info("Appending hidden service config to torrc…")
            if not self.dry_run:
                with open(TOR_TORRC, "a") as f:
                    f.write(append_block)

        if not self.dry_run:
            Path(TOR_HS_DIR).mkdir(parents=True, exist_ok=True)
            try:
                run(["chown", "-R", "debian-tor:debian-tor", TOR_HS_DIR])
                run(["chmod", "700", TOR_HS_DIR])
            except subprocess.CalledProcessError as exc:
                logger.warning("chown/chmod on Tor HS dir failed: %s", exc)
            run(["systemctl", "reload", "tor"], check=False)
            logger.info("Waiting 15s for Tor to generate hidden service keys…")
            time.sleep(15)
            self.onion_address = self._read_hostname()

    def _read_hostname(self) -> Optional[str]:
        hostname_path = Path(TOR_HS_HOSTNAME)
        if hostname_path.exists():
            addr = hostname_path.read_text().strip()
            logger.info("Tor .onion address: %s", addr)
            return addr
        logger.warning("Tor hostname file not found at %s", TOR_HS_HOSTNAME)
        return None

    def run_all(self) -> None:
        self.configure_hidden_service()


# ---------------------------------------------------------------------------
# Phase 9: Security Hardener
# ---------------------------------------------------------------------------

class SecurityHardener:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def set_permissions(self) -> None:
        logger.info("Setting file/directory permissions on %s…", SITE_ROOT)
        if self.dry_run:
            logger.info("[DRY-RUN] Would chown/chmod website files.")
            return

        run(["chown", "-R", "www-data:www-data", SITE_ROOT])

        # chmod 755 for directories
        for root, dirs, _ in os.walk(SITE_ROOT):
            for d in dirs:
                dp = os.path.join(root, d)
                os.chmod(dp, 0o755)

        # chmod 644 for files (except SQLite DB)
        for root, _, files in os.walk(SITE_ROOT):
            for fn in files:
                fp = os.path.join(root, fn)
                if fp == DB_PATH:
                    os.chmod(fp, 0o666)
                else:
                    os.chmod(fp, 0o644)

        logger.info("Permissions applied.")

    def write_config_ini(self, port: int, address: str, daemon_url: str) -> None:
        logger.info("Writing /etc/crypto_realestate/config.ini…")
        if not self.dry_run:
            Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
        cfg = configparser.ConfigParser()
        cfg["site"] = {
            "port": str(port),
            "document_root": f"{SITE_ROOT}/public",
            "site_name": "Crypto Real Estate Emporium",
        }
        cfg["xmrgateway"] = {
            "directory": XMR_GATEWAY_DIR,
            "internal_api_port": str(INTERNAL_API_PORT),
            "external_api_port": str(EXTERNAL_API_PORT),
            "wallet_address": address,
            "daemon_url": daemon_url,
        }
        cfg["database"] = {
            "path": DB_PATH,
        }
        if not self.dry_run:
            with open(CONFIG_FILE, "w") as f:
                cfg.write(f)
            os.chmod(CONFIG_FILE, 0o640)
        logger.info("Config written to %s", CONFIG_FILE)

    def run_all(self, port: int, address: str, daemon_url: str) -> None:
        self.set_permissions()
        self.write_config_ini(port, address, daemon_url)


# ---------------------------------------------------------------------------
# Phase 10: Final Verifier
# ---------------------------------------------------------------------------

class FinalVerifier:
    def __init__(self, port: int, onion_address: Optional[str],
                 dry_run: bool = False) -> None:
        self.port = port
        self.onion_address = onion_address
        self.dry_run = dry_run

    def test_apache_config(self) -> bool:
        logger.info("Running apachectl configtest…")
        result = run(
            ["apachectl", "configtest"],
            check=False, capture=True, dry_run=self.dry_run,
        )
        if result.returncode == 0 or "Syntax OK" in (result.stderr or ""):
            logger.info("Apache config: OK")
            return True
        logger.warning("Apache configtest output: %s", result.stderr)
        return False

    def test_tor_config(self) -> bool:
        logger.info("Running tor --verify-config…")
        result = run(
            ["tor", "--verify-config"],
            check=False, capture=True, dry_run=self.dry_run,
        )
        if result.returncode == 0:
            logger.info("Tor config: OK")
            return True
        logger.warning("Tor verify-config output: %s", result.stdout or result.stderr)
        return False

    def test_http(self) -> bool:
        logger.info("Testing HTTP response on 127.0.0.1:%d…", self.port)
        if self.dry_run:
            logger.info("[DRY-RUN] Skipping HTTP curl test.")
            return True
        result = run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             f"http://127.0.0.1:{self.port}/"],
            check=False, capture=True,
        )
        code = result.stdout.strip() if result.stdout else "000"
        if code in ("200", "302", "301"):
            logger.info("HTTP test: %s — OK", code)
            return True
        logger.warning("HTTP test returned status code: %s", code)
        return False

    def print_summary(self) -> None:
        sep = "=" * 70
        onion = self.onion_address or "(not yet available — check /var/lib/tor/crypto_realestate/hostname)"
        print(f"""
{sep}
  DEPLOYMENT COMPLETE — Crypto Real Estate Emporium
{sep}

  Local URL:         http://127.0.0.1:{self.port}/
  Tor Onion Address: {onion}

  Services:
    Apache          : systemctl status apache2
    AcceptXMR       : systemctl status acceptxmr
    Tor             : systemctl status tor

  Logs:
    Deploy log      : {LOG_FILE}
    Apache error    : {SITE_ROOT}/logs/error.log
    Apache access   : {SITE_ROOT}/logs/access.log
    App log         : {SITE_ROOT}/logs/app.log

  Configuration:
    Site config     : {CONFIG_FILE}
    AcceptXMR YAML  : {XMR_YAML}
    Systemd service : {SYSTEMD_SERVICE}
    Apache vhost    : {APACHE_CONF}

  IMPORTANT:
    1. Edit {SYSTEMD_SERVICE} to set PRIVATE_VIEWKEY
       (or use: systemctl edit acceptxmr to set env override)
    2. Run: systemctl start acceptxmr
    3. Verify AcceptXMR is reachable: curl http://127.0.0.1:{INTERNAL_API_PORT}/invoices

{sep}
""")

    def run_all(self) -> None:
        self.test_apache_config()
        self.test_tor_config()
        self.test_http()
        self.print_summary()


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def rollback(tor_backup: Optional[str], dry_run: bool = False) -> None:
    logger.warning("Rolling back changes…")
    if tor_backup and Path(tor_backup).exists():
        logger.info("Restoring torrc from %s", tor_backup)
        if not dry_run:
            shutil.copy2(tor_backup, TOR_TORRC)

    vhost_enabled = Path(f"/etc/apache2/sites-enabled/crypto_realestate.conf")
    if vhost_enabled.exists():
        logger.info("Disabling new Apache vhost…")
        run(["a2dissite", "crypto_realestate.conf"], check=False, dry_run=dry_run)
        run(["systemctl", "reload", "apache2"], check=False, dry_run=dry_run)

    logger.warning("Rollback complete. Check %s for details.", LOG_FILE)


# ---------------------------------------------------------------------------
# Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deploy the Crypto Real Estate Emporium with AcceptXMR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--view-key", metavar="KEY", default="",
        help="Monero private view key (set in acceptxmr.service env)",
    )
    p.add_argument(
        "--address", metavar="ADDR", default=DEFAULT_ADDRESS,
        help=f"Monero primary address (default: {DEFAULT_ADDRESS[:20]}…)",
    )
    p.add_argument(
        "--daemon-url", metavar="URL", default=DEFAULT_DAEMON_URL,
        help=f"Monero daemon RPC URL (default: {DEFAULT_DAEMON_URL})",
    )
    p.add_argument(
        "--port", metavar="PORT", type=int, default=DEFAULT_PORT,
        help=f"Apache listen port (default: {DEFAULT_PORT})",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without making changes",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose/debug output",
    )
    return p


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)
    logger.info("deploy_crypto_realestate.py v%s starting…", SCRIPT_VERSION)

    if args.dry_run:
        logger.info("DRY-RUN mode enabled — no changes will be written.")

    checker = SystemChecker(port=args.port, dry_run=args.dry_run)
    try:
        # Phase 1: Pre-flight
        checker.run_all()

        # Phase 2: Dependencies
        deps = DependencyInstaller(dry_run=args.dry_run)
        deps.run_all()

        # Phase 3: xmrgateway
        xmr = XMRGatewaySetup(
            view_key=args.view_key,
            address=args.address,
            daemon_url=args.daemon_url,
            dry_run=args.dry_run,
        )
        xmr.run_all()

        # Phase 4-6: Website
        site = WebsiteBuilder(dry_run=args.dry_run)
        site.run_all()

        # Phase 7: Apache
        apache = ApacheConfigurator(port=args.port, dry_run=args.dry_run)
        apache.run_all()

        # Phase 8: Tor
        tor = TorConfigurator(port=args.port, dry_run=args.dry_run)
        tor.run_all()

        # Phase 9: Security
        sec = SecurityHardener(dry_run=args.dry_run)
        sec.run_all(
            port=args.port,
            address=args.address,
            daemon_url=args.daemon_url,
        )

        # Phase 10: Verify & Report
        verifier = FinalVerifier(
            port=args.port,
            onion_address=tor.onion_address,
            dry_run=args.dry_run,
        )
        verifier.run_all()

    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        rollback(checker.tor_backup, dry_run=args.dry_run)
        sys.exit(1)
    except Exception as exc:
        logger.exception("Deployment failed: %s", exc)
        rollback(checker.tor_backup, dry_run=args.dry_run)
        sys.exit(2)


if __name__ == "__main__":
    main()
