[![Build Status](https://github.com/busyboredom/acceptxmr/workflows/CI/badge.svg)](https://img.shields.io/github/actions/workflow/status/busyboredom/acceptxmr/ci.yml?branch=main)
[![Crates.io](https://img.shields.io/crates/v/acceptxmr.svg)](https://crates.io/crates/acceptxmr)
[![Documentation](https://docs.rs/acceptxmr/badge.svg)](https://docs.rs/acceptxmr)
[![MSRV](https://img.shields.io/badge/MSRV-1.76.0-blue)](https://blog.rust-lang.org/2024/02/08/Rust-1.76.0.html)
[![Docker Image Size](https://badgen.net/docker/size/busyboredom/acceptxmr/latest/amd64?icon=docker&label=Docker%20Size)](https://hub.docker.com/r/busyboredom/acceptxmr/)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](#12-license)

# AcceptXMR — Monero Payment Gateway

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [Environment Setup (No Physical Device Required)](#3-environment-setup-no-physical-device-required)
4. [Configuration](#4-configuration)
5. [Installation](#5-installation)
6. [Build](#6-build)
7. [Running Tests](#7-running-tests)
8. [Common Issues & Troubleshooting](#8-common-issues--troubleshooting)
9. [Project Structure](#9-project-structure)
10. [Scripts Reference](#10-scripts-reference)
11. [Contributing](#11-contributing)
12. [License](#12-license)

---

## 1. Project Overview

`AcceptXMR` is a non-custodial Monero (XMR) payment processing system composed
of two main deliverables that share a single Rust workspace:

- **`acceptxmr` (library)** — A slim, composable Rust library for tracking
  Monero payments inside any Rust application. It derives stealth subaddresses
  from your private view key, polls a Monero daemon for matching transactions,
  and notifies your code via async subscribers or HTTP callbacks.
- **`acceptxmr-server` (server)** — A batteries-included, standalone payment
  gateway built on top of the library. It exposes two HTTP/WebSocket APIs (one
  internal for your back-end, one external/user-facing) and ships a ready-made
  payment UI with Tera HTML templating.
- **`configure_site.py`** — A single-file Python 3.7+ generator (stdlib only,
  no internet required) that reads the `investment-platform/` source files and
  writes a complete, upload-ready PHP website with zero JavaScript, handling all
  XMR price conversion server-side.

### Key Features

- **View-key-only operation** — no hot wallet; your private spend key never
  leaves your control.
- **Subaddress-based invoicing** — every invoice receives its own unique
  Monero subaddress.
- **Persistent invoice storage** — SQLite, Sled, or in-memory backends;
  survives process restarts.
- **Configurable confirmations** — set required block confirmations per invoice.
- **Burning-bug mitigation** — tracks used stealth-address output keys across
  all historical and in-flight transactions.
- **Multi-transaction payments** — a single invoice accepts funds spread across
  multiple XMR transactions.
- **Real-time WebSocket push** — live payment-status updates pushed to the
  user's browser.
- **Callback support** — HTTP callbacks fired on every invoice state change,
  with configurable retry logic.
- **TLS + Bearer-token auth** — internal API is secured out of the box.
- **Cross-platform Docker image** — pre-built for `linux/amd64` and
  `linux/arm64`; published to Docker Hub as `busyboredom/acceptxmr`.
- **OpenAPI / Swagger UI** — interactive API docs served at runtime at
  `<host>:<port>/swagger-ui/`.
- **Zero-JavaScript PHP site generator** — `configure_site.py` produces a
  fully PHP-driven investment-tier payment page with no client-side logic.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Rust (edition 2021, MSRV 1.76) |
| Async runtime | Tokio 1 |
| HTTP server | Axum 0.7 |
| HTTP client | Hyper 1 + hyper-rustls |
| TLS | tokio-rustls / rustls |
| Serialisation | serde / serde\_json / serde\_yaml |
| Storage backends | SQLite (`sqlite` crate), Sled 0.34, in-memory |
| HTML templating | Tera 1 |
| CLI argument parsing | Clap 4 |
| Containerisation | Docker (multi-stage, multi-arch build) |
| CI/CD | GitHub Actions |
| Site generator | Python 3.7+ (stdlib only) |
| PHP site | PHP 7.4+ (generated; no framework) |

### Supported Platforms

| Platform | Method |
|----------|--------|
| Linux x86-64 | Native binary, Docker |
| Linux arm64 | Native binary, Docker |
| macOS x86-64 / Apple Silicon | Native binary |
| Windows x86-64 | Native binary (Rust toolchain required) |
| Any OCI-compatible host | Docker image `busyboredom/acceptxmr` |

---

## 2. Prerequisites

Install every tool listed below before proceeding to the Installation section.
Follow the steps in the order shown.

---

### 2.1 Git

| | |
|---|---|
| Minimum version | 2.39 |
| Download | <https://git-scm.com/downloads> |

**Install**

<details>
<summary>macOS</summary>

```bash
brew install git
```

</details>

<details>
<summary>Linux (Debian / Ubuntu)</summary>

```bash
sudo apt update && sudo apt install -y git
```

</details>

<details>
<summary>Windows</summary>

```powershell
winget install --id Git.Git -e --source winget
```

</details>

**Verify**

```bash
git --version
# Expected: git version 2.x.x or higher
```

---

### 2.2 Rust Toolchain (rustup)

The library and server are written in Rust. The minimum supported Rust version
(MSRV) is **1.76.0**. The CI pipeline also tests against the current `nightly`
toolchain.

| | |
|---|---|
| Minimum version | 1.76.0 |
| Download | <https://rustup.rs> |

**Install (macOS / Linux)**

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
# Reload your shell so that `cargo` is on $PATH
source "$HOME/.cargo/env"
```

**Install (Windows)**

1. Download `rustup-init.exe` from <https://rustup.rs>.
2. Run the installer and accept the default options.
3. Open a new PowerShell window.

**Verify**

```bash
rustc --version
# Expected: rustc 1.76.0 or higher
cargo --version
# Expected: cargo 1.76.0 or higher
```

**Install the nightly toolchain** (required for `cargo fmt --check` and
`cargo clippy` with all features):

```bash
rustup toolchain install nightly
rustup component add rustfmt clippy --toolchain nightly
```

---

### 2.3 Docker (optional — for container-based workflow)

Required only if you intend to run or build the Docker image.

| | |
|---|---|
| Minimum version | Docker Engine 24 / Docker Desktop 4.x |
| Download | <https://docs.docker.com/get-docker/> |

**Install (macOS)**

```bash
brew install --cask docker
open -a Docker   # starts the Docker Desktop application
```

**Install (Linux — Debian / Ubuntu)**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
```

**Install (Windows)**

Download and install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/).

**Verify**

```bash
docker --version
# Expected: Docker version 24.x.x or higher
docker info
# Expected: server info block with no errors
```

---

### 2.4 Python 3.7+ (for `configure_site.py` only)

Required only if you intend to run the PHP site generator.

| | |
|---|---|
| Minimum version | 3.7 |
| Download | <https://www.python.org/downloads/> |

**Install (macOS)**

```bash
brew install python@3.11
```

**Install (Linux — Debian / Ubuntu)**

```bash
sudo apt update && sudo apt install -y python3
```

**Install (Windows)**

```powershell
winget install --id Python.Python.3.11 -e --source winget
```

**Verify**

```bash
python3 --version   # macOS / Linux
python --version    # Windows
# Expected: Python 3.7.x or higher
```

---

### 2.5 A Monero Daemon (stagenet or mainnet)

The gateway requires a running `monerod` instance to scan the blockchain.
For local development you can use a public remote node (the default config
points at `xmr-node.cakewallet.com:18081`) — no local installation needed.

If you prefer a local stagenet node for fully offline development:

| | |
|---|---|
| Download | <https://www.getmonero.org/downloads/> |

```bash
# Start a stagenet daemon (downloads ~5 GB of stagenet blockchain)
monerod --stagenet --detach
```

---

## 3. Environment Setup (No Physical Device Required)

The entire project can be built, tested, and run on a single machine with no
physical device. Three software-only methods are described below. Choose the
one that best fits your workflow.

---

### Method A — Native Rust (fastest for development)

This method runs the gateway directly on your host OS using the Rust toolchain
installed in Section 2.2. No Docker, no VM required.

```bash
# 1. Clone the repository
git clone https://github.com/busyboredom/acceptxmr.git
cd acceptxmr

# 2. Install dependencies (downloaded automatically by cargo)
cargo fetch

# 3. Configure secrets (see Section 4)
cp .env .env.local   # edit .env.local with real values
```

Expected output of `cargo fetch`:

```
Blocking waiting for file lock on package cache
Downloading crates ...
  Downloaded acceptxmr v0.14.0
  ...
```

---

### Method B — Docker Compose (recommended for production-like testing)

Runs the server inside a container on your local machine. No Rust toolchain
required on the host.

```bash
# 1. Clone the repository
git clone https://github.com/busyboredom/acceptxmr.git
cd acceptxmr

# 2. Create the database directory (Docker bind-mount target)
mkdir -p AcceptXMR_DB

# 3. Copy and configure the example env file
cp .env .env.local   # edit with real values

# 4. Start the stack
docker compose up --build
```

Expected output:

```
[+] Building 12.3s (18/18) FINISHED
[+] Running 1/1
 ✔ Container acceptxmr-server-1  Started
acceptxmr-server-1  | [INFO  acceptxmr_server] Starting AcceptXMR-Server...
acceptxmr-server-1  | [INFO  acceptxmr_server] External API listening on 127.0.0.1:8080
acceptxmr-server-1  | [INFO  acceptxmr_server] Internal API listening on 127.0.0.1:8081
```

The external payment UI is available at <http://127.0.0.1:8080/pay?id=>.

---

### Method C — Pre-built Docker image (zero build time)

Pull the published image from Docker Hub and run it directly.

```bash
# 1. Pull the image
docker pull busyboredom/acceptxmr:latest

# 2. Create database and cert directories
mkdir -p AcceptXMR_DB server/tests/testdata/cert

# 3. Start the container
docker run -d \
  --name acceptxmr \
  --network host \
  --mount type=bind,source="$(pwd)/AcceptXMR_DB",target=/AcceptXMR_DB \
  --mount type=bind,source="$(pwd)/server/tests/testdata/cert",target=/server/tests/testdata/cert \
  --mount type=bind,source="$(pwd)/acceptxmr.yaml",target=/acceptxmr.yaml \
  --env-file .env \
  busyboredom/acceptxmr:latest
```

Expected output:

```
<container-id>
```

Confirm the container is running:

```bash
docker ps --filter name=acceptxmr
```

Expected output:

```
CONTAINER ID   IMAGE                          COMMAND                  CREATED        STATUS        PORTS     NAMES
abc123def456   busyboredom/acceptxmr:latest   "./acceptxmr-server"     3 seconds ago  Up 2 seconds            acceptxmr
```

---

### Troubleshooting the environment setup

| Symptom | Cause | Fix |
|---------|-------|-----|
| `cargo: command not found` | Rust not on `$PATH` | Run `source "$HOME/.cargo/env"` then open a new terminal |
| `docker: command not found` | Docker not installed or not on `$PATH` | Re-run the Docker install steps in Section 2.3 |
| `permission denied` when running Docker | User not in `docker` group | `sudo usermod -aG docker "$USER" && newgrp docker` |
| Container exits immediately with exit code 1 | Missing `acceptxmr.yaml` or secrets | Ensure `acceptxmr.yaml` is present in the working directory and `.env` is set |
| Port 8080 already in use | Another process is bound to the port | Change `external-api.port` in `acceptxmr.yaml` to an unused port (e.g. `9080`) |

---

## 4. Configuration

### 4.1 Primary configuration file — `acceptxmr.yaml`

The server reads its configuration from `acceptxmr.yaml` in the working
directory by default. An alternative path can be specified via:

- CLI flag: `acceptxmr-server --config-file /path/to/file.yaml`
- Environment variable: `CONFIG_FILE=/path/to/file.yaml`

If the file does not exist on startup, a default file is created automatically.

Below is a fully annotated example:

```yaml
external-api:
  # Port that end-users connect to (payment UI, GET /invoice, WebSocket).
  port: 8080
  # IPv4 address to bind. Use 0.0.0.0 to accept connections from all interfaces.
  ipv4: 127.0.0.1
  # IPv6 address to bind. Comment out to disable IPv6.
  ipv6: "::1"
  # Optional bearer token to restrict access. Requires TLS when set.
  # Prefer EXTERNAL_API_TOKEN environment variable.
  # token: "..."
  # Optional TLS configuration.
  # tls:
  #   cert: /path/to/certificate.pem
  #   key:  /path/to/privatekey.pem
  # Directory containing static files (HTML, CSS, JS) for the payment UI.
  static_dir: server/static/

internal-api:
  # Port that YOUR back-end uses to create / delete invoices.
  port: 8081
  ipv4: 127.0.0.1
  # ipv6: "::1"
  # Bearer token required by all internal API calls.
  # Prefer INTERNAL_API_TOKEN environment variable.
  # token: "supersecrettoken"
  tls:
    # Path to the TLS certificate (PEM format).
    cert: server/tests/testdata/cert/certificate.pem
    # Path to the matching private key (PEM format).
    key:  server/tests/testdata/cert/privatekey.pem
  static_dir: server/static/

callback:
  # Maximum number of pending callbacks to queue before dropping.
  queue-size: 1000
  # Maximum number of times a failed callback will be retried.
  # Set to null for unlimited retries.
  max-retries: 50

wallet:
  # Your Monero primary address (starts with "4" on mainnet).
  primary-address: "4613YiHLM6JMH4zejMB..."
  # account-index: 0       # default: 0
  # restore-height: null   # set to wallet restore height to speed up initial scan
  # private-viewkey is intentionally absent here — set it via PRIVATE_VIEWKEY env var.

daemon:
  # URL of the monerod RPC endpoint.
  url: "https://xmr-node.cakewallet.com:18081"
  # Uncomment if your node requires authentication.
  # login:
  #   username: "youruser"
  #   password is set via DAEMON_PASSWORD env var.
  # RPC call timeout in seconds.
  rpc-timeout: 30
  # Initial connection timeout in seconds.
  connection-timeout: 20

database:
  # Absolute or relative path to the SQLite/Sled database directory.
  path: AcceptXMR_DB/
  # Automatically delete expired invoices from the database.
  delete-expired: true

logging:
  # One of: ERROR, WARN, INFO, DEBUG, TRACE
  verbosity: DEBUG
```

---

### 4.2 Environment variables (secrets)

Secrets must **never** be placed in `acceptxmr.yaml` or committed to version
control. Set them via environment variables or a `.env` file in the working
directory.

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `PRIVATE_VIEWKEY` | **Yes** | Monero wallet private view key (64-char hex). | `ad2093a5705b9f33e6f0f0...` |
| `INTERNAL_API_TOKEN` | Recommended | Bearer token protecting the internal API. Must be used with TLS. | `a-very-long-random-string` |
| `EXTERNAL_API_TOKEN` | Optional | Bearer token protecting the external/user-facing API. Must be used with TLS. | `another-random-string` |
| `DAEMON_PASSWORD` | Conditional | Password for the Monero daemon RPC, if `daemon.login.username` is set in the config. | `supersecretpassword` |
| `CONFIG_FILE` | Optional | Override the path to `acceptxmr.yaml`. | `/etc/acceptxmr/config.yaml` |

**Fully commented `.env.example`**

```dotenv
# .env.example — copy to .env and fill in real values.
# Never commit the real .env file.

# -----------------------------------------------------------------------
# REQUIRED: Monero wallet private view key.
# Obtain it from your Monero wallet software:
#   CLI:  monero-wallet-cli --> viewkey
#   GUI:  Wallet --> Advanced --> Show Keys --> Private View Key
# 64 hex characters.
# -----------------------------------------------------------------------
PRIVATE_VIEWKEY=ad2093a5705b9f33e6f0f0c1bc1f5f639c756cdfc168c8f2ac6127ccbdab3a03

# -----------------------------------------------------------------------
# RECOMMENDED: Bearer token for the internal API (creates/deletes invoices).
# Generate a random token:
#   Linux / macOS: openssl rand -hex 32
#   Windows PowerShell: [Convert]::ToBase64String((1..32 | % { Get-Random -Max 256 }))
# Must be used together with TLS (internal-api.tls in acceptxmr.yaml).
# -----------------------------------------------------------------------
INTERNAL_API_TOKEN=supersecrettoken

# -----------------------------------------------------------------------
# OPTIONAL: Bearer token for the external (user-facing) API.
# Leave commented out unless you need to restrict access.
# -----------------------------------------------------------------------
# EXTERNAL_API_TOKEN=

# -----------------------------------------------------------------------
# CONDITIONAL: Monero daemon RPC password.
# Required only when daemon.login.username is set in acceptxmr.yaml.
# -----------------------------------------------------------------------
# DAEMON_PASSWORD=

# -----------------------------------------------------------------------
# OPTIONAL: Path to the configuration YAML file.
# Defaults to ./acceptxmr.yaml when not set.
# -----------------------------------------------------------------------
# CONFIG_FILE=/etc/acceptxmr/acceptxmr.yaml
```

---

### 4.3 Generating a self-signed TLS certificate (for local development)

The internal API uses TLS. For local development you can generate a self-signed
certificate with `openssl`:

```bash
mkdir -p server/tests/testdata/cert
openssl req -x509 \
  -newkey rsa:4096 \
  -keyout server/tests/testdata/cert/privatekey.pem \
  -out    server/tests/testdata/cert/certificate.pem \
  -days   365 \
  -nodes \
  -subj   "/CN=localhost"
```

For production, replace these files with a certificate issued by a trusted CA
(e.g. Let's Encrypt).

---

### 4.4 Generating an API bearer token

```bash
# Linux / macOS
openssl rand -hex 32

# Windows PowerShell
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Max 256) })
```

Place the output in your `.env` file as `INTERNAL_API_TOKEN`.

---

### 4.5 Switching between environments

| Environment | Recommended approach |
|-------------|----------------------|
| Development | Use public remote node (`xmr-node.cakewallet.com`); `acceptxmr.yaml` binds to `127.0.0.1`; `logging.verbosity: DEBUG` |
| Staging | Point `daemon.url` at a stagenet node; restrict to a local network; use a staging wallet |
| Production | Bind to `0.0.0.0`; use a trusted TLS cert; set all tokens; `logging.verbosity: INFO` or `WARN`; enable `delete-expired: true` |

---

## 5. Installation

Follow these steps on a clean machine. All commands are written for a standard
POSIX shell (bash / zsh) on Linux or macOS. Windows equivalents are shown where
they differ.

### Step 1 — Clone the repository

```bash
git clone https://github.com/busyboredom/acceptxmr.git
```

Expected output:

```
Cloning into 'acceptxmr'...
remote: Enumerating objects: ...
Resolving deltas: ..., done.
```

### Step 2 — Navigate into the project directory

```bash
cd acceptxmr
```

### Step 3 — (Docker path) Build and start the server

If you are using Docker, skip steps 4–7 and run:

```bash
# Copy the example env file and edit it
cp .env .env       # already exists; open in your editor
# Start with Docker Compose
mkdir -p AcceptXMR_DB
docker compose up --build
```

The server will be available at `http://127.0.0.1:8080`.

### Step 4 — (Native path) Install Rust dependencies

Cargo downloads and compiles all crate dependencies automatically:

```bash
cargo fetch
```

Expected output (abbreviated):

```
Blocking waiting for file lock on package cache
Downloading crates ...
  Downloaded tokio v1.x.x
  Downloaded axum v0.7.x
  ...
```

**Common error:** `error: failed to get ... (network error)`
→ Ensure you have internet access at this step. Dependencies are only
downloaded once; after that the build works offline.

### Step 5 — Copy and configure the environment file

```bash
cp .env .env          # file already contains example values — edit as needed
```

Open `.env` in your editor and set at minimum:

```dotenv
PRIVATE_VIEWKEY=<your 64-character hex private view key>
INTERNAL_API_TOKEN=<output of: openssl rand -hex 32>
```

### Step 6 — Verify the configuration is valid

The server validates configuration at startup. Run a quick dry-run to catch
mistakes before a full build:

```bash
# Set CONFIG_FILE to point at the test config to avoid modifying the real one
CONFIG_FILE=server/tests/testdata/config/config_full.yaml \
PRIVATE_VIEWKEY=ad2093a5705b9f33e6f0f0c1bc1f5f639c756cdfc168c8f2ac6127ccbdab3a03 \
INTERNAL_API_TOKEN=supersecrettoken \
  cargo run --bin acceptxmr-server 2>&1 | head -20
```

Press `Ctrl+C` to stop the server. Expected output (first few lines):

```
[INFO  acceptxmr_server] Starting AcceptXMR-Server...
[INFO  acceptxmr_server] External API listening on 127.0.0.1:8080
[INFO  acceptxmr_server] Internal API listening on 127.0.0.1:8081
```

### Step 7 — Verify the installation

In a second terminal, send a health-check request:

```bash
curl -s http://127.0.0.1:8080/invoice?id=invalid | head -c 200
```

Expected response (HTTP 400 or a JSON error body — proof the server is up):

```json
{"error":"invalid invoice ID"}
```

**Common error:** `curl: (7) Failed to connect to 127.0.0.1 port 8080`
→ The server is not yet running. Complete Step 6 first.

---

## 6. Build

### Development Build

Start the server in development mode with debug logging:

```bash
RUST_LOG=debug \
PRIVATE_VIEWKEY=<your-key> \
INTERNAL_API_TOKEN=<your-token> \
  cargo run
```

- External payment UI: `http://127.0.0.1:8080/pay?id=<invoice-id>`
- Internal API Swagger UI: `https://127.0.0.1:8081/swagger-ui/`
- External API Swagger UI: `http://127.0.0.1:8080/swagger-ui/`

To enable hot-recompilation as you edit source files, install `cargo-watch`:

```bash
cargo install cargo-watch
cargo watch -x run
```

---

### Production Build

Build an optimised release binary with link-time optimisation (LTO enabled in
`Cargo.toml`):

```bash
cargo build --release
```

Output artifact: `target/release/acceptxmr-server`

Expected build time on a modern laptop: approximately 3–6 minutes on the first
run (all dependencies compiled from source). Subsequent builds are incremental
and take 10–30 seconds.

**Pre-build step** — generate a TLS certificate if you do not already have one:

```bash
openssl req -x509 \
  -newkey rsa:4096 \
  -keyout server/tests/testdata/cert/privatekey.pem \
  -out    server/tests/testdata/cert/certificate.pem \
  -days 365 -nodes -subj "/CN=localhost"
```

**Run the release binary**

```bash
PRIVATE_VIEWKEY=<your-key> \
INTERNAL_API_TOKEN=<your-token> \
  ./target/release/acceptxmr-server
```

**Verify the build output**

```bash
# Check the binary exists and is executable
ls -lh target/release/acceptxmr-server

# Confirm it starts without errors
./target/release/acceptxmr-server --help
```

---

### Docker Production Build

Build the multi-arch Docker image locally (requires BuildKit / Docker Buildx):

```bash
# Build for the current platform only
docker build -t acceptxmr:local .

# Build for both amd64 and arm64 (requires QEMU binfmt on Linux)
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --tag acceptxmr:local \
  .
```

Expected output (abbreviated):

```
[+] Building 240.0s (18/18) FINISHED
 => CACHED [build 1/9] FROM docker.io/library/rust:1.76-slim-bookworm
 => [build 9/9] RUN ... cargo build --release
 => [final 2/3] COPY --from=build /acceptxmr-server/acceptxmr-server .
```

---

### CI/CD Build (Headless / Automated)

The project ships two GitHub Actions workflows.

**`rust.yml`** — runs on every push/PR:

```yaml
# .github/workflows/rust.yml (excerpt)
jobs:
  static_analysis:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3.3.0
      - name: Install Rust nightly
        uses: actions-rs/toolchain@v1.0.6
        with:
          toolchain: nightly
          override: true
          components: rustfmt, clippy
      - name: Rustfmt
        run: cargo fmt --all -- --check
      - name: Clippy
        run: cargo clippy --all-targets --all-features
      - name: Doc
        run: cargo doc --all-features --all
  build:
    strategy:
      matrix:
        rust: [1.76.0, nightly]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3.3.0
      - uses: Swatinem/rust-cache@v2.2.1
      - run: cargo build --verbose
      - run: cargo build --verbose --all-features
  test:
    strategy:
      matrix:
        rust: [1.76.0, nightly]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3.3.0
      - uses: Swatinem/rust-cache@v2.2.1
      - run: cargo test --verbose --all-features
```

**`docker.yml`** — builds and pushes the Docker image on tags and main-branch
merges:

```yaml
# .github/workflows/docker.yml (excerpt)
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to DockerHub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Injecting secrets in CI**

Add the following repository secrets in your GitHub repository settings
(`Settings → Secrets and variables → Actions → New repository secret`):

| Secret name | Value |
|-------------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token |

No interactive prompts are present in either workflow.

---

### PHP Site Generator Build (`configure_site.py`)

The generator requires no build step; run it directly:

```bash
# macOS / Linux
python3 configure_site.py

# Windows
python configure_site.py

# With explicit options
python3 configure_site.py \
  --repo-root . \
  --output ./site-output \
  --wallet 4YourMoneroPrimaryAddressHere
```

Output directory: `./site-output/` (created automatically).
Upload the entire contents of `site-output/` to any PHP 7.4+ web host.

---

## 7. Running Tests

All tests run via standard Cargo commands. No additional test framework
installation is required.

### Run all tests

```bash
cargo test --all-features
```

Expected output (abbreviated):

```
   Compiling acceptxmr v0.14.0 (library)
   Compiling acceptxmr-server v0.1.0 (server)
    Finished test [unoptimized + debuginfo] target(s) in 45.2s
     Running unittests src/lib.rs (target/debug/deps/acceptxmr-...)
test result: ok. 42 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
     Running tests/integration_tests/... (target/debug/deps/acceptxmr_server-...)
test result: ok. 18 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

### Run a single test file

```bash
# Run only tests in the server config module
cargo test --all-features -p acceptxmr-server config

# Run only tests in the library crate
cargo test --all-features -p acceptxmr
```

### Run a single named test

```bash
cargo test --all-features default
# Runs any test whose name contains "default"
```

### Run tests in verbose mode

```bash
cargo test --all-features -- --nocapture
```

### Run tests with the nightly toolchain

The CI pipeline tests against both MSRV (1.76.0) and nightly:

```bash
cargo +nightly test --all-features
```

### Run linting and formatting checks

```bash
# Check formatting (does not modify files)
cargo +nightly fmt --all -- --check

# Run Clippy with all features and all targets
cargo +nightly clippy --all-targets --all-features

# Build documentation (checks doc-comment validity)
cargo +nightly doc --all-features --all
```

### Code coverage (optional)

Install `cargo-tarpaulin` (Linux only):

```bash
cargo install cargo-tarpaulin
cargo tarpaulin --all-features --out Html --output-dir coverage/
# Open coverage/tarpaulin-report.html in a browser
```

---

## 8. Common Issues & Troubleshooting

| Error Message / Symptom | Cause | Fix |
|-------------------------|-------|-----|
| `please configure your monero primary address` (panic on startup) | `wallet.primary-address` is missing or empty in `acceptxmr.yaml` | Set `primary-address:` in `acceptxmr.yaml` to your Monero address starting with `4` |
| `please configure your monero private viewkey` (panic on startup) | `PRIVATE_VIEWKEY` env var is not set | Add `PRIVATE_VIEWKEY=<64-char hex key>` to `.env` and ensure the `.env` file is in the working directory |
| `API tokens without TLS are insecure` (panic on startup) | `token` is set in the config but `tls` is not | Either remove the token, or add TLS config (`tls.cert` + `tls.key`) to the relevant API section |
| `error: linker 'cc' not found` during `cargo build` | C linker not installed on Linux | `sudo apt install -y build-essential` |
| `error[E0463]: can't find crate for 'std'` | Rust toolchain not properly installed | Run `rustup default stable` and then retry |
| `Connection refused` on port 8080 | Server not started, or bound to a different address | Run `cargo run` (or Docker), then check the log output for the actual bound address |
| `docker: Error response from daemon: Bind for 0.0.0.0:8080 failed: port is already allocated` | Port 8080 is in use on the host | Change `external-api.port` in `acceptxmr.yaml` to an unused port, or stop the conflicting process |
| `WARN ... Could not load config from payment-config.json` in `configure_site.py` | `investment-platform/payment-config.json` not found relative to `--repo-root` | Run the script from the repository root, or pass `--repo-root /path/to/repo` |
| `Unsupported target arch` during Docker cross-compile | `TARGETARCH` is neither `amd64` nor `arm64` | Specify the platform explicitly: `docker build --platform linux/amd64 .` |
| Integration tests hang indefinitely | Tests attempt to connect to a live Monero node that is unreachable | The library ships an `httpmock`-based test harness; ensure `--all-features` is passed so the mock daemon is compiled in |
| `error: failed to parse private viewkey` | View key string is invalid (not 64 hex chars) | Re-export the view key from your Monero wallet and confirm it is exactly 64 hexadecimal characters |

---

## 9. Project Structure

```
acceptxmr/                         # Cargo workspace root
│
├── Cargo.toml                     # Workspace manifest; shared dependency versions
├── Cargo.lock                     # Reproducible dependency lock file
├── acceptxmr.yaml                 # Example server configuration file
├── .env                           # Example secrets file (do NOT commit real secrets)
├── Dockerfile                     # Multi-stage, multi-arch Docker image build
├── docker-compose.yml             # Local Docker Compose stack definition
├── docker.sh                      # Convenience shell script to run docker run
├── configure_site.py              # Zero-JS PHP site generator (Python, stdlib only)
├── CHANGELOG.md                   # Semantic-versioned change history
├── README.md                      # This file
├── LICENSE-MIT                    # MIT licence text
├── LICENSE-APACHE                 # Apache-2.0 licence text
├── clippy.toml                    # Clippy lint configuration (allowed duplicates)
├── .rustfmt.toml                  # Rust code formatting configuration
├── typos.toml                     # Typo-checking configuration
├── flake.nix / flake.lock         # Nix development shell (optional)
│
├── library/                       # `acceptxmr` crate — the core Rust library
│   ├── Cargo.toml                 # Library crate manifest and feature flags
│   ├── README.md                  # Library-specific documentation
│   ├── src/
│   │   └── lib.rs                 # Public API entry point; re-exports all types
│   ├── examples/
│   │   ├── nojs/                  # Example: server with no client-side JS
│   │   ├── websockets/            # Example: real-time updates via WebSocket
│   │   ├── persistence/           # Example: SQLite persistent storage
│   │   └── custom_storage/        # Example: custom InvoiceStore implementation
│   └── tests/                     # Library integration tests
│
├── server/                        # `acceptxmr-server` crate — the gateway binary
│   ├── Cargo.toml                 # Server crate manifest
│   ├── README.md                  # Server-specific documentation
│   ├── acceptxmr.yaml             # Server's own test configuration file
│   ├── src/
│   │   ├── main.rs                # Binary entry point; calls `entrypoint()`
│   │   ├── lib.rs                 # Library facade; exposes `entrypoint()`
│   │   ├── callbacks.rs           # HTTP callback dispatch and retry logic
│   │   ├── logging.rs             # Log initialisation helper
│   │   ├── config/                # Configuration parsing and validation
│   │   │   ├── mod.rs             # Top-level `Config` struct; YAML + env loading
│   │   │   ├── callback.rs        # `CallbackConfig` (queue-size, max-retries)
│   │   │   ├── daemon.rs          # `DaemonConfig` (URL, login, timeouts)
│   │   │   ├── database.rs        # `DatabaseConfig` (path, delete-expired)
│   │   │   ├── logging.rs         # `LoggingConfig` (verbosity level)
│   │   │   ├── server.rs          # `ServerConfig` + `TlsConfig` (port, addr, TLS)
│   │   │   └── wallet.rs          # `WalletConfig` (address, view-key, index)
│   │   └── server/
│   │       ├── mod.rs             # Builds and starts the Axum HTTP servers
│   │       ├── auth.rs            # Bearer-token authentication middleware
│   │       ├── state.rs           # Shared application state injected into handlers
│   │       ├── tls.rs             # TLS acceptor construction
│   │       └── api/
│   │           ├── mod.rs         # Error types and shared response helpers
│   │           ├── external.rs    # External API routes (GET /invoice, /invoice/ws, /pay)
│   │           ├── internal.rs    # Internal API routes (POST/DELETE /invoice, /invoice/ids)
│   │           ├── templating.rs  # Tera template loading and rendering
│   │           └── types/         # Shared request/response data types
│   ├── static/                    # Static files served by the payment UI
│   │   ├── pay.html               # Tera template: payment prompt page
│   │   ├── missing-invoice.html   # Tera template: expired invoice page
│   │   ├── error.html             # Tera template: generic error page
│   │   ├── acceptxmr.css          # Default payment UI stylesheet
│   │   ├── acceptxmr.js           # WebSocket update client (payment UI only)
│   │   ├── favicon.ico            # Browser favicon
│   │   └── vendor/
│   │       └── qrcode.js          # QR code renderer (vendored, no CDN)
│   └── tests/
│       ├── main.rs                # Integration test harness
│       ├── integration_tests/     # End-to-end server tests (mock daemon)
│       ├── common/                # Shared test helpers
│       └── testdata/
│           ├── cert/              # Self-signed TLS certificate for tests
│           └── config/            # Test configuration YAML files
│
├── testing-utils/                 # Shared test helpers crate (not published)
│   ├── Cargo.toml
│   ├── src/                       # Mock Monero daemon and blockchain helpers
│   └── rpc_resources/             # Captured RPC responses used by the mock daemon
│
└── investment-platform/           # Source for the zero-JS PHP site generator
    ├── payment-config.json        # Investment tiers, API URL, defaults
    ├── styles.css                 # Overlay styles (used by configure_site.py as reference)
    ├── scanner.js                 # (Source reference only — NOT included in generated output)
    ├── xmr-converter.js           # (Source reference only — NOT included in generated output)
    ├── payment-overlay.js         # (Source reference only — NOT included in generated output)
    ├── inject.js                  # (Source reference only — NOT included in generated output)
    └── README.md                  # Investment platform documentation
```

---

## 10. Scripts Reference

The project does not use a `package.json` or `Makefile`; all automation is
done through `cargo` sub-commands, Docker commands, and the Python generator
script.

### Cargo commands

| Command | Description |
|---------|-------------|
| `cargo build` | Debug build of the entire workspace |
| `cargo build --release` | Optimised release build (LTO enabled) |
| `cargo build --all-features` | Build with every optional feature enabled |
| `cargo run` | Build and run `acceptxmr-server` in debug mode |
| `cargo run --release` | Build and run in release mode |
| `cargo test --all-features` | Run all unit and integration tests |
| `cargo +nightly fmt --all -- --check` | Check code formatting without modifying files |
| `cargo +nightly clippy --all-targets --all-features` | Run all Clippy lints |
| `cargo +nightly doc --all-features --all` | Build and validate documentation |
| `cargo fetch` | Pre-download all dependencies (useful in offline environments) |

### Docker commands

| Command | Description |
|---------|-------------|
| `docker compose up --build` | Build image locally and start the server stack |
| `docker compose up -d` | Start the stack in detached (background) mode |
| `docker compose down` | Stop and remove containers |
| `docker build -t acceptxmr:local .` | Build the Docker image for the current platform |
| `docker pull busyboredom/acceptxmr:latest` | Pull the latest pre-built image |
| `sh docker.sh` | Run the pre-built image using the example `docker run` command |

### Python generator

| Command | Description |
|---------|-------------|
| `python3 configure_site.py` | Generate the PHP site into `./site-output/` using defaults |
| `python3 configure_site.py --output DIR` | Write generated files to `DIR` |
| `python3 configure_site.py --wallet ADDR` | Override the Monero wallet address |
| `python3 configure_site.py --repo-root PATH` | Specify the repository root (when running from outside the repo) |
| `python3 configure_site.py --version` | Print the generator version |
| `python3 configure_site.py --help` | Show all options |

### Nix development shell (optional)

| Command | Description |
|---------|-------------|
| `nix develop` | Enter the Nix dev shell (provides `gcc`, `rustup`, `rust-analyzer`, etc.) |

---

## 11. Contributing

### Fork and clone

```bash
# 1. Fork the repository on GitHub (click "Fork" on the repo page).

# 2. Clone your fork
git clone https://github.com/<your-username>/acceptxmr.git
cd acceptxmr

# 3. Add the upstream remote
git remote add upstream https://github.com/busyboredom/acceptxmr.git
```

### Branch naming convention

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<short-description>` | `feature/add-sqlite-migrations` |
| Bug fix | `fix/<short-description>` | `fix/expired-invoice-panic` |
| Documentation | `docs/<short-description>` | `docs/improve-config-section` |
| Refactor | `refactor/<short-description>` | `refactor/extract-tls-module` |

```bash
# Create and switch to a new branch
git checkout -b feature/my-new-feature
```

### Make your changes and run checks

```bash
# Run all tests
cargo test --all-features

# Check formatting (CI will fail if this fails)
cargo +nightly fmt --all -- --check

# Fix formatting automatically
cargo +nightly fmt --all

# Run Clippy (CI will fail if this fails)
cargo +nightly clippy --all-targets --all-features

# Ensure docs compile without warnings
cargo +nightly doc --all-features --all
```

### PR checklist

Before opening a pull request, confirm every item below:

- [ ] A relevant issue is linked in the PR description.
- [ ] The change has been manually tested.
- [ ] Automated test coverage is sufficient for the change.
- [ ] `cargo +nightly fmt --all -- --check` passes with zero output.
- [ ] `cargo +nightly clippy --all-targets --all-features` passes with zero warnings.
- [ ] `README.md` has been updated if the change affects user-facing behaviour.
- [ ] `CHANGELOG.md` has been updated under the `[Unreleased]` heading.

### Submitting the PR

```bash
# Push your branch to your fork
git push origin feature/my-new-feature
```

Then open a pull request from `<your-username>/acceptxmr:feature/my-new-feature`
to `busyboredom/acceptxmr:main` on GitHub.

---

## 12. License

This project is dual-licensed under the **MIT License** and the **Apache
License, Version 2.0**. You may choose either licence when using this software.

- [MIT License](LICENSE-MIT) — Copyright © 2021–2024 AcceptXMR contributors
- [Apache License 2.0](LICENSE-APACHE) — Copyright © 2021–2024 AcceptXMR contributors

See [`LICENSE-MIT`](LICENSE-MIT) and [`LICENSE-APACHE`](LICENSE-APACHE) in the
repository root for the full licence texts.
