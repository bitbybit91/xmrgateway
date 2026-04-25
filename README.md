[![Build Status](https://github.com/busyboredom/acceptxmr/workflows/CI/badge.svg)](https://img.shields.io/github/actions/workflow/status/busyboredom/acceptxmr/ci.yml?branch=main)
[![Crates.io](https://img.shields.io/crates/v/acceptxmr.svg)](https://crates.io/crates/acceptxmr)
[![Documentation](https://docs.rs/acceptxmr/badge.svg)](https://docs.rs/acceptxmr)
[![MSRV](https://img.shields.io/badge/MSRV-1.76.0-blue)](https://blog.rust-lang.org/2024/02/08/Rust-1.76.0.html)
[![Docker Image Size](https://badgen.net/docker/size/busyboredom/acceptxmr/latest/amd64?icon=docker&label=Docker%20Size)](https://hub.docker.com/r/busyboredom/acceptxmr/)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](#license)

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
of two deliverables:

- **`AcceptXMR` (library)** — A slim, composable Rust library for tracking
  Monero payments in any Rust application. It generates subaddresses from your
  private view key, polls a Monero daemon for incoming transactions, and notifies
  your code via async subscribers or callbacks.
- **`AcceptXMR-Server` (server)** — A batteries-included, standalone payment
  gateway built on top of the library. It exposes two HTTP/WebSocket APIs (one
  internal for your backend, one external for end users) and ships a ready-made
  payment UI with Tera HTML templating.

### Key Features

- **View-key-only operation** — no hot wallet, no private spend key ever leaves
  your control.
- **Subaddress-based invoicing** — every invoice receives its own unique
  subaddress.
- **Persistent invoice storage** — survives process restarts; backends include
  SQLite, Sled, and in-memory.
- **Configurable confirmations** — set required block confirmations per invoice.
- **Timelock-aware** — ignores timelocked transactions.
- **Burning-bug mitigation** — tracks used stealth addresses across all
  historical and in-flight transactions.
- **Multi-transaction payments** — a single invoice accepts funds spread across
  multiple transactions.
- **Real-time updates** — WebSocket push notifications to the payment UI.
- **Callback support** — HTTP callbacks fired on every invoice state change,
  with configurable retry logic.
- **TLS + Bearer-token auth** — the internal API is secured out of the box.
- **Cross-platform Docker image** — pre-built for `linux/amd64` and
  `linux/arm64`.
- **OpenAPI / Swagger UI** — interactive API docs served at runtime.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Rust (edition 2021, MSRV 1.76) |
| Async runtime | Tokio |
| HTTP server | Axum 0.7 |
| HTTP client | Hyper 1 + hyper-rustls |
| TLS | tokio-rustls / rustls |
| Serialisation | serde / serde_json / serde_yaml |
| Storage backends | SQLite (`sqlite` crate), Sled, in-memory |
| Templating | Tera |
| CLI arg parsing | Clap 4 |
| Containerisation | Docker (multi-stage, multi-arch) |
| CI/CD | GitHub Actions |

### Supported Platforms

| Platform | Method |
|----------|--------|
| Linux (x86-64, arm64) | Native binary, Docker |
| macOS (x86-64, Apple Silicon) | Native binary |
| Windows (x86-64) | Native binary (Rust toolchain required) |
| Any OCI-compatible host | Docker image `busyboredom/acceptxmr` |

---

## 2. Prerequisites

Every tool listed below must be present **before** following the Installation
section. Install them in order.

### 2.1 Git

| Detail | Value |
|--------|-------|
| Minimum version | 2.x |
| Download | https://git-scm.com/downloads |

<details>
<summary>macOS</summary>

```bash
brew install git
```
</details>

<details>
<summary>Ubuntu / Debian</summary>

```bash
sudo apt update && sudo apt install -y git
```
</details>

<details>
<summary>Windows</summary>

```powershell
winget install Git.Git
```
</details>

Verify:

```bash
git --version
# Expected: git version 2.x.x
```

---

### 2.2 Rust Toolchain

| Detail | Value |
|--------|-------|
| Minimum version | 1.76.0 (MSRV) |
| Recommended | latest stable |
| Download | https://rustup.rs |

<details>
<summary>macOS / Linux</summary>

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
```
</details>

<details>
<summary>Windows</summary>

Download and run `rustup-init.exe` from https://rustup.rs, then open a new
terminal.
</details>

Verify:

```bash
rustc --version
# Expected: rustc 1.76.0 (or newer)
cargo --version
# Expected: cargo 1.76.0 (or newer)
```

To install the nightly toolchain (required for `cargo fmt --all` with the
project's formatting rules):

```bash
rustup toolchain install nightly
rustup component add rustfmt clippy --toolchain nightly
```

---

### 2.3 Docker (optional — required only for the Docker-based setup)

| Detail | Value |
|--------|-------|
| Minimum version | 24.x (Docker Engine) or Docker Desktop 4.x |
| Download | https://docs.docker.com/get-docker/ |

<details>
<summary>macOS</summary>

```bash
brew install --cask docker
# Then open the Docker Desktop application to complete installation.
```
</details>

<details>
<summary>Ubuntu / Debian</summary>

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"
newgrp docker
```
</details>

<details>
<summary>Windows</summary>

Download Docker Desktop from https://docs.docker.com/desktop/install/windows-install/
and follow the installer wizard.
</details>

Verify:

```bash
docker --version
# Expected: Docker version 24.x.x (or newer)
docker compose version
# Expected: Docker Compose version v2.x.x
```

---

## 3. Environment Setup (No Physical Device Required)

`AcceptXMR-Server` communicates with a remote Monero daemon over HTTPS. No
local Monero node is required; a public node is used by default. All
development, testing, and CI steps run entirely in software.

### 3.1 Using a Public Monero Node (Default — Zero Setup)

The default configuration in `acceptxmr.yaml` already points at a public node:

```
https://xmr-node.cakewallet.com:18081/
```

No additional daemon setup is needed for development or testing.

### 3.2 Running a Local Monero Node via Docker (Optional)

If you need an isolated, offline-friendly test environment, you can run
[Monero's stagenet](https://monerodocs.org/infrastructure/stagenet/) inside a
Docker container.

1. Pull the official Monero image:

   ```bash
   docker pull sethsimmons/simple-monerod:latest
   ```

2. Start a stagenet daemon:

   ```bash
   docker run -d \
     --name monerod-stagenet \
     -p 38081:38081 \
     sethsimmons/simple-monerod:latest \
     --stagenet \
     --rpc-bind-ip=0.0.0.0 \
     --confirm-external-bind \
     --rpc-bind-port=38081 \
     --no-igd \
     --hide-my-port
   ```

3. Confirm the daemon is reachable:

   ```bash
   curl -s http://127.0.0.1:38081/json_rpc \
     -d '{"jsonrpc":"2.0","id":"0","method":"get_info"}' \
     -H 'Content-Type: application/json' | python3 -m json.tool
   ```

   Expected output contains `"status": "OK"`.

4. Update `acceptxmr.yaml` to point at the local daemon:

   ```yaml
   daemon:
     url: http://127.0.0.1:38081/
   ```

### 3.3 Troubleshooting Common Setup Failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `curl: (7) Failed to connect` | Daemon not yet started | Wait 30 s and retry; check `docker logs monerod-stagenet` |
| `docker: command not found` | Docker not installed | Follow §2.3 |
| `permission denied` running Docker | User not in `docker` group | `sudo usermod -aG docker "$USER" && newgrp docker` |
| Daemon says `"busy"` | Initial sync still in progress | Wait for sync to complete or use the public node |

---

## 4. Configuration

`AcceptXMR-Server` uses **two** configuration sources:

| Source | Purpose |
|--------|---------|
| `acceptxmr.yaml` | All non-secret settings |
| Environment variables / `.env` file | Secrets (view key, API tokens, daemon password) |

### 4.1 Environment Variables

| Variable | Required | Type | Default | Description |
|----------|----------|------|---------|-------------|
| `PRIVATE_VIEWKEY` | **Yes** | hex string (64 chars) | — | Monero wallet private view key. Never commit this. |
| `INTERNAL_API_TOKEN` | No | string | — | Bearer token to protect the internal API. Requires TLS to be configured. |
| `EXTERNAL_API_TOKEN` | No | string | — | Bearer token to protect the external API. Requires TLS to be configured. |
| `DAEMON_PASSWORD` | No | string | — | Password for Monero daemon RPC authentication (when `daemon.login` is set in YAML). |
| `CONFIG_FILE` | No | filesystem path | `./acceptxmr.yaml` | Override the config file path. Equivalent to the `--config-file` CLI flag. |

### 4.2 `.env.example`

```bash
# .env.example — copy this file to .env and fill in real values.
# Never commit .env to version control.

# ------------------------------------------------------------------
# REQUIRED
# ------------------------------------------------------------------

# Your Monero wallet's private view key (64-character hex string).
# Obtain this from your Monero wallet software under:
#   Feather Wallet:  Wallet → View Only → Private View Key
#   Monero GUI:      Settings → Show seed & keys → Private View Key
#   Monero CLI:      viewkey
PRIVATE_VIEWKEY=ad2093a5705b9f33e6f0f0c1bc1f5f639c756cdfc168c8f2ac6127ccbdab3a03

# ------------------------------------------------------------------
# OPTIONAL — API authentication (requires TLS; see acceptxmr.yaml)
# ------------------------------------------------------------------

# Bearer token for the internal API (invoice creation/deletion).
# Generate with: openssl rand -hex 32
INTERNAL_API_TOKEN=supersecrettoken

# Bearer token for the external API.
# EXTERNAL_API_TOKEN=anothersecrettoken

# ------------------------------------------------------------------
# OPTIONAL — Monero daemon authentication
# ------------------------------------------------------------------

# Password for the Monero daemon RPC login (when daemon.login is set
# in acceptxmr.yaml).
# DAEMON_PASSWORD=supersecretpassword
```

### 4.3 `acceptxmr.yaml` Reference

The file is auto-generated with defaults the first time the server starts if it
does not already exist. An annotated reference follows:

```yaml
# acceptxmr.yaml — full annotated example

# -----------------------------------------------------------------
# External API: safe to expose to end users.
# -----------------------------------------------------------------
external-api:
  port: 8080                     # TCP port to listen on.
  ipv4: 127.0.0.1                # IPv4 bind address. Use 0.0.0.0 to bind all interfaces.
  # ipv6: ::1                    # Optional IPv6 bind address.
  static_dir: server/static/    # Directory containing HTML/CSS/JS assets for the payment UI.
  # tls:                         # Uncomment to enable TLS on this API.
  #   cert: /path/to/cert.pem
  #   key:  /path/to/key.pem

# -----------------------------------------------------------------
# Internal API: must NOT be exposed to the public internet.
# -----------------------------------------------------------------
internal-api:
  port: 8081
  ipv4: 127.0.0.1
  # ipv6: ::1
  tls:                           # TLS is required when an API token is set.
    cert: ./cert/certificate.pem
    key:  ./cert/privatekey.pem
  static_dir: server/static/

# -----------------------------------------------------------------
# Callback configuration
# -----------------------------------------------------------------
callback:
  queue-size: 1000               # Maximum number of pending callback requests.
  max-retries: 50                # Maximum retry attempts per callback. Omit for unlimited.

# -----------------------------------------------------------------
# Monero wallet (secrets set via environment variables)
# -----------------------------------------------------------------
wallet:
  primary-address: 4613YiHLM6JMH4zejMB2zJY5TwQCxL8p65ufw8kBP5yxX9itmuGLqp1dS4tkVoTxjyH3aYhYNrtGHbQzJQP5bFus3KHVdmf
  account-index: 0               # Wallet account index. Defaults to 0.
  restore-height: null           # Block height from which to start scanning. null = chain tip.

# -----------------------------------------------------------------
# Monero daemon connection
# -----------------------------------------------------------------
daemon:
  url: https://xmr-node.cakewallet.com:18081/
  rpc-timeout: 30                # Seconds to wait for an RPC response.
  connection-timeout: 20         # Seconds to wait when establishing a connection.
  # login:                       # Uncomment if your node requires authentication.
  #   username: myuser           # Password must be supplied via DAEMON_PASSWORD env var.

# -----------------------------------------------------------------
# Invoice database
# -----------------------------------------------------------------
database:
  path: AcceptXMR_DB/            # Directory where the SQLite database is stored.
  delete-expired: true           # Automatically remove expired, unconfirmed invoices.

# -----------------------------------------------------------------
# Logging
# -----------------------------------------------------------------
logging:
  verbosity: INFO                # One of: ERROR, WARN, INFO, DEBUG, TRACE, OFF
```

### 4.4 Generating Secrets

**Private view key** — export from your Monero wallet:

- *Feather Wallet*: Wallet → View Only → Private View Key
- *Monero GUI*: Settings → Show seed & keys → Private View Key
- *Monero CLI*: type `viewkey` at the interactive prompt

**Random API token**:

```bash
openssl rand -hex 32
```

**Self-signed TLS certificate** (development only):

```bash
mkdir -p cert
openssl req -x509 -newkey rsa:4096 -keyout cert/privatekey.pem \
  -out cert/certificate.pem -sha256 -days 365 -nodes \
  -subj "/CN=localhost"
```

### 4.5 Switching Between Environments

| Environment | Recommended approach |
|-------------|---------------------|
| Development | Use the default public node; set `logging.verbosity: DEBUG` |
| Staging | Point `daemon.url` at a stagenet node; use a separate wallet |
| Production | Point `daemon.url` at a trusted mainnet node; enable TLS; set `INTERNAL_API_TOKEN` |

---

## 5. Installation

### 5.1 From Source

Follow every numbered step in sequence on a clean machine.

1. **Clone the repository**:

   ```bash
   git clone https://github.com/busyboredom/acceptxmr.git
   cd acceptxmr
   ```

2. **Verify the Rust toolchain meets the MSRV**:

   ```bash
   rustc --version
   # Must be 1.76.0 or newer. If not, upgrade:
   rustup update stable
   ```

3. **Build all workspace crates** to confirm dependencies resolve correctly:

   ```bash
   cargo build
   ```

   Expected output ends with:

   ```
   Finished `dev` profile [unoptimized + debuginfo] target(s) in ...
   ```

   > **Common error**: `error: package 'sqlite' requires a newer Rust compiler`
   > **Fix**: `rustup update stable`

4. **Copy the example environment file**:

   ```bash
   cp .env .env.local
   # Edit .env.local and replace example values with your own:
   #   PRIVATE_VIEWKEY=<your 64-character hex view key>
   #   INTERNAL_API_TOKEN=<random token from: openssl rand -hex 32>
   ```

5. **Copy and review the example configuration file**:

   ```bash
   cp acceptxmr.yaml my-acceptxmr.yaml
   # Edit my-acceptxmr.yaml:
   #   - Set wallet.primary-address to your Monero primary address.
   #   - Adjust daemon.url if using a different node.
   #   - Set TLS cert paths if enabling token authentication.
   ```

6. **Generate a self-signed TLS certificate** (required when using
   `INTERNAL_API_TOKEN`):

   ```bash
   mkdir -p cert
   openssl req -x509 -newkey rsa:4096 -keyout cert/privatekey.pem \
     -out cert/certificate.pem -sha256 -days 365 -nodes \
     -subj "/CN=localhost"
   ```

7. **Verify the installation** by running the test suite:

   ```bash
   cargo test --all-features
   ```

   Expected: all tests pass (output ends with `test result: ok`).

---

### 5.2 Using Docker

1. **Clone the repository**:

   ```bash
   git clone https://github.com/busyboredom/acceptxmr.git
   cd acceptxmr
   ```

2. **Create the environment file**:

   ```bash
   cp .env .env.local
   # Edit .env.local with your secrets.
   ```

3. **Create / review `acceptxmr.yaml`** (the file already exists in the repo as
   a working example):

   ```bash
   # Open and edit acceptxmr.yaml — set wallet.primary-address at minimum.
   ```

4. **Create the database directory**:

   ```bash
   mkdir -p AcceptXMR_DB
   ```

5. **Build and start the server**:

   ```bash
   docker compose up --build
   ```

   Expected output contains:

   ```
   server  | INFO acceptxmr_server: Starting AcceptXMR-Server
   server  | INFO acceptxmr_server: External API listening on 127.0.0.1:8080
   server  | INFO acceptxmr_server: Internal API listening on 127.0.0.1:8081
   ```

6. **Or pull the pre-built image** (no build step required):

   ```bash
   docker pull busyboredom/acceptxmr:latest
   docker run -d \
     --name acceptxmr \
     --network host \
     --mount type=bind,source="${PWD}/AcceptXMR_DB",target=/AcceptXMR_DB \
     --mount type=bind,source="${PWD}/cert",target=/cert \
     --mount type=bind,source="${PWD}/acceptxmr.yaml",target=/acceptxmr.yaml \
     --env-file .env.local \
     busyboredom/acceptxmr:latest
   ```

---

## 6. Build

### 6.1 Development Build

Start a debug build in watch mode using `cargo-watch` (install once):

```bash
cargo install cargo-watch
cargo watch -x 'run --bin acceptxmr-server'
```

The server starts at:
- External API: `http://127.0.0.1:8080`
- Internal API: `https://127.0.0.1:8081` (TLS)
- Swagger UI (external): `http://127.0.0.1:8080/swagger-ui/`
- Swagger UI (internal): `https://127.0.0.1:8081/swagger-ui/`

Source file changes trigger an automatic rebuild and restart.

To run the server with a custom config file path:

```bash
cargo run --bin acceptxmr-server -- --config-file /path/to/my-acceptxmr.yaml
```

Alternatively, via environment variable:

```bash
CONFIG_FILE=/path/to/my-acceptxmr.yaml cargo run --bin acceptxmr-server
```

---

### 6.2 Production Build

1. **Compile with full optimisations** (LTO is enabled in `[profile.release]`):

   ```bash
   cargo build --release
   ```

2. **Locate the binary**:

   ```bash
   ls -lh target/release/acceptxmr-server
   ```

3. **Run the production binary**:

   ```bash
   ./target/release/acceptxmr-server --config-file /etc/acceptxmr/acceptxmr.yaml
   ```

4. **Verify the binary starts correctly**:

   ```bash
   curl -s http://127.0.0.1:8080/swagger-ui/ | grep -i "swagger"
   # Expected: HTML containing "Swagger UI"
   ```

---

### 6.3 Docker Production Build

Build a multi-arch image locally:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t acceptxmr:latest \
  --load \
  .
```

To build for a single platform (faster, useful for local testing):

```bash
docker build -t acceptxmr:latest .
```

Verify the image:

```bash
docker run --rm acceptxmr:latest ./acceptxmr-server --help
```

---

### 6.4 CI/CD Build (Headless / Automated)

The repository ships two GitHub Actions workflows.

#### Rust CI workflow (`.github/workflows/rust.yml`)

Runs on every push and pull request. Performs:
- `cargo fmt --all -- --check` (nightly)
- `cargo clippy --all-targets --all-features` (nightly)
- `cargo doc --all-features --all` (nightly)
- `cargo build --verbose` (stable 1.76 and nightly)
- `cargo test --verbose --all-features` (stable 1.76 and nightly)

```yaml
# .github/workflows/rust.yml — included verbatim for reference
name: rust-ci

on:
  push:
    branches: ['main']
    tags: ['*']
  pull_request:
    branches: ['*']

env:
  CARGO_TERM_COLOR: always
  RUSTFLAGS: '-D warnings'
  RUSTDOCFLAGS: '-D warnings'

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
          profile: minimal
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
      - name: Install Rust ${{ matrix.rust }}
        uses: actions-rs/toolchain@v1.0.6
        with:
          toolchain: ${{ matrix.rust }}
          override: true
          profile: minimal
      - uses: Swatinem/rust-cache@v2.2.1
      - name: Build
        run: cargo build --verbose
      - name: Build with all features
        run: cargo build --verbose --all-features

  test:
    strategy:
      matrix:
        rust: [1.76.0, nightly]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3.3.0
      - name: Install Rust ${{ matrix.rust }}
        uses: actions-rs/toolchain@v1.0.6
        with:
          toolchain: ${{ matrix.rust }}
          override: true
          profile: minimal
      - uses: Swatinem/rust-cache@v2.2.1
      - run: cargo test --verbose --all-features
```

#### Injecting secrets in CI

Add the following repository secrets in GitHub → Settings → Secrets and
variables → Actions:

| Secret name | Description |
|-------------|-------------|
| `DOCKERHUB_USERNAME` | Docker Hub username (Docker workflow only) |
| `DOCKERHUB_TOKEN` | Docker Hub access token (Docker workflow only) |

To inject `PRIVATE_VIEWKEY` during a test run that needs it:

```yaml
env:
  PRIVATE_VIEWKEY: ${{ secrets.PRIVATE_VIEWKEY }}
```

#### Running the full CI pipeline locally (no GitHub required)

Install [`act`](https://github.com/nektos/act):

```bash
# macOS
brew install act

# Linux
curl -s https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

Run the Rust CI job locally:

```bash
act push --job build
```

---

## 7. Running Tests

### 7.1 Run the Full Test Suite

```bash
cargo test --all-features
```

### 7.2 Run Tests for a Specific Crate

```bash
# Library only
cargo test -p acceptxmr --all-features

# Server only
cargo test -p acceptxmr-server --all-features
```

### 7.3 Run a Single Test by Name

```bash
cargo test --all-features <test_name>
# Example:
cargo test --all-features default
```

### 7.4 Run Tests with Verbose Output

```bash
cargo test --all-features -- --nocapture
```

### 7.5 Run Tests with a Specific Log Level

```bash
RUST_LOG=debug cargo test --all-features -- --nocapture
```

### 7.6 Generate and View a Coverage Report

Install `cargo-llvm-cov`:

```bash
cargo install cargo-llvm-cov
rustup component add llvm-tools-preview
```

Generate an HTML coverage report:

```bash
cargo llvm-cov --all-features --html
```

Open the report:

```bash
# macOS
open target/llvm-cov/html/index.html

# Linux
xdg-open target/llvm-cov/html/index.html
```

### 7.7 Expected Output of a Passing Test Run

```
running X tests
test config::test::default ... ok
test config::test::from_yaml ... ok
...
test result: ok. X passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

---

## 8. Common Issues & Troubleshooting

| Error Message / Symptom | Cause | Fix |
|------------------------|-------|-----|
| `error[E0554]: #![feature] may not be used on the stable release channel` | Nightly-only feature used with stable compiler | `rustup toolchain install nightly && cargo +nightly build` |
| `error: package '...' requires a newer Rust compiler` | Installed Rust is below MSRV 1.76 | `rustup update stable` |
| `please configure your monero primary address` (panic on startup) | `wallet.primary-address` is missing from `acceptxmr.yaml` | Add a valid `4...` Monero address to `acceptxmr.yaml` |
| `please configure your monero private viewkey` (panic on startup) | `PRIVATE_VIEWKEY` env var not set | `export PRIVATE_VIEWKEY=<your 64-char hex key>` or add it to `.env` |
| `API tokens without TLS are insecure` (panic on startup) | `INTERNAL_API_TOKEN` is set but `tls` is absent from the config | Add TLS cert/key paths under `internal-api.tls` in `acceptxmr.yaml` |
| `daemon login exists in config, but a password was not set` (panic) | `daemon.login.username` is in YAML but `DAEMON_PASSWORD` is unset | `export DAEMON_PASSWORD=<password>` or remove the `login` block |
| `Failed to connect to <daemon URL>` at runtime | Monero daemon is unreachable | Check daemon URL, network, and firewall; try the default public node |
| `No such file or directory` for cert PEM files | TLS cert files do not exist at the configured paths | Run the `openssl req` command from §4.4 and update paths in YAML |
| `cargo: command not found` | Rust toolchain not installed | Follow §2.2 |
| `docker compose up` exits with `port is already allocated` | Port 8080 or 8081 already in use | Change `external-api.port` / `internal-api.port` in `acceptxmr.yaml` |

---

## 9. Project Structure

```
acceptxmr/                        ← Workspace root
├── Cargo.toml                    ← Workspace manifest; shared dependency versions
├── Cargo.lock                    ← Locked dependency tree
├── acceptxmr.yaml                ← Example / default server configuration file
├── .env                          ← Example environment variable file (secrets)
├── Dockerfile                    ← Multi-stage, multi-arch Docker build
├── docker-compose.yml            ← Compose file for local Docker development
├── docker.sh                     ← Convenience shell script for `docker run`
├── clippy.toml                   ← Clippy lint configuration
├── .rustfmt.toml                 ← rustfmt code formatting rules
├── typos.toml                    ← typos spell-checker configuration
├── CHANGELOG.md                  ← Human-readable version history
│
├── .cargo/
│   └── config.toml               ← Cargo build flags (tokio_unstable, sparse registry)
│
├── .github/
│   ├── workflows/
│   │   ├── rust.yml              ← CI: fmt, clippy, build, test (stable + nightly)
│   │   └── docker.yml            ← CI: build & push Docker image to Docker Hub
│   └── pull_request_template.md  ← PR checklist template
│
├── library/                      ← `acceptxmr` crate (the Rust library)
│   ├── Cargo.toml
│   ├── README.md
│   ├── src/
│   │   ├── lib.rs                ← Public API surface
│   │   ├── payment_gateway.rs    ← PaymentGateway struct and builder
│   │   ├── invoice.rs            ← Invoice type and state machine
│   │   ├── scanner.rs            ← Block/txpool scanning loop
│   │   ├── pubsub.rs             ← Subscriber / notification channel
│   │   ├── caching/              ← In-memory output-key and height caches
│   │   ├── monerod_client/       ← Hyper-based Monero daemon RPC client
│   │   └── storage/              ← InvoiceStorage trait + Sled/SQLite/InMemory backends
│   ├── examples/
│   │   ├── websockets/           ← Actix-web WebSocket payment demo
│   │   ├── nojs/                 ← Server-side-rendered (no JS) payment demo
│   │   ├── persistence/          ← SQLite persistence example
│   │   └── custom_storage/       ← Custom storage backend example
│   └── tests/                    ← Integration tests for the library
│
├── server/                       ← `acceptxmr-server` crate (the binary)
│   ├── Cargo.toml
│   ├── README.md
│   ├── acceptxmr.yaml            ← Server-specific example config
│   ├── src/
│   │   ├── main.rs               ← Binary entry point
│   │   ├── lib.rs                ← `entrypoint()` function
│   │   ├── server/               ← Axum router, handlers, WebSocket logic
│   │   ├── callbacks.rs          ← Async HTTP callback dispatcher
│   │   ├── logging.rs            ← env_logger initialisation
│   │   └── config/               ← Typed configuration structs + YAML/env loading
│   │       ├── mod.rs            ← Top-level Config struct
│   │       ├── server.rs         ← ServerConfig / TlsConfig
│   │       ├── wallet.rs         ← WalletConfig (view key, address)
│   │       ├── daemon.rs         ← DaemonConfig (URL, login, timeouts)
│   │       ├── database.rs       ← DatabaseConfig (path, auto-delete)
│   │       ├── callback.rs       ← CallbackConfig (queue size, retries)
│   │       └── logging.rs        ← LoggingConfig (verbosity)
│   ├── static/                   ← Default payment UI assets
│   │   ├── pay.html              ← Tera template: payment prompt page
│   │   ├── missing-invoice.html  ← Tera template: expired invoice page
│   │   ├── error.html            ← Tera template: internal error page
│   │   ├── acceptxmr.css         ← Default UI stylesheet
│   │   ├── acceptxmr.js          ← Default UI JavaScript (WebSocket client)
│   │   ├── favicon.ico
│   │   └── vendor/               ← Vendored front-end libraries
│   └── tests/                    ← Integration tests for the server
│       ├── main.rs
│       ├── common/               ← Test helpers (server fixture, HTTP client)
│       ├── integration_tests/    ← Per-endpoint test modules
│       └── testdata/
│           ├── cert/             ← Self-signed certs for testing
│           └── config/           ← YAML fixture configs for config tests
│
├── testing-utils/                ← Shared test helpers (mock Monero daemon)
│   ├── Cargo.toml
│   ├── src/
│   └── rpc_resources/            ← Recorded Monero RPC JSON fixtures
│
└── investment-platform/          ← Drop-in JS XMR payment button scanner
    ├── inject.js
    ├── scanner.js
    ├── xmr-converter.js
    ├── payment-overlay.js
    ├── payment-config.json
    ├── styles.css
    └── README.md
```

---

## 10. Scripts Reference

This project uses Cargo commands as its primary build system. There is no
`Makefile` or `package.json`. All commands are invoked via `cargo`.

| Command | Description |
|---------|-------------|
| `cargo build` | Debug build of all workspace members |
| `cargo build --release` | Optimised production build (LTO enabled) |
| `cargo build --all-features` | Debug build with all optional Cargo features enabled |
| `cargo run --bin acceptxmr-server` | Build and run the server binary (debug) |
| `cargo run --release --bin acceptxmr-server` | Build and run the server binary (release) |
| `cargo test` | Run unit tests for all workspace members |
| `cargo test --all-features` | Run all tests with every optional feature enabled |
| `cargo test -p acceptxmr` | Run tests for the library crate only |
| `cargo test -p acceptxmr-server` | Run tests for the server crate only |
| `cargo fmt --all` | Format all Rust source files (requires nightly) |
| `cargo fmt --all -- --check` | Check formatting without modifying files |
| `cargo clippy --all-targets --all-features` | Run the Clippy linter on all targets |
| `cargo doc --all-features --all --open` | Build and open API documentation in browser |
| `cargo clean` | Remove all build artefacts |
| `docker compose up --build` | Build locally and start the server in Docker |
| `docker compose up -d` | Start the server in Docker (detached) |
| `docker compose down` | Stop and remove Docker containers |
| `sh docker.sh` | Convenience script: `docker run` with pre-filled paths |

---

## 11. Contributing

### 11.1 Fork and Clone

1. Fork the repository on GitHub.
2. Clone your fork:

   ```bash
   git clone https://github.com/<your-username>/acceptxmr.git
   cd acceptxmr
   ```

3. Add the upstream remote:

   ```bash
   git remote add upstream https://github.com/busyboredom/acceptxmr.git
   ```

### 11.2 Branch Naming Convention

Use descriptive, lowercase, hyphen-separated names:

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<short-description>` | `feat/add-sqlite-backend` |
| Bug fix | `fix/<short-description>` | `fix/burning-bug-mitigation` |
| Documentation | `docs/<short-description>` | `docs/update-readme` |
| Refactor | `refactor/<short-description>` | `refactor/scanner-loop` |
| CI/CD | `ci/<short-description>` | `ci/add-coverage-report` |

```bash
git checkout -b feat/my-new-feature
```

### 11.3 Linting and Formatting Before a PR

Run all of the following commands and ensure they pass without errors before
opening a pull request:

1. **Format code** (nightly required):

   ```bash
   cargo +nightly fmt --all
   ```

2. **Run Clippy**:

   ```bash
   cargo +nightly clippy --all-targets --all-features
   ```

   No warnings are permitted (`RUSTFLAGS='-D warnings'` is enforced in CI).

3. **Run all tests**:

   ```bash
   cargo test --all-features
   ```

4. **Build documentation** (no warnings allowed):

   ```bash
   RUSTDOCFLAGS='-D warnings' cargo doc --all-features --all
   ```

5. **Check for typos** (requires [`typos-cli`](https://github.com/crate-ci/typos)):

   ```bash
   cargo install typos-cli
   typos
   ```

### 11.4 PR Checklist

When opening a pull request, the repository template will prompt you to confirm:

- [ ] Link relevant issue(s).
- [ ] Manually test the change.
- [ ] Ensure sufficient automated test coverage.
- [ ] Update `README.md` if necessary.
- [ ] Update `CHANGELOG.md` if necessary.

---

## 12. License

`AcceptXMR` and `AcceptXMR-Server` are dual-licensed under either of:

- [MIT License](./LICENSE-MIT)
- [Apache License, Version 2.0](./LICENSE-APACHE)

at your option.

Copyright © 2021–2024 the AcceptXMR contributors.

---

### Security Notes

`AcceptXMR` is non-custodial, and does not require a hot wallet. However, it
does require your private view key and primary address for scanning outputs. If
keeping these private is important to you, please take appropriate precautions
to secure the platform you run your application on.

Care is taken to protect users from malicious transactions containing timelocks
or duplicate output keys (i.e. the [burning
bug](https://www.getmonero.org/2018/09/25/a-post-mortum-of-the-burning-bug.html)).
For the best protection against the burning bug, use a dedicated wallet or
account index for `AcceptXMR` that is not used for any other purpose and set
`wallet.restore-height` to the wallet's restore height.

Also note that anonymity networks like TOR are not currently supported for RPC
calls. Your network traffic will reveal that you are interacting with the Monero
network.

### Reliability Notes

`AcceptXMR` can survive unexpected power loss thanks to persistent storage
(SQLite or Sled). RPC calls in the scanning thread are logged on failure and
retried on the next scan cycle. Use `AcceptXMR` at your own risk.

### Performance Notes

It is recommended that you host your own Monero daemon on the same local
network. Network and daemon latency are the primary cause of high invoice-update
latency. To reduce average latency, lower the gateway's `scan_interval` (library
API) below the default of 1 second. Note that reducing the scan interval below
the round-trip time to your node will have no effect.

### Donations

AcceptXMR is a hobby project. Donations from generous users and community
members help keep it economically viable to work on.

XMR:
`82assiV5dy7guoxxV7vSReZTyY5rGMrWg6BsfvFqiEKRcTiDs7LGMpg5dF5gXVGUWPEXQxyt8SNYx8L8HiGAzvtBK3eJ3EY`

---

*For the library-specific documentation see [`library/README.md`](./library/README.md).
For the server-specific documentation see [`server/README.md`](./server/README.md).*
