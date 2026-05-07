# CryptoInvest Website

A Pantera Capital–inspired blockchain investment platform built on PHP + MariaDB, accepting **Monero (XMR)** payments via [AcceptXMR](https://github.com/aceinnolab/acceptxmr).

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │                  User Browser                    │
                    └──────────────────────┬──────────────────────────┘
                                           │ HTTPS (443)
                    ┌──────────────────────▼──────────────────────────┐
                    │               Apache 2.4 (mod_php)               │
                    │         DocumentRoot: /var/www/cryptoinvest      │
                    └───────────────┬──────────────┬───────────────────┘
                                    │              │
               ┌────────────────────▼──┐    ┌──────▼──────────────────┐
               │  PHP 7.4 Application  │    │  AcceptXMR-Server       │
               │  (cryptoinvest)       │    │  Internal: :8081        │
               │  /var/www/cryptoinvest│    │  External: :8080        │
               └────────────┬──────────┘    └──────────────┬──────────┘
                            │                              │
               ┌────────────▼──────────┐    ┌─────────────▼──────────┐
               │  MariaDB              │    │  Monero Network         │
               │  Database:cryptoinvest│    │  (via monerod daemon)   │
               └───────────────────────┘    └────────────────────────┘
```

## Quick Installation

```bash
sudo bash website/scripts/install.sh
```

The installer will:
- Install Apache 2.4, PHP 7.4, MariaDB, and dependencies
- Clone and build AcceptXMR-Server
- Create the database with a random password
- Deploy all website files to `/var/www/cryptoinvest`
- Configure Apache virtual host
- Add a cron job for payment polling

### Requirements
- Ubuntu 20.04 LTS
- Root / sudo access
- Outbound internet access (for package installation and Rust)

---

## AcceptXMR Configuration

After installation, configure AcceptXMR by editing `/opt/xmrgateway/acceptxmr.yaml`:

```yaml
# Your Monero wallet's private view key
private_view_key: "your_private_view_key_here"

# Your Monero wallet's primary address
primary_address: "your_primary_address_here"

# Monero daemon RPC URL (local or remote)
daemon_url: "http://127.0.0.1:18081"

# Optional: daemon login (if daemon requires auth)
# daemon_login: "user:password"

# Internal API (used by website backend)
internal_address: "127.0.0.1:8081"

# External API (used by confirm.php for public invoice lookup)
external_address: "127.0.0.1:8080"

# Optional Bearer token for internal API security
# internal_api_token: "your_random_token_here"
```

Then start the service:
```bash
sudo systemctl start acceptxmr
sudo systemctl status acceptxmr
```

If using a Bearer token, set `INTERNAL_API_TOKEN` in the environment or update `/var/www/cryptoinvest/includes/config.php`:
```php
define('ACCEPTXMR_TOKEN', 'your_random_token_here');
```

---

## SSL / HTTPS Setup

```bash
# Replace with your actual domain
sudo certbot --apache -d yourdomain.com

# Update the Apache vhost ServerName first:
sudo nano /etc/apache2/sites-available/cryptoinvest.conf
# Change: ServerName invest.example.com
# To:     ServerName yourdomain.com

sudo systemctl reload apache2
```

---

## Admin Panel

The admin panel is available at `/admin/`. You must create an admin user manually:

```sql
-- Connect to MariaDB
mysql cryptoinvest

-- Insert admin user (replace 'yourpassword' with a strong password)
INSERT INTO admin_users (username, password_hash, role)
VALUES ('admin', '$argon2id$...', 'superadmin');
```

To generate the password hash in PHP:
```php
php -r "echo password_hash('your_strong_password', PASSWORD_ARGON2ID);"
```

---

## Adding Funds

Funds are managed directly in the database:

```sql
INSERT INTO funds (name, slug, description, min_investment_xmr, apy_target, tier, active)
VALUES (
    'My New Fund',
    'my-new-fund',
    'Description of the fund strategy.',
    0.500000000000,   -- minimum investment in XMR
    18.50,            -- target APY percentage
    1,                -- tier (1=Venture, 2=Token, 3=Liquid)
    1                 -- 1=active, 0=inactive
);
```

---

## Backup & Restore

### Manual Backup
```bash
sudo bash /var/www/cryptoinvest/scripts/backup.sh
```

Backups are stored in `/var/backups/cryptoinvest/` with 7-day retention.

### Automated Backup (Cron)
```bash
# Add to root's crontab for daily backups at 2am
echo "0 2 * * * root /bin/bash /var/www/cryptoinvest/scripts/backup.sh >> /var/log/cryptoinvest_backup.log 2>&1" \
    | sudo tee /etc/cron.d/cryptoinvest-backup
```

### Restore from Backup
```bash
# Restore database
gunzip -c /var/backups/cryptoinvest/TIMESTAMP/database.sql.gz | mysql cryptoinvest

# Restore files
tar -xzf /var/backups/cryptoinvest/TIMESTAMP/website.tar.gz -C /var/www/
```

---

## Payment Polling

The `scripts/poll_payments.php` script polls AcceptXMR for pending invoice updates and automatically marks investments as `confirmed` or `expired`. It runs every minute via cron (installed automatically).

To run manually:
```bash
php /var/www/cryptoinvest/scripts/poll_payments.php
```

Logs are written to `/var/log/cryptoinvest_poll.log`.

---

## Troubleshooting

### AcceptXMR not responding
```bash
sudo systemctl status acceptxmr
sudo journalctl -u acceptxmr -f
```

### Apache/PHP errors
```bash
sudo tail -f /var/log/apache2/cryptoinvest_error.log
```

### Database connection issues
```bash
# Test connection manually
mysql -u cryptoinvest -p cryptoinvest
# Enter the DB password from /var/www/cryptoinvest/includes/config.php
```

### Payment not confirming
- Check AcceptXMR logs for Monero sync status
- Verify the daemon is synced: `monerod status`
- Check poll_payments log: `tail -f /var/log/cryptoinvest_poll.log`
- Verify the private view key and primary address in `acceptxmr.yaml` are correct

### Session issues
- Ensure PHP session directory is writable by www-data
- Check `session.cookie_secure` is set correctly for your SSL setup

---

## Security Notes

- `config.php` is set to mode 640 (readable by www-data only)
- The `/includes/` and `/sql/` directories are blocked via `.htaccess` and Apache config
- All user inputs are sanitized with `htmlspecialchars()` and PDO prepared statements
- Passwords use `PASSWORD_ARGON2ID` with tuned memory/iteration parameters
- Login rate limiting: 5 attempts per 15 minutes per account
- CSRF tokens on all POST forms
- Session cookies: httponly, secure, samesite=Strict

---

## Legal Disclaimer

**This platform is for educational and demonstration purposes only.**

Accepting investments from the public may require registration and licensing under applicable securities laws, including but not limited to:
- **United States**: SEC registration, FINRA membership, Investment Advisers Act compliance
- **European Union**: MiFID II authorization
- **United Kingdom**: FCA authorization
- **Other jurisdictions**: Equivalent local financial services regulations

**Do not use this software to accept real funds without obtaining proper legal advice and regulatory approval in your jurisdiction.**

Cryptocurrency investments carry significant risk including total loss of capital. Past performance is not indicative of future results. Nothing in this software constitutes financial or investment advice.

---

## License

See [LICENSE-MIT](../LICENSE-MIT) and [LICENSE-APACHE](../LICENSE-APACHE).
