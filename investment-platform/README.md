# Investment Platform — Payment Button Scanner + XMR Converter

A drop-in JavaScript module that automatically detects payment/investment
buttons on any static HTML page, resolves or assigns dollar amounts, and
displays the equivalent **Monero (XMR)** amount in real time using a live
price feed. No backend required beyond a CORS-friendly price API.

---

## File Structure

```
investment-platform/
├── inject.js              ← Single script tag to add to your page
├── scanner.js             ← DOM scanner — detects buttons & amounts
├── xmr-converter.js       ← Live XMR price fetcher + conversion logic
├── payment-overlay.js     ← Modal overlay shown on button click
├── payment-config.json    ← Tier config + currency settings
├── styles.css             ← Overlay and display styles
└── README.md              ← This file
```

---

## Quick Start

### 1. Copy the files

Place the entire `investment-platform/` folder somewhere your web server can
serve static files, e.g. `/assets/xmr/`.

### 2. Add a single `<script>` tag

Add this at the **end of `<body>`** (or in `<head>` with `defer`):

```html
<script src="/assets/xmr/inject.js"
        data-config="/assets/xmr/payment-config.json"></script>
```

That's it. The script automatically:

1. Loads `payment-config.json`.
2. Scans the page for payment/investment buttons.
3. Attaches a click handler that opens a Monero payment overlay.
4. Re-scans when the DOM changes (supports single-page apps).

---

## Configuration — `payment-config.json`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `currency` | string | `"USD"` | Fiat currency code for display. |
| `tiers` | array | 10 tiers $1k–$1M | Default investment tiers. See below. |
| `defaultTierIndex` | number | `0` | Which tier to apply when no amount is found on page. |
| `xmrPriceApiUrl` | string | CoinGecko | URL returning XMR price JSON. |
| `priceCacheDurationMs` | number | `60000` | How long (ms) to cache the live price. |
| `overlayTitle` | string | `"Pay with Monero (XMR)"` | Title shown in the overlay header. |
| `xmrPrecision` | number | `6` | Decimal places for XMR amounts. |
| `buttonTextPattern` | string | *(see below)* | Regex source for button text matching. |
| `buttonSelectorPattern` | string | *(see below)* | Regex source for class/id matching. |

### Default tiers

```json
[
  { "name": "Starter",      "amount": 1000    },
  { "name": "Basic",        "amount": 2500    },
  { "name": "Standard",     "amount": 5000    },
  { "name": "Advanced",     "amount": 10000   },
  { "name": "Professional", "amount": 25000   },
  { "name": "Enterprise",   "amount": 50000   },
  { "name": "Premium",      "amount": 100000  },
  { "name": "Elite",        "amount": 250000  },
  { "name": "Ultimate",     "amount": 500000  },
  { "name": "Platinum",     "amount": 1000000 }
]
```

Set `defaultTierIndex` to choose which tier is applied when a button has no
associated price. Values range from `0` (Starter / $1,000) to `9` (Platinum /
$1,000,000).

---

## Button Detection Rules

`scanner.js` uses a two-step detection strategy.

### Step 1 — Text matching (case-insensitive)

Buttons whose **visible text** (or `aria-label`) matches:

```
/(pay|invest|buy|checkout|subscribe|purchase|get\s+started|deposit|fund|contribute)/i
```

Examples that are matched: *Pay Now*, *Invest Today*, *Buy Plan*, *Checkout*,
*Subscribe*, *Purchase Tokens*, *Get Started*, *Deposit Funds*, *Fund Account*,
*Contribute*.

### Step 2 — Attribute matching (class / id / name / data-action)

Elements whose **`class`**, **`id`**, **`name`**, or **`data-action`**
attribute matches:

```
/(pay|invest|buy|checkout|cta|btn|button|action)/i
```

### Supported element types

The scanner queries for: `button`, `a`, `input[type="button"]`,
`input[type="submit"]`, `[role="button"]`, `[onclick]`, `.btn`, `.button`,
`.cta`.

---

## Amount Detection Rules

For each detected button, the scanner resolves a dollar amount in this order:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `data-amount` or `data-price` attribute on the button | `<button data-amount="499">Buy</button>` |
| 2 | Currency-formatted number inside the button's own text | `<button>Buy for $499</button>` |
| 3 | Currency-formatted number in a sibling or ancestor element | Price label nearby in the DOM |
| 4 | Configured default tier (fallback) | `defaultTierIndex: 2` → $5,000 |

Recognised currency formats: `$1,234.56`, `1234.56`, `USD 1234`, `€ 250`, etc.

