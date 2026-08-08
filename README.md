[![BuildStatus](https://github.com/busyboredom/acceptxmr/workflows/CI/badge.svg)](https://img.shields.io/github/actions/workflow/status/busyboredom/acceptxmr/ci.yml?branch=main)

# XMR Gateway Capital — Investment Platform

This repository contains two things:

1. **A crypto investment website** (`webapp/`) — a PHP + MySQL website where users can register, deposit Monero (XMR) or Bitcoin (BTC), invest in managed funds, and request withdrawals. Prices are pulled live from CoinGecko.
2. **The AcceptXMR library and server** (`library/`, `server/`) — the underlying Rust payment-processing engine.

---

## Plain-English Quick-Start: Investment Website

### What You Need Before Starting

- A web server running **PHP 8.1 or newer** (Apache, Nginx, or anything similar)
- A **MySQL 8** database server
- **Composer** is not required — there are no PHP dependencies to install
- Your **XMR primary address** and **BTC receiving address** (from your wallet)
- Basic comfort with copy-pasting terminal commands

---

### Step 1 — Download or Clone the Code

If you have Git installed, open a terminal and run:

```bash
git clone https://github.com/bitbybit91/xmrgateway.git
cd xmrgateway
```

If you don't have Git, download the ZIP from GitHub and unzip it.

---

### Step 2 — Create the MySQL Database

Log into MySQL (replace `root` with your MySQL username if different):

```bash
mysql -u root -p
```

Then inside MySQL:

```sql
CREATE DATABASE xmrgateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'xmr_app'@'localhost' IDENTIFIED BY 'PICK_A_STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON xmrgateway.* TO 'xmr_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Now import the schema (tables + sample fund data):

```bash
mysql -u root -p xmrgateway < webapp/db/schema.sql
```

---

### Step 3 — Configure the Database Connection

Copy the example database config:

```bash
cp webapp/config/db.php webapp/config/db.local.php
```

Open `webapp/config/db.local.php` in any text editor and change these four lines to match your MySQL setup:

```php
define('DB_HOST', '127.0.0.1');
define('DB_NAME', 'xmrgateway');
define('DB_USER', 'xmr_app');
define('DB_PASS', 'PICK_A_STRONG_PASSWORD_HERE');  // same password as Step 2
```

> `db.local.php` is listed in `.gitignore` — it will never be committed and your password stays safe.

---

### Step 4 — Set Your Crypto Receiving Addresses

Copy the example config:

```bash
cp config/crypto.config.example.json config/crypto.config.json
```

Open `config/crypto.config.json` and fill in your own values:

```json
{
  "xmr": {
    "primaryAddress": "4YourXMRAddressHere...",
    "viewKey": "yourPrivateViewKey64HexChars",
    "restoreHeight": 0
  },
  "btc": {
    "receivingAddress": "bc1YourBTCAddressHere",
    "network": "mainnet"
  },
  "acceptxmr": {
    "daemonUrl": "https://your-monero-node:18081",
    "scanInterval": 1000
  }
}
```

**Tips:**
- Your **XMR primary address** starts with a `4` and is about 95 characters long. Find it in your Monero wallet.
- Your **private view key** is 64 hex characters. In Feather Wallet: Wallet → View Key.
- Your **BTC receiving address** is from your Bitcoin wallet (starts with `1`, `3`, or `bc1`).
- The `daemonUrl` is the address of a Monero node. Public ones: `https://xmr-node.cakewallet.com:18081` or `https://nodes.hashvault.pro:18081`.

> `config/crypto.config.json` is gitignored — your keys are safe.

---

### Step 5 — Point Your Web Server at `webapp/`

**Apache example** — add to your virtual host or `.htaccess`:

```apache
DocumentRoot /path/to/xmrgateway/webapp
DirectoryIndex index.php
```

Make sure `mod_rewrite` is enabled if you want clean URLs (optional).

**Nginx example:**

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    root /path/to/xmrgateway/webapp;
    index index.php;

    location ~ \.php$ {
        fastcgi_pass unix:/run/php/php8.3-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }
}
```

**Local testing** — PHP has a built-in server, great for trying things out:

```bash
cd webapp
php -S localhost:8080
```

Then open `http://localhost:8080` in your browser.

---

### Step 6 — Open the Website

Go to your site in a browser. You should see:

- The **landing page** with all four investment funds listed.
- An **Open Account** button — create a user to test login and dashboard.
- The **dashboard** lets you (when you fill it in) deposit, invest, and withdraw.

---

### How the Investment Flow Works

1. **Register / Log in** — any email + password (8 chars minimum).
2. **Deposit** — choose XMR or BTC, enter a USD amount. The system fetches the live price from CoinGecko and tells you the exact coin amount to send. Send it to the displayed address. An admin confirms the deposit and credits your USD balance.
3. **Invest** — once you have a USD balance, pick a fund and invest between **$250 and $1,000,000**.
4. **Withdraw** — request a withdrawal in XMR or BTC. The USD is deducted instantly; an admin processes the crypto transfer within 24 hours.

---

### CoinGecko Pricing

Prices are fetched from the **CoinGecko free public API** — no API key needed. Results are cached for 60 seconds to avoid rate limits. If CoinGecko is temporarily unavailable, the last cached price is used.

---

### File Layout

```
webapp/
├── index.php                  ← Landing page with fund listings
├── api/
│   └── prices.php             ← CoinGecko price proxy (called by JS)
├── auth/
│   ├── login.php
│   ├── register.php
│   └── logout.php
├── config/
│   ├── app.php                ← Site settings, crypto addresses, limits
│   ├── db.php                 ← Database credentials template
│   └── db.local.php           ← Your real credentials (gitignored, you create this)
├── dashboard/
│   ├── index.php              ← Account overview
│   ├── deposit.php            ← Create a deposit
│   ├── withdraw.php           ← Request a withdrawal
│   └── invest.php             ← Invest in a fund
├── db/
│   └── schema.sql             ← Run once to create all tables + seed funds
├── includes/
│   ├── auth_guard.php         ← Login check + CSRF helpers
│   ├── header.php             ← Navigation bar
│   └── footer.php             ← Footer + JS includes
└── assets/
    ├── css/style.css          ← Dark finance theme (Bootstrap 5 customisation)
    └── js/app.js              ← CoinGecko conversion, live price display
```

---

### Security Notes

- Passwords are hashed with **bcrypt** (cost 12).
- All forms are protected with **CSRF tokens**.
- User input is escaped with `htmlspecialchars()` before display.
- Database queries use **PDO prepared statements** — SQL injection is not possible.
- Session cookies are `HttpOnly` and `SameSite=Strict`.
- Your private view key and database password are **never committed** to Git.

---

### Frequently Asked Questions

**Do I need to install Composer or npm?**
No. The investment website uses no PHP dependencies and includes Bootstrap via CDN.

**Is this ready for production?**
It is a complete, working foundation. Before going live you should:
- Enable HTTPS (get a free cert from [Let's Encrypt](https://letsencrypt.org/)).
- Set a strong `APP_SECRET` in `webapp/config/app.php`.
- Add an admin interface to manually confirm deposits and approve withdrawals.
- Consider restricting `webapp/config/` from web access (place config outside webroot or deny via server config).

**How do I add more funds?**
Insert a row into the `funds` table in MySQL:

```sql
INSERT INTO funds (slug, name, description, strategy, target_return, risk_level)
VALUES ('my-fund', 'My New Fund', 'Description here', 'Strategy here', '20 % p.a.', 'Medium');
```

**The prices show "—" instead of numbers.**
The browser calls `/api/prices.php` which proxies CoinGecko. If it fails, check that PHP can make outbound HTTP requests (`allow_url_fopen = On` in `php.ini`), or that your server is not blocking outbound connections.

---

# `AcceptXMR`: Accept Monero in Your Application
`AcceptXMR` aims to provide a simple, reliable, and efficient means to track
monero payments.

To track payments, `AcceptXMR` generates subaddresses using your private view
key and primary address. It then watches for monero sent to that subaddress
using a monero daemon of your choosing, updating the UI in realtime and
optionally performing a configurable callback once payment is confirmed.

For a batteries-included payment gateway, see
[`AcceptXMR-Server`](./server/).

For a slim & performant library to use in your rust applications, see
[`AcceptXMR`](./library/).

## Static Frontend

In addition to the full Rust server, this repository ships a **static site
generator** that builds a self-contained frontend into `dist/` using only
Node.js. The generated files can be served by any static file host (GitHub
Pages, Nginx, Caddy, `python3 -m http.server`, etc.) without a running Rust
process.

### Quick Start

**1. Configure your crypto addresses**

```bash
cp config/crypto.config.example.json config/crypto.config.json
```

Open `config/crypto.config.json` and replace the placeholder values:

```json
{
  "xmr": {
    "primaryAddress": "<your XMR primary address starting with 4>",
    "viewKey": "<your 64-char hex private view key>",
    "restoreHeight": 0
  },
  "btc": {
    "receivingAddress": "<your BTC address>",
    "network": "mainnet"
  },
  "acceptxmr": {
    "daemonUrl": "https://your-monerod-node:18081",
    "scanInterval": 1000
  }
}
```

> **Security:** `config/crypto.config.json` is listed in `.gitignore` and must
> never be committed. The private view key is used only at build time for
> validation and is never written to the generated output.

**2. Build**

```bash
npm run build
```

The build script validates all addresses and fails with a clear error message if
anything is wrong. On success it writes the `dist/` directory.

**3. Serve**

```bash
# Any of the following work:
npx serve dist/
python3 -m http.server --directory dist 8080
# Or point Nginx / Caddy / GitHub Pages at the dist/ folder.
```

The `dist/config.js` file exposes your (browser-safe) configuration as
`window.CRYPTO_CONFIG` so the frontend JavaScript can reference your addresses
without any server-side rendering.

## Key Advantages
* View pair only, no hot wallet.
* Subaddress based. 
* Pending invoices can be stored persistently, enabling recovery from power
  loss. 
* Number of confirmations is configurable per-invoice.
* Ignores transactions with timelocks.
* Tracks used stealth addresses to mitigate the [burning
  bug](https://www.getmonero.org/2018/09/25/a-post-mortum-of-the-burning-bug.html).
* Payment can occur over multiple transactions.

## Security
`AcceptXMR` is non-custodial, and does not require a hot wallet. However, it
does require your private view key and primary address for scanning outputs. If
keeping these private is important to you, please take appropriate precautions
to secure the platform you run your application on.

Care is taken to protect users from malicious transactions containing timelocks
or duplicate output keys (i.e. the burning bug). For the best protection against
the burning bug, it is recommended that users use a dedicated wallet or account
index for `AcceptXMR` that is not used for any other purpose. The payment
gateway's initial height should also be set to the wallet's restore height.
These measures allow `AcceptXMR` to keep a full inventory of used output keys so
that duplicates can be reliably identified.

Also note that anonymity networks like TOR are not currently supported for RPC
calls. This means that your network traffic will reveal that you are interacting
with the monero network.

## Reliability
`AcceptXMR` strives for reliability, but that attempt may not be successful. It
is young and unproven, and relies on several crates which are undergoing rapid
changes themselves. For example, one of the built-in storage layer
implementations ([`Sled`](https://docs.rs/sled)) is still in beta.

That said, `AcceptXMR` can survive unexpected power loss thanks to the ability
to flush pending invoices to disk each time new blocks/transactions are scanned.
A best effort is made to keep the scanning thread free any of potential panics,
and RPC calls in the scanning thread are logged on failure and repeated next
scan. In the event that an error does occur, the liberal use of logging within
`AcceptXMR` will hopefully facilitate a speedy diagnosis and correction.

Use `AcceptXMR` at your own risk.

## Performance
It is recommended that you host your own monero daemon on the same local
network. Network and daemon slowness are the primary cause of high invoice
update latency in the majority of use cases.

To reduce the average latency before receiving invoice updates, you may also
consider lowering the gateway's scanning interval below the default of 1 second.
If using the `AcceptXMR` library, this can be done using the `scan_interval`
method of the `PaymentGatewayBuilder`. If using the standalone
`AcceptXMR-Server`, the scanning interval can be set in config.

Note that lowering the gateway's scanning interval will do nothing if latency to
your chosen node is slower than the scan interval.

## License
Licensed under either of

 * Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or
   http://www.apache.org/licenses/LICENSE-2.0)
 * MIT license ([LICENSE-MIT](LICENSE-MIT) or
   http://opensource.org/licenses/MIT)

at your option.

## Contribution
Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in the work by you, as defined in the Apache-2.0 license, shall be
dual licensed as above, without any additional terms or conditions.

### Donations
AcceptXMR is a hobby project which generates no revenue for the developer(s).
Donations from generous users and community members help keep it economically
viable to work on.

XMR:
`82assiV5dy7guoxxV7vSReZTyY5rGMrWg6BsfvFqiEKRcTiDs7LGMpg5dF5gXVGUWPEXQxyt8SNYx8L8HiGAzvtBK3eJ3EY`
