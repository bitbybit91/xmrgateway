#!/usr/bin/env bash
# =============================================================================
# install.sh — Crypto Investment Platform Installer
# Target: Ubuntu 20.04 LTS
# Usage: sudo bash install.sh
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── A. PRE-FLIGHT ─────────────────────────────────────────────────────────────
info "=== A. Pre-flight checks ==="

[[ "$EUID" -eq 0 ]] || error "This script must be run as root (sudo bash install.sh)."

# Detect Ubuntu 20.04
if ! grep -q 'DISTRIB_RELEASE=20.04' /etc/lsb-release 2>/dev/null; then
  warn "This script is designed for Ubuntu 20.04. Detected: $(lsb_release -d 2>/dev/null | cut -f2 || echo 'unknown'). Continuing anyway…"
fi

# Snapshot existing state
TS=$(date +%s)
LOG_FILE="/root/cryptoinvest_preinstall_${TS}.log"
{
  echo "=== Pre-install snapshot: $(date) ==="
  echo "--- /var/www contents ---"
  ls /var/www/ 2>/dev/null || true
  echo "--- /etc/nginx/sites-enabled ---"
  ls /etc/nginx/sites-enabled/ 2>/dev/null || true
  echo "--- /etc/apache2/sites-enabled ---"
  ls /etc/apache2/sites-enabled/ 2>/dev/null || true
  echo "--- Running services ---"
  systemctl list-units --type=service --state=running 2>/dev/null | head -40 || true
  echo "--- MySQL databases ---"
  mysql -e "SHOW DATABASES;" 2>/dev/null || true
} > "$LOG_FILE"
info "Pre-install snapshot saved to $LOG_FILE"

# ── Prompt for configuration ──────────────────────────────────────────────────
info "=== Configuration ==="

read -rp "Enter your domain (e.g. invest.example.com) [default: invest.example.com]: " DOMAIN
DOMAIN="${DOMAIN:-invest.example.com}"

read -rp "Enter your XMR primary address: " XMR_PRIMARY_ADDRESS
XMR_PRIMARY_ADDRESS="${XMR_PRIMARY_ADDRESS:-4613YiHLM6JMH4zejMB2zJY5TwQCxL8p65ufw8kBP5yxX9itmuGLqp1dS4tkVoTxjyH3aYhYNrtGHbQzJQP5bFus3KHVdmf}"

read -rsp "Enter your XMR private view key: " XMR_VIEWKEY
echo
XMR_VIEWKEY="${XMR_VIEWKEY:-ad2093a5705b9f33e6f0f0c1bc1f5f639c756cdfc168c8f2ac6127ccbdab3a03}"

read -rp "Enter XMR daemon URL [default: http://xmr-node.cakewallet.com:18081/]: " DAEMON_URL
DAEMON_URL="${DAEMON_URL:-http://xmr-node.cakewallet.com:18081/}"

# ── Port detection ────────────────────────────────────────────────────────────
HTTP_PORT=80
HTTPS_PORT=443
if ss -ltn 2>/dev/null | grep -q ':80 '; then
  warn "Port 80 appears to be in use. Will configure Nginx on port 8080 instead."
  HTTP_PORT=8080
fi
if ss -ltn 2>/dev/null | grep -q ':8081 '; then
  warn "Port 8081 is in use. AcceptXMR may conflict — please check after install."
fi

# ── Generate secrets ──────────────────────────────────────────────────────────
APP_SECRET=$(openssl rand -hex 32)
DB_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
ADMIN_PASS=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9' | head -c 16)
INTERNAL_TOKEN=$(openssl rand -hex 32)

CREDS_FILE="/root/cryptoinvest_credentials.txt"

# ── B. SYSTEM PACKAGES ────────────────────────────────────────────────────────
info "=== B. Installing system packages ==="

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq

# Add ondrej/php PPA for PHP 8.1 if needed
if ! apt-cache show php8.1-fpm &>/dev/null; then
  info "Adding ondrej/php PPA..."
  apt-get install -y -qq software-properties-common
  add-apt-repository -y ppa:ondrej/php
  apt-get update -qq
fi

apt-get install -y -qq \
  nginx \
  mariadb-server \
  php8.1-fpm php8.1-mysql php8.1-curl php8.1-mbstring php8.1-xml php8.1-gd php8.1-bcmath php8.1-zip php8.1-cli \
  composer \
  git curl wget \
  build-essential pkg-config libssl-dev \
  ufw \
  certbot python3-certbot-nginx \
  ca-certificates

