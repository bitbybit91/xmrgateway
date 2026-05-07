#!/usr/bin/env bash
# CryptoInvest installer script
# Installs AcceptXMR, MariaDB, Apache, PHP 7.4, and deploys the website
set -euo pipefail

# ===== Color variables =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
skip() { echo -e "${YELLOW}[SKIP]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
info() { echo -e "        $*"; }

# ===== Must run as root =====
if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (use sudo)."
fi

# ===== Check Ubuntu 20.04 =====
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" || "$VERSION_ID" != "20.04" ]]; then
        echo -e "${YELLOW}[WARN]${NC}  Expected Ubuntu 20.04, detected: ${PRETTY_NAME:-unknown}. Proceeding anyway."
    else
        ok "Ubuntu 20.04 detected."
    fi
else
    echo -e "${YELLOW}[WARN]${NC}  Cannot detect OS. Proceeding."
fi

REPO_DIR="/opt/xmrgateway"
REPO_URL="https://github.com/bitbybit91/xmrgateway.git"
REPO_BRANCH="copilot/update-website-updater-script"
WEB_ROOT="/var/www/cryptoinvest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ===== apt-get update =====
echo ""
info "Updating package lists..."
apt-get update -qq
ok "Package lists updated."

# ===== Install packages =====
PACKAGES=(
    apache2
    php7.4
    php7.4-mysql
    php7.4-curl
    php7.4-gd
    php7.4-mbstring
    php7.4-xml
    libapache2-mod-php7.4
    mariadb-server
    curl
    git
    unzip
    certbot
    python3-certbot-apache
    build-essential
    pkg-config
    libssl-dev
)

echo ""
info "Checking and installing required packages..."
TO_INSTALL=()
for pkg in "${PACKAGES[@]}"; do
    if dpkg -s "$pkg" &>/dev/null 2>&1; then
        skip "$pkg already installed."
    else
        TO_INSTALL+=("$pkg")
    fi
done

if [[ ${#TO_INSTALL[@]} -gt 0 ]]; then
    info "Installing: ${TO_INSTALL[*]}"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${TO_INSTALL[@]}"
    ok "Packages installed."
else
    ok "All packages already present."
fi

# ===== Enable Apache modules =====
echo ""
info "Enabling Apache modules..."
for mod in rewrite ssl headers; do
    if apache2ctl -M 2>/dev/null | grep -q "${mod}_module"; then
        skip "Apache module '$mod' already enabled."
    else
        a2enmod "$mod" -q
        ok "Enabled Apache module: $mod"
    fi
done

# ===== Clone repository =====
echo ""
if [[ -d "$REPO_DIR/.git" ]]; then
    skip "Repository already cloned at $REPO_DIR."
else
    info "Cloning repository to $REPO_DIR..."
    git clone --branch "$REPO_BRANCH" "$REPO_URL" "$REPO_DIR"
    ok "Repository cloned."
fi

# ===== Install Rust =====
echo ""
if command -v rustc &>/dev/null; then
    skip "Rust already installed: $(rustc --version)"
else
    info "Installing Rust via rustup..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path
    export PATH="$HOME/.cargo/bin:$PATH"
    ok "Rust installed: $(rustc --version)"
fi
export PATH="$HOME/.cargo/bin:$PATH"

# ===== Build AcceptXMR =====
echo ""
ACCEPTXMR_BIN="$REPO_DIR/target/release/acceptxmr-server"
if [[ -f "$ACCEPTXMR_BIN" ]]; then
    skip "AcceptXMR binary already built."
else
    info "Building AcceptXMR-Server (this may take several minutes)..."
    cd "$REPO_DIR"
    cargo build --release 2>&1 | tail -5
    ok "AcceptXMR-Server built successfully."
fi

# ===== Create systemd unit =====
echo ""
SYSTEMD_UNIT="/etc/systemd/system/acceptxmr.service"
if [[ -f "$SYSTEMD_UNIT" ]]; then
    skip "systemd unit already exists at $SYSTEMD_UNIT."
else
    info "Creating systemd service..."
    cat > "$SYSTEMD_UNIT" << 'UNIT'
[Unit]
Description=AcceptXMR Payment Server
After=network.target

[Service]
Type=simple
User=www-data
ExecStart=/opt/xmrgateway/target/release/acceptxmr-server
WorkingDirectory=/opt/xmrgateway
Restart=on-failure
RestartSec=5
Environment=RUST_LOG=info

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
    systemctl enable acceptxmr
    ok "systemd unit created and enabled."
fi

# ===== Setup MariaDB =====
echo ""
info "Configuring MariaDB..."

# Generate random password (use larger entropy source to ensure 32 chars after filtering)
DB_PASS=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32)
DB_NAME="cryptoinvest"
DB_USER="cryptoinvest"

systemctl start mariadb

# Secure MariaDB (remove anonymous users, test db, disable remote root)
mysql -u root << MYSQL_SECURE
DELETE FROM mysql.user WHERE User='';
DELETE FROM mysql.user WHERE User='root' AND Host NOT IN ('localhost', '127.0.0.1', '::1');
DROP DATABASE IF EXISTS test;
DELETE FROM mysql.db WHERE Db='test' OR Db='test\\_%';
FLUSH PRIVILEGES;
MYSQL_SECURE
ok "MariaDB secured."

# Create database and user
mysql -u root << MYSQL_SETUP
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'127.0.0.1';
FLUSH PRIVILEGES;
MYSQL_SETUP
ok "Database '$DB_NAME' and user '$DB_USER' created."

# Import schema
mysql -u root "$DB_NAME" < "$PROJECT_ROOT/sql/schema.sql"
ok "Schema imported."

# ===== Deploy website files =====
echo ""
info "Deploying website files to $WEB_ROOT..."
mkdir -p "$WEB_ROOT"
rsync -a --delete "$PROJECT_ROOT/" "$WEB_ROOT/" --exclude=".git" --exclude="target"
ok "Website files copied."

# ===== Write config.php with real credentials =====
CONFIG_FILE="$WEB_ROOT/includes/config.php"
sed -i "s|__DB_PASS__|${DB_PASS}|g" "$CONFIG_FILE"
ok "Database credentials written to config.php."

# ===== Set permissions =====
info "Setting file permissions..."
chown -R www-data:www-data "$WEB_ROOT"
find "$WEB_ROOT" -type d -exec chmod 755 {} \;
find "$WEB_ROOT" -type f -exec chmod 644 {} \;
chmod 640 "$CONFIG_FILE"
chmod +x "$WEB_ROOT/scripts/"*.php 2>/dev/null || true
ok "Permissions set."

# ===== Apache virtual host =====
echo ""
VHOST="/etc/apache2/sites-available/cryptoinvest.conf"
if [[ -f "$VHOST" ]]; then
    skip "Apache vhost already exists."
else
    info "Creating Apache virtual host..."
    cat > "$VHOST" << VHOST_CONF
<VirtualHost *:80>
    ServerName invest.example.com
    DocumentRoot ${WEB_ROOT}/public

    <Directory "${WEB_ROOT}/public">
        AllowOverride All
        Require all granted
        Options -Indexes +FollowSymLinks
    </Directory>

    # Block access to includes and sql
    <DirectoryMatch "${WEB_ROOT}/(includes|sql|scripts)">
        Require all denied
    </DirectoryMatch>

    # Security headers
    Header always set X-Frame-Options "SAMEORIGIN"
    Header always set X-Content-Type-Options "nosniff"
    Header always set X-XSS-Protection "1; mode=block"
    Header always set Referrer-Policy "strict-origin-when-cross-origin"

    ErrorLog \${APACHE_LOG_DIR}/cryptoinvest_error.log
    CustomLog \${APACHE_LOG_DIR}/cryptoinvest_access.log combined
</VirtualHost>
VHOST_CONF
    a2ensite cryptoinvest
    ok "Virtual host created and enabled."
fi

# Test Apache config
apache2ctl configtest 2>&1 | grep -E "Syntax|Error" || true
apache2ctl configtest && ok "Apache config valid." || err "Apache config test failed."
systemctl reload apache2
ok "Apache reloaded."

# ===== Cron for poll_payments.php =====
echo ""
CRON_CMD="* * * * * /usr/bin/php ${WEB_ROOT}/scripts/poll_payments.php >> /var/log/cryptoinvest_poll.log 2>&1"
if crontab -u www-data -l 2>/dev/null | grep -qF "poll_payments.php"; then
    skip "Cron job already exists."
else
    (crontab -u www-data -l 2>/dev/null; echo "$CRON_CMD") | crontab -u www-data -
    ok "Cron job added for www-data (every minute)."
fi

# ===== Summary =====
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} CryptoInvest Installation Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
info "Web Root:       $WEB_ROOT"
info "Database:       $DB_NAME"
info "DB User:        $DB_USER"
info "DB Password:    $DB_PASS"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
info "1. Update ServerName in $VHOST to your domain."
info "2. Run: certbot --apache -d yourdomain.com"
info "3. Start AcceptXMR: systemctl start acceptxmr"
info "4. Configure AcceptXMR view key and daemon URL."
info "5. Create admin user: INSERT INTO admin_users ..."
echo ""
echo -e "${YELLOW}IMPORTANT: Save your DB password:${NC} $DB_PASS"
echo ""
