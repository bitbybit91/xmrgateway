# Website Updater Tool

`website_updater.py` is a standalone Python 3.6+ script that updates a directory of static
HTML/PHP/CSS website files — restructuring directories, modernising the UI, adding SEO
optimisations, continent-based pricing, shipping selectors, and a live Monero/Bitcoin payment
page — **without deleting any existing files**.

---

## Deliverables

| File | Purpose |
|------|---------|
| `website_updater.py` | The complete updater script (standard library only) |
| `config.json` | Sample configuration — edit before running |
| `keywords.txt` | SEO keywords injected into every page (one per line) |
| `WEBSITE_UPDATER_README.md` | This document |

---

## What the Script Does

1. **Backs up** the entire website directory before making any changes.
2. **Ensures** `products/`, `css/`, `js/`, and `images/` directories exist.
3. **Writes** a modern dark-theme `css/style.css` and sorting/pricing `js/main.js`.
4. **Discovers** all `.html`, `.php`, `.css`, `.js`, and image files recursively.
5. **Checks and fixes broken internal links** — auto-corrects paths where the target
   file exists elsewhere in the tree; logs unresolvable broken links.
6. **Injects** `<link>` and `<script>` tags into existing pages for the shared CSS/JS.
7. **Injects SEO meta tags** (`keywords`, `description`, Open Graph) into every page,
   driven by your `keywords.txt`.
8. **Generates** `sitemap.xml` and an optimised `robots.txt`.
9. **Parses every HTML/PHP file** to extract product names, prices, descriptions, and
   images; **automatically infers categories** from content and file names.
10. **Enhances product pages** with continent/shipping selectors and a dynamic pricing
    block that recalculates the total in the browser.
11. **Generates category listing pages** with client-side sorting (price, name, quantity).
12. **Injects a category grid** into your existing `index.html/php`, or creates a new
    one if none exists.
13. **Generates a modern `payment.php`** that:
    - Reads order details from URL parameters (`?item=…&price=…&amount=…`)
    - Fetches live XMR and BTC prices from the free CoinGecko API (client-side JS — **no
      Python network calls**)
    - Displays your Monero wallet address and a QR code
    - Shows continent + shipping selectors with live total recalculation
    - "Waiting for Deposit" status indicator
    - Contact info (Wickr / email) from `config.json`
14. **Writes a detailed `update_log.txt`** in the website root.

> **CRITICAL:** The script **never deletes any files**. It only creates new files and
> modifies the text content of existing HTML/PHP files.

---

## Requirements

- Python 3.8 or later
- Standard library only — no `pip install` needed
- The website files must already exist in a local directory (USB drive, local folder, etc.)

---

## Quick Start

### 1 — Copy the tool files

Copy `website_updater.py`, `config.json`, and `keywords.txt` into the **same directory**
as your website files (the directory that contains `index.html` or `index.php`).

```
/usb/mysite/
├── index.html          ← your existing site
├── products/
│   ├── product1.html
│   └── product2.php
├── images/
├── website_updater.py  ← copy here
├── config.json         ← copy here
└── keywords.txt        ← copy here
```

### 2 — Edit `config.json`

Open `config.json` in any text editor and fill in:

| Key | Description |
|-----|-------------|
| `monero_wallet_address` | Your XMR receive address |
| `website_root` | Path to site root — use `"."` when the file is in the root |
| `keywords_file` | Path to your keywords file (default `"keywords.txt"`) |
| `site_url` | Your site's base URL (e.g. `http://yoursite.onion`) |
| `contact_wickr` | Your Wickr handle (shown on payment page) |
| `contact_email` | Your contact email (shown on payment page) |
| `continent_pricing` | Price multipliers by continent (North America = 1.0 base) |
| `shipping_methods` | Flat-rate shipping costs in USD |

### 3 — Edit `keywords.txt`

Add one SEO keyword or phrase per line. These are injected as `<meta name="keywords">`
into every HTML/PHP page.

### 4 — Dry-run first (recommended)

```bash
python website_updater.py --dry-run
```

This prints every change that *would* be made without modifying any files.

### 5 — Apply changes

```bash
python website_updater.py
```

A backup is automatically created **before** any changes are made:

```
/usb/website_backup_20250101_120000/   ← timestamped backup
/usb/mysite/                           ← updated site
```

---

## Command-Line Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would change; no files are written |
| `--config <path>` | Path to a `config.json` (default: `./config.json`) |
| `--root <path>` | Override the website root directory |

Examples:

```bash
# Preview only
python website_updater.py --dry-run

# Config in a different location
python website_updater.py --config /path/to/my_config.json

# Explicit root
python website_updater.py --root /media/usb/mysite
```

---

## Directory Structure

### Before

```
mysite/
├── index.html
├── payment.php          ← old static echo version
├── product-a.html
├── product-b.php
├── style.css
└── images/
    ├── img1.jpg
    └── img2.png
```

### After

```
mysite/
├── index.html           ← category grid injected
├── payment.php          ← replaced with modern client-side page
├── product-a.html       ← pricing controls injected
├── product-b.php        ← pricing controls injected
├── category_other.html  ← generated category page
├── sitemap.xml          ← generated
├── robots.txt           ← generated
├── update_log.txt       ← full change log
├── css/
│   └── style.css        ← modern dark theme
├── js/
│   └── main.js          ← sorting + pricing JS
└── images/
    ├── img1.jpg         ← untouched
    └── img2.png         ← untouched
```

---

## Idempotency

Running the script twice is safe. Generated sections are wrapped in HTML comments
(`<!-- AUTO-GENERATED … -->`) and replaced on subsequent runs rather than appended.

---

## Payment Flow

1. Visitor views a product page → selects region and shipping method → clicks
   **"Proceed to Payment"**.
2. Browser opens `payment.php?item=…&price=…&amount=…`.
3. The page fetches live XMR/BTC prices from CoinGecko **in the visitor's browser**
   (no server-side network calls required).
4. Visitor sends the displayed XMR amount to your wallet address.
5. Visitor contacts you (Wickr/email) with their TXID and shipping details.

> The Python script itself makes **zero network calls**. All API communication is
> client-side JavaScript embedded in the generated HTML.

---

## Uploading to Apache

After running the script, upload the entire updated directory to your Apache web server.
No server-side configuration changes are needed — all dynamic behaviour is client-side
JavaScript. The `payment.php` file uses only HTML and embedded JS (no PHP logic).

---

## License

Same as the parent project (Apache-2.0 / MIT dual licence).