success "System packages installed."

# ── Install Rust / cargo (for AcceptXMR build) ────────────────────────────────
if ! command -v cargo &>/dev/null; then
  info "Installing Rust toolchain..."
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
  source "$HOME/.cargo/env" || true
fi
source "$HOME/.cargo/env" 2>/dev/null || export PATH="$HOME/.cargo/bin:$PATH"
success "Rust $(rustc --version 2>/dev/null) available."

# ── C. ACCEPTXMR SETUP ───────────────────────────────────────────────────────
info "=== C. AcceptXMR Payment Gateway Setup ==="

if [ ! -d /opt/acceptxmr ]; then
  git clone https://github.com/bitbybit91/xmrgateway.git /opt/acceptxmr
fi
cd /opt/acceptxmr
git fetch origin 2>/dev/null || true
git checkout copilot/update-website-updater-script 2>/dev/null || git checkout main 2>/dev/null || true

# Build the acceptxmr-server binary (only if not already built)
if [ ! -f /opt/acceptxmr/target/release/acceptxmr-server ]; then
  info "Building AcceptXMR server (this may take several minutes)..."
  cargo build --release --bin acceptxmr-server 2>&1 | tail -5
  success "AcceptXMR server built."
else
  success "AcceptXMR server binary already exists, skipping build."
fi

# Write config
cat > /opt/acceptxmr/acceptxmr.yaml <<YAMLEOF
external-api:
  port: 8080
  ipv4: 127.0.0.1
  tls: null
  static_dir: server/static/

internal-api:
  port: 8081
  ipv4: 127.0.0.1
  tls: null
  static_dir: server/static/

callback:
  queue-size: 1000
  max-retries: 50

wallet:
  primary-address: ${XMR_PRIMARY_ADDRESS}
  account-index: 0
  restore-height: null

daemon:
  url: ${DAEMON_URL}
  login: null
  rpc-timeout: 30
  connection-timeout: 20

database:
  path: AcceptXMR_DB/
  delete-expired: true

logging:
  verbosity: INFO
YAMLEOF

# Write .env for AcceptXMR
cat > /opt/acceptxmr/.env <<ENVEOF
PRIVATE_VIEWKEY=${XMR_VIEWKEY}
INTERNAL_API_TOKEN=${INTERNAL_TOKEN}
ENVEOF
chmod 600 /opt/acceptxmr/.env

# Create dedicated user for AcceptXMR service
if ! id acceptxmr &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin acceptxmr
fi

# Ownership
chown -R acceptxmr:acceptxmr /opt/acceptxmr
mkdir -p /opt/acceptxmr/AcceptXMR_DB
chown acceptxmr:acceptxmr /opt/acceptxmr/AcceptXMR_DB

# systemd unit
cp /opt/acceptxmr/deploy/systemd/acceptxmr.service /etc/systemd/system/acceptxmr.service 2>/dev/null || \
cat > /etc/systemd/system/acceptxmr.service <<SVCEOF
[Unit]
Description=AcceptXMR Monero Payment Gateway
After=network.target

[Service]
Type=simple
User=acceptxmr
WorkingDirectory=/opt/acceptxmr
ExecStart=/opt/acceptxmr/target/release/acceptxmr-server --config /opt/acceptxmr/acceptxmr.yaml
Restart=on-failure
RestartSec=5s
EnvironmentFile=/opt/acceptxmr/.env
NoNewPrivileges=yes
PrivateTmp=yes
ReadWritePaths=/opt/acceptxmr/AcceptXMR_DB

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
if ! systemctl is-active --quiet acceptxmr; then
  systemctl enable acceptxmr
  systemctl start acceptxmr
  sleep 3
fi

if systemctl is-active --quiet acceptxmr; then
  success "AcceptXMR service is running."
else
  warn "AcceptXMR service failed to start. Check: journalctl -u acceptxmr"
fi

# ── D. MYSQL SETUP ────────────────────────────────────────────────────────────
info "=== D. MySQL / MariaDB Setup ==="

if ! systemctl is-active --quiet mariadb; then
  systemctl enable mariadb
  systemctl start mariadb
fi