---

## XMR Price Feed

By default, prices are fetched from the **CoinGecko** public API:

```
https://api.coingecko.com/api/v3/simple/price?ids=monero&vs_currencies=usd
```

A **CryptoCompare** mirror is used automatically as a fallback if CoinGecko
fails.

### Custom price relay (CORS)

If the host page's CSP or the browser's CORS policy blocks the external API,
set `xmrPriceApiUrl` to your own relay:

```json
{
  "xmrPriceApiUrl": "https://your-site.com/api/xmr-price"
}
```

Your relay should return JSON in **either** of these formats:

```json
{ "monero": { "usd": 170.50 } }     // CoinGecko format
{ "USD": 170.50 }                    // CryptoCompare format
```

---

## Providing a Monero Wallet Address

To display a receiving address in the overlay, use **any** of these methods:

### Option A — `data-xmr-address` on the button

```html
<button class="btn-pay"
        data-xmr-address="4AdUndXHHZ...">
  Invest Now
</button>
```

### Option B — `data-xmr-address` on a container element

The scanner walks up to 5 levels of ancestors:

```html
<div data-xmr-address="4AdUndXHHZ...">
  <p>$5,000 — Professional Plan</p>
  <button class="btn-invest">Get Started</button>
</div>
```

### Option C — Global `window.XMR_ADDRESS`

Set this before loading `inject.js`:

```html
<script>window.XMR_ADDRESS = "4AdUndXHHZ...";</script>
<script src="/assets/xmr/inject.js"></script>
```

---

## Inline Config Override

You can pass config without a JSON file:

```html
<script>
  window.XMR_CONFIG = {
    currency: "EUR",
    defaultTierIndex: 3,
    overlayTitle: "Invest with Monero"
  };
</script>
<script src="/assets/xmr/inject.js"></script>
```

`window.XMR_CONFIG` is merged on top of whatever `payment-config.json` contains
(or the built-in defaults if the file cannot be loaded).

---

## CSS Theming

All styles are namespaced under `#xmr-payment-overlay` and `.xmr-*` classes.
Override the CSS custom properties to match your brand:

```css
:root {
  --xmr-primary:      #your-brand-color;
  --xmr-surface:      #ffffff;
  --xmr-text:         #1a1a1a;
  --xmr-radius:       10px;
}
```

Dark mode and reduced-motion are supported automatically via `@media` queries.

---

## Browser Support

Works in all modern browsers (Chrome, Firefox, Safari, Edge) and IE 11+
(via graceful degradation — `WeakSet`/`MutationObserver` polyfills built-in).

---

## Security Notes

- This module is **non-custodial**: it only displays a wallet address and XMR
  amount. It never handles private keys or submits transactions.
- The XMR price is fetched over HTTPS. If you deploy a custom relay, ensure it
  is served over HTTPS as well.
- CSP: allow `connect-src https://api.coingecko.com` (and your relay domain)
  in your Content Security Policy.

---

## Full Integration Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Investment Plans</title>
</head>
<body>

  <!-- Option A: button with explicit price in text -->
  <section>
    <h2>Professional Plan — $25,000</h2>
    <button class="btn-invest cta"
            data-xmr-address="4AdUndXHHZrjcnVMBPFNMGLDGqDkfq59Q...">
      Invest Now
    </button>
  </section>

  <!-- Option B: button with data-amount attribute -->
  <section>
    <h2>Enterprise Plan</h2>
    <button data-amount="50000"
            data-xmr-address="4AdUndXHHZrjcnVMBPFNMGLDGqDkfq59Q...">
      Get Started
    </button>
  </section>

  <!-- Option C: no price detected → falls back to defaultTierIndex tier -->
  <section>
    <h2>Custom Plan</h2>
    <button class="pay-btn">Subscribe</button>
  </section>

  <!-- Inline config override (optional) -->
  <script>
    window.XMR_CONFIG   = { defaultTierIndex: 4 }; // Professional = $25,000
    window.XMR_ADDRESS  = "4AdUndXHHZrjcnVMBPFNMGLDGqDkfq59Q..."; // global fallback
  </script>

  <!-- Load the platform (one line) -->
  <script src="/assets/xmr/inject.js"
          data-config="/assets/xmr/payment-config.json"></script>

</body>
</html>
```

---

## Licence

This module is distributed under the same licence as the parent repository
(Apache-2.0 / MIT dual licence). See `LICENSE-APACHE` and `LICENSE-MIT` in the
repository root.
