# Crypto Investment Platform — Operating Guide

A Pantera-style institutional crypto investment website built on PHP 8.1 + Twig + MariaDB, with [AcceptXMR](https://github.com/bitbybit91/xmrgateway) as the Monero payment backend.

---

## Quick Start

```bash
# On Ubuntu 20.04, as root:
git clone https://github.com/bitbybit91/xmrgateway.git /opt/xmrgateway
cd /opt/xmrgateway
git checkout copilot/create-crypto-investment-website
sudo bash install.sh
```

The installer will prompt you for:
- Your domain (e.g. `invest.example.com`)
- Your XMR primary wallet address
- Your XMR private view key (stored encrypted at `/opt/acceptxmr/.env`)

All generated credentials are saved to `/root/cryptoinvest_credentials.txt` (chmod 600).

---

## Architecture

```
/var/www/cryptoinvest/       ← PHP application
/opt/acceptxmr/              ← AcceptXMR Rust binary + config
/etc/nginx/sites-enabled/    ← cryptoinvest.conf Nginx vhost
/etc/systemd/system/         ← acceptxmr.service
/etc/cron.d/cryptoinvest     ← scheduled tasks
```

### Payment Flow

1. User selects a plan → enters USD amount
2. Backend converts USD → XMR piconeros via CoinGecko
3. Backend calls AcceptXMR internal API (`POST /invoice`) → gets invoice ID + address
4. User sees payment page with QR code and countdown
5. AcceptXMR detects on-chain payment, calls `POST /payment/callback`
6. `poll_payments.php` (cron, every 1 min) also polls AcceptXMR for any missed callbacks
7. On confirmation: investment activates, user receives email
8. `accrue_roi.php` (hourly cron) adds hourly ROI to `roi_accruals` + `transactions` tables
9. User requests withdrawal → admin approves/rejects → email notification

---

## Configuring the XMR Wallet

Edit `/opt/acceptxmr/acceptxmr.yaml`:
```yaml
wallet:
  primary-address: YOUR_XMR_ADDRESS
  account-index: 0
  restore-height: null   # set to current block height for a fresh wallet

daemon:
  url: https://node.community.rino.io:18081   # or your own node
```

Edit `/opt/acceptxmr/.env`:
```
PRIVATE_VIEWKEY=your_64char_hex_viewkey
INTERNAL_API_TOKEN=your_secret_token
```

Then restart: `systemctl restart acceptxmr`

---

## Adding / Editing Investment Plans

**Via Admin Dashboard:**
1. Log in at `https://yourdomain.com/login` as admin
2. Navigate to **Admin → Plans**
3. Fill in the "Add New Plan" form (name, ROI %, duration, min/max USD)
4. Click **Create Plan**

**Via MySQL:**
```sql
INSERT INTO plans (name, slug, description, min_amount_usd, max_amount_usd, daily_roi_percent, duration_days, type, is_active)
VALUES ('My Plan', 'my-plan', 'Description', 500.00, 50000.00, 0.1200, 60, 'liquid_token', 1);
```

---

## Backup Procedure

```bash
# 1. Database
mysqldump -u root cryptoinvest_db | gzip > /root/backups/db_$(date +%F).sql.gz

# 2. Application files (including .env)
tar czf /root/backups/app_$(date +%F).tar.gz /var/www/cryptoinvest

# 3. AcceptXMR DB
tar czf /root/backups/xmr_$(date +%F).tar.gz /opt/acceptxmr/AcceptXMR_DB /opt/acceptxmr/.env

# Automate with cron:
echo "0 3 * * * root mysqldump -u root cryptoinvest_db | gzip > /root/backups/db_\$(date +\%F).sql.gz" \
  >> /etc/cron.d/cryptoinvest_backup
```

---

## Updating Without Disrupting Other Sites

The installer only touches:
- `/var/www/cryptoinvest` — application files
- `/etc/nginx/sites-available/cryptoinvest.conf` — new vhost (symlinked to sites-enabled)
- `/etc/systemd/system/acceptxmr.service` — new systemd unit
- `/opt/acceptxmr` — AcceptXMR binary + config
- `/etc/cron.d/cryptoinvest` — cron jobs

To update the PHP application:
```bash
cd /opt/xmrgateway
git pull
rsync -a --exclude='.env' --exclude='vendor' --exclude='storage' website/ /var/www/cryptoinvest/
cd /var/www/cryptoinvest
COMPOSER_ALLOW_SUPERUSER=1 composer install --no-dev --optimize-autoloader
chown -R www-data:www-data /var/www/cryptoinvest
nginx -t && systemctl reload nginx
```

To update AcceptXMR:
```bash
cd /opt/acceptxmr
git pull
cargo build --release --bin acceptxmr-server
systemctl restart acceptxmr
```

---

## Monitoring & Logs

```bash
# Live application logs
tail -f /var/www/cryptoinvest/storage/logs/php_errors.log
tail -f /var/log/nginx/cryptoinvest_error.log

# Cron job logs
tail -f /var/www/cryptoinvest/storage/logs/poll_payments.log
tail -f /var/www/cryptoinvest/storage/logs/accrue_roi.log

# AcceptXMR service
journalctl -u acceptxmr -f

# Payment gateway health
curl http://127.0.0.1:8080/health
```

---

## Verification Checklist

After installation, an operator should verify:

- [ ] `curl http://yourdomain.com/` returns HTTP 200
- [ ] `curl http://yourdomain.com/api/health` returns `{"status":"ok"}`
- [ ] `curl http://127.0.0.1:8080/health` returns 200 (AcceptXMR online)
- [ ] Admin login works at `/login` with credentials from `/root/cryptoinvest_credentials.txt`
- [ ] Investment plans appear on homepage and `/funds`
- [ ] Creating a test investment reaches the payment page with QR code
- [ ] Cron jobs listed in `/etc/cron.d/cryptoinvest` — check with `crontab -l`
- [ ] MariaDB accessible: `mysql -u cryptoinvest_user -p cryptoinvest_db`
- [ ] `/var/www/cryptoinvest/.env` is chmod 600 and not world-readable
- [ ] HTTPS working (if certbot was run): `curl -I https://yourdomain.com/`

---

## Security Notes

- `.env` and `storage/` are blocked by Nginx config — never served to clients
- All passwords hashed with bcrypt cost 12
- CSRF protection on every POST form
- Session cookies: HttpOnly + Secure + SameSite=Strict
- AcceptXMR internal API (port 8081) is bound to 127.0.0.1 only — not exposed
- Admin password is rotated at install time and printed to credentials file only