# Create DB and user if they don't exist
mysql -e "
  CREATE DATABASE IF NOT EXISTS cryptoinvest_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER IF NOT EXISTS 'cryptoinvest_user'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
  GRANT ALL PRIVILEGES ON cryptoinvest_db.* TO 'cryptoinvest_user'@'127.0.0.1';
  FLUSH PRIVILEGES;
" 2>/dev/null || {
  warn "DB setup via 127.0.0.1 failed, trying localhost..."
  mysql -e "
    CREATE DATABASE IF NOT EXISTS cryptoinvest_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    CREATE USER IF NOT EXISTS 'cryptoinvest_user'@'localhost' IDENTIFIED BY '${DB_PASS}';
    GRANT ALL PRIVILEGES ON cryptoinvest_db.* TO 'cryptoinvest_user'@'localhost';
    FLUSH PRIVILEGES;
  " || warn "MySQL setup had issues — verify manually."
  DB_HOST_PHP="localhost"
}
DB_HOST_PHP="${DB_HOST_PHP:-127.0.0.1}"

# Import schema
mysql cryptoinvest_db < /var/www/cryptoinvest/database/schema.sql 2>/dev/null || \
mysql cryptoinvest_db < /opt/acceptxmr/../website/database/schema.sql 2>/dev/null || \
warn "Could not auto-import schema (app directory may not be deployed yet — see Step E)."

# Hash admin password and update
ADMIN_HASH=$(php -r "echo password_hash('${ADMIN_PASS}', PASSWORD_BCRYPT, ['cost'=>12]);")
mysql cryptoinvest_db -e "UPDATE users SET password_hash='${ADMIN_HASH}' WHERE email='admin@cryptoinvest.local';" 2>/dev/null || true

success "Database ready."

# ── E. PHP APPLICATION DEPLOYMENT ────────────────────────────────────────────
info "=== E. Deploying PHP Application ==="

APP_DIR=/var/www/cryptoinvest
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBSITE_DIR="$SCRIPT_DIR/website"

# Copy website source if running from repo root
if [ -d "$WEBSITE_DIR" ]; then
  if [ ! -d "$APP_DIR" ]; then
    cp -r "$WEBSITE_DIR" "$APP_DIR"
    success "Application copied to $APP_DIR."
  else
    warn "$APP_DIR already exists — syncing website source files only (not overwriting .env)."
    rsync -a --exclude='.env' --exclude='vendor' --exclude='storage' "$WEBSITE_DIR/" "$APP_DIR/"
  fi
else
  warn "website/ directory not found relative to install.sh. Assuming app is already in $APP_DIR."
  mkdir -p "$APP_DIR"
fi

# Write .env
if [ ! -f "$APP_DIR/.env" ]; then
  cat > "$APP_DIR/.env" <<DOTENV
APP_NAME="Pantera Capital Crypto"
APP_URL=http://${DOMAIN}
APP_ENV=production
APP_SECRET=${APP_SECRET}

DB_HOST=${DB_HOST_PHP}
DB_PORT=3306
DB_NAME=cryptoinvest_db
DB_USER=cryptoinvest_user
DB_PASS=${DB_PASS}

ACCEPTXMR_INTERNAL_URL=http://127.0.0.1:8081
ACCEPTXMR_EXTERNAL_URL=http://127.0.0.1:8080
ACCEPTXMR_INTERNAL_TOKEN=${INTERNAL_TOKEN}
ACCEPTXMR_EXTERNAL_TOKEN=

ADMIN_EMAIL=admin@cryptoinvest.local
ADMIN_PASS=${ADMIN_PASS}

MAIL_HOST=localhost
MAIL_PORT=25
MAIL_ENCRYPTION=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM_ADDRESS=noreply@${DOMAIN}
MAIL_FROM_NAME="Pantera Capital Crypto"

COINGECKO_API_URL=https://api.coingecko.com/api/v3
DOTENV
  chmod 600 "$APP_DIR/.env"
  success ".env written."
fi

# Create required directories
mkdir -p "$APP_DIR/storage/"{logs,cache,sessions}
mkdir -p "$APP_DIR/public/uploads"

# Run Composer
if [ -f "$APP_DIR/composer.json" ]; then
  info "Running composer install..."
  cd "$APP_DIR"
  if command -v composer &>/dev/null; then
    COMPOSER_ALLOW_SUPERUSER=1 composer install --no-dev --optimize-autoloader --no-interaction 2>&1 | tail -5
    success "Composer install complete."
  else
    warn "composer not found in PATH. Install dependencies manually: cd $APP_DIR && composer install"
  fi
