# CHANGES.md

Summary of changes made to add a static site generator frontend to the AcceptXMR repository.

---

## Added

| File | Description |
|------|-------------|
| `config/crypto.config.example.json` | Committed template for crypto addresses and AcceptXMR settings. Copy to `config/crypto.config.json` and fill in real values before building. |
| `scripts/build.js` | Node.js static site generator. Reads `config/crypto.config.json`, validates all addresses, copies `server/static/` assets into `dist/`, emits `dist/config.js` (browser-safe `window.CRYPTO_CONFIG` global), and generates `dist/index.html` from `server/static/pay.html`. |
| `package.json` | Defines `npm run build` which invokes `scripts/build.js`. No new runtime dependencies; uses Node.js built-ins only. |

---

## Modified

| File | Change |
|------|--------|
| `.gitignore` | Added `/dist`, `/node_modules`, and `config/crypto.config.json` so real credentials and generated output are never committed. |
| `README.md` | Added a **Static Frontend** section describing how to copy the example config, fill in addresses, run `npm run build`, and serve `dist/` with any static file host. |

---

## Removed

None. **No Apache configuration files, `.htaccess` files, or server-side PHP/dynamic files were found in this repository.** The codebase already uses a pure Rust server (`AcceptXMR-Server`) for dynamic functionality. This change layer adds an optional static frontend build on top without touching any existing files.

If the project maintainer later adds Apache or PHP files, see the problem statement's verification checklist for removal criteria.

---

## Notes on existing files preserved as-is

- `server/static/pay.html`, `error.html`, `missing-invoice.html` — Tera-template HTML files used by the Rust server. Preserved unchanged; `build.js` reads `pay.html` as the index template and strips Tera variables for static serving.
- `server/static/acceptxmr.js`, `acceptxmr.css`, `vendor/qrcode.js` — copied verbatim into `dist/`.
- All Rust source (`library/`, `server/src/`) — untouched.
- `.env`, `acceptxmr.yaml`, `docker-compose.yml`, `Dockerfile` — untouched.

---

## Security notes

- The private XMR view key is read from `config/crypto.config.json` for validation only; it is **never written to `dist/config.js`** or any browser-facing file.
- `config/crypto.config.json` is listed in `.gitignore` to prevent accidental credential commits.