fi

# Import schema (now that APP_DIR exists)
if mysql cryptoinvest_db < "$APP_DIR/database/schema.sql" 2>/dev/null; then
  ADMIN_HASH=$(php -r "echo password_hash('${ADMIN_PASS}', PASSWORD_BCRYPT, ['cost'=>12]);")
  mysql cryptoinvest_db -e "UPDATE users SET password_hash='${ADMIN_HASH}' WHERE email='admin@cryptoinvest.local';" 2>/dev/null || true
  success "Database schema imported."
fi

# Permissions
chown -R www-data:www-data "$APP_DIR"
find "$APP_DIR" -type d -exec chmod 755 {} \;
find "$APP_DIR" -type f -exec chmod 644 {} \;
chmod 775 "$APP_DIR/storage" "$APP_DIR/public/uploads"
find "$APP_DIR/storage" -type d -exec chmod 775 {} \;
chmod 600 "$APP_DIR/.env"

success "Application deployed and permissions set."

# ── F. NGINX VHOST ────────────────────────────────────────────────────────────
info "=== F. Nginx Virtual Host ==="

NGINX_CONF=/etc/nginx/sites-available/cryptoinvest.conf
if [ ! -f "$NGINX_CONF" ]; then
  sed "s/__DOMAIN__/${DOMAIN}/g; s/listen 80;/listen ${HTTP_PORT};/g" \
    "$APP_DIR/../deploy/nginx/cryptoinvest.conf" 2>/dev/null > "$NGINX_CONF" || \
  cat > "$NGINX_CONF" <<NGINXEOF
server {
    listen ${HTTP_PORT};
    server_name ${DOMAIN};

    root ${APP_DIR}/public;
    index index.php;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    location ~ /\\. { deny all; }
    location ~ ^/(vendor|storage|config|database|cli)/ { deny all; }

    location ~* \\.(css|js|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf)\$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files \$uri \$uri/ /index.php?\$query_string;
    }

    location ~ \\.php\$ {
        include        fastcgi_params;
        fastcgi_pass   unix:/run/php/php8.1-fpm.sock;
        fastcgi_param  SCRIPT_FILENAME \$realpath_root\$fastcgi_script_name;
        fastcgi_index  index.php;
    }

    access_log /var/log/nginx/cryptoinvest_access.log;
    error_log  /var/log/nginx/cryptoinvest_error.log warn;
}
NGINXEOF
fi

ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/cryptoinvest.conf

if ! systemctl is-active --quiet nginx; then
  systemctl enable nginx
  systemctl start nginx
fi

nginx -t && systemctl reload nginx && success "Nginx configured and reloaded." || warn "Nginx config test failed — check $NGINX_CONF"

# Attempt Let's Encrypt cert (only if domain resolves)
if [[ "$DOMAIN" != "invest.example.com" ]] && [[ "$HTTP_PORT" == "80" ]]; then
  HOST_IP=$(dig +short "$DOMAIN" 2>/dev/null | head -1 || true)
  SERVER_IP=$(curl -s https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')
  if [[ "$HOST_IP" == "$SERVER_IP" ]]; then
    info "Requesting Let's Encrypt certificate for $DOMAIN..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "admin@$DOMAIN" || \
      warn "certbot failed. You can run it manually later: certbot --nginx -d $DOMAIN"
    # Update APP_URL in .env
    sed -i "s|APP_URL=http://|APP_URL=https://|" "$APP_DIR/.env" && \
      success "APP_URL updated to HTTPS."
  else
    warn "DNS for $DOMAIN ($HOST_IP) does not resolve to this server ($SERVER_IP). Skipping certbot."
  fi
fi

# ── G. CRON JOBS ─────────────────────────────────────────────────────────────
info "=== G. Setting up cron jobs ==="

CRON_FILE=/etc/cron.d/cryptoinvest
if [ ! -f "$CRON_FILE" ]; then
  cp "$APP_DIR/../deploy/cron/cryptoinvest" "$CRON_FILE" 2>/dev/null || \
  cat > "$CRON_FILE" <<CRONEOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# Poll payments every minute
* * * * * www-data /usr/bin/php ${APP_DIR}/cli/poll_payments.php >> ${APP_DIR}/storage/logs/poll_payments.log 2>&1

# Accrue ROI hourly
0 * * * * www-data /usr/bin/php ${APP_DIR}/cli/accrue_roi.php >> ${APP_DIR}/storage/logs/accrue_roi.log 2>&1

# Send daily reports at 08:00 UTC
0 8 * * * www-data /usr/bin/php ${APP_DIR}/cli/send_daily_reports.php >> ${APP_DIR}/storage/logs/daily_reports.log 2>&1
CRONEOF
  chmod 644 "$CRON_FILE"
  success "Cron jobs installed."
else
  success "Cron file already exists — not modified."
fi

# ── H. FIREWALL ───────────────────────────────────────────────────────────────
info "=== H. Firewall ==="

if command -v ufw &>/dev/null; then
  ufw allow OpenSSH  2>/dev/null || true
  ufw allow "$HTTP_PORT/tcp" 2>/dev/null || true
  if [[ "$HTTPS_PORT" != "80" ]]; then
    ufw allow "$HTTPS_PORT/tcp" 2>/dev/null || true
  fi
  ufw --force enable 2>/dev/null || warn "ufw could not be enabled (may already be on)."
  success "Firewall rules added."
fi

# ── I. POST-INSTALL VERIFICATION ─────────────────────────────────────────────
info "=== I. Post-install Verification ==="

# Test HTTP
HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" "http://localhost:${HTTP_PORT}/" -H "Host: $DOMAIN" || echo "000")
if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "302" ]]; then
  success "HTTP request returned $HTTP_CODE ✓"
else
  warn "HTTP request returned $HTTP_CODE — site may not be fully configured yet."
fi

# Test DB
php -r "
  try {
    \$pdo = new PDO('mysql:host=${DB_HOST_PHP};dbname=cryptoinvest_db', 'cryptoinvest_user', '${DB_PASS}');
    echo '[OK] Database connection successful.\n';
  } catch (Exception \$e) {
    echo '[WARN] Database connection failed: ' . \$e->getMessage() . '\n';
  }
" 2>/dev/null || warn "PHP DB test failed."

# Test AcceptXMR
if curl -s --max-time 3 http://127.0.0.1:8080/health &>/dev/null; then
  success "AcceptXMR health endpoint reachable ✓"
else
  warn "AcceptXMR health endpoint not reachable (service may still be starting)."
fi

# ── Save Credentials ──────────────────────────────────────────────────────────
cat > "$CREDS_FILE" <<CREDEOF
# =============================================================
# Crypto Investment Platform — Credentials
# Generated: $(date)
# =============================================================

[Domain]
  URL:             http://${DOMAIN}:${HTTP_PORT}

[Admin Login]
  Email:           admin@cryptoinvest.local
  Password:        ${ADMIN_PASS}

[Database]
  Host:            ${DB_HOST_PHP}:3306
  Database:        cryptoinvest_db
  User:            cryptoinvest_user
  Password:        ${DB_PASS}

[AcceptXMR]
  Internal URL:    http://127.0.0.1:8081
  External URL:    http://127.0.0.1:8080
  Internal Token:  ${INTERNAL_TOKEN}
  XMR Address:     ${XMR_PRIMARY_ADDRESS}
  Daemon URL:      ${DAEMON_URL}

[App]
  APP_SECRET:      ${APP_SECRET}
  APP_DIR:         ${APP_DIR}
  .env path:       ${APP_DIR}/.env

[Logs]
  Nginx access:    /var/log/nginx/cryptoinvest_access.log
  Nginx error:     /var/log/nginx/cryptoinvest_error.log
  PHP:             ${APP_DIR}/storage/logs/php_errors.log
  Poll payments:   ${APP_DIR}/storage/logs/poll_payments.log
  AcceptXMR:       journalctl -u acceptxmr -f
CREDEOF
chmod 600 "$CREDS_FILE"

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}  INSTALLATION COMPLETE!${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "  Site URL:       http://${DOMAIN}:${HTTP_PORT}"
echo -e "  Admin login:    admin@cryptoinvest.local / ${ADMIN_PASS}"
echo -e "  Credentials:    ${CREDS_FILE}"
echo -e "  App directory:  ${APP_DIR}"
echo ""
echo -e "  Next steps:"
echo -e "    1. Point DNS for ${DOMAIN} to this server's IP."
echo -e "    2. Run: certbot --nginx -d ${DOMAIN}   (for HTTPS)"
echo -e "    3. Update MAIL_* in ${APP_DIR}/.env for email notifications."
echo -e "${GREEN}================================================================${NC}"
