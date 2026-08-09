-- =============================================================
-- XMR Gateway Investment Platform — MySQL Schema
-- Run once on a fresh database: mysql -u root -p xmrgateway < schema.sql
-- =============================================================

CREATE DATABASE IF NOT EXISTS xmrgateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE xmrgateway;

-- ─── Users & Authentication ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    email         VARCHAR(255)    NOT NULL UNIQUE,
    password_hash VARCHAR(255)    NOT NULL,
    full_name     VARCHAR(120)    NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- ─── Accounts (one per user, holds USD-equivalent balance) ───────────────────
CREATE TABLE IF NOT EXISTS accounts (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL UNIQUE,
    balance_usd     DECIMAL(18, 4)  NOT NULL DEFAULT 0.0000,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    FOREIGN KEY fk_account_user (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ─── Investment Funds ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS funds (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    slug            VARCHAR(80)     NOT NULL UNIQUE,       -- URL-safe identifier
    name            VARCHAR(120)    NOT NULL,
    description     TEXT            NOT NULL,
    strategy        TEXT            NOT NULL,
    target_return   VARCHAR(40)     NOT NULL,              -- e.g. "15–25 % p.a."
    risk_level      ENUM('Low','Medium','High','Very High') NOT NULL DEFAULT 'Medium',
    min_investment  DECIMAL(12, 2)  NOT NULL DEFAULT 250.00,
    max_investment  DECIMAL(12, 2)  NOT NULL DEFAULT 1000000.00,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,
    PRIMARY KEY (id)
) ENGINE=InnoDB;

-- Seed funds
INSERT INTO funds (slug, name, description, strategy, target_return, risk_level) VALUES
('bitcoin-fund',
 'Bitcoin Fund',
 'Long-only exposure to Bitcoin, the premier store-of-value asset. Fully collateralised and custodied with institutional-grade security.',
 'Buy-and-hold BTC with periodic rebalancing. No leverage.',
 '20–40 % p.a.',
 'High'),
('monero-fund',
 'Monero Privacy Fund',
 'Pure exposure to Monero (XMR), the leading privacy-preserving cryptocurrency. Ideal for investors who value financial sovereignty.',
 'Long XMR with systematic accumulation on dips.',
 '25–60 % p.a.',
 'Very High'),
('crypto-blend',
 'Crypto Blend Fund',
 'A diversified basket of top-10 cryptocurrencies by market cap, rebalanced monthly. Reduces single-asset risk while capturing broad market growth.',
 'Market-cap-weighted basket rebalanced monthly. BTC ≥ 40 %.',
 '15–35 % p.a.',
 'Medium'),
('defi-yield',
 'DeFi Yield Fund',
 'Actively managed DeFi yield strategies across leading protocols. Targets above-market returns through liquidity provision and governance participation.',
 'Multi-protocol yield farming with automated compounding.',
 '30–80 % p.a.',
 'Very High');

-- ─── Deposits ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deposits (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL,
    coin            ENUM('XMR','BTC') NOT NULL,
    amount_coin     DECIMAL(24, 12) NOT NULL,              -- amount in the chosen coin
    usd_rate        DECIMAL(18, 4)  NOT NULL,              -- USD/coin rate at deposit time
    amount_usd      DECIMAL(18, 4)  NOT NULL,              -- = amount_coin * usd_rate
    address         VARCHAR(120)    NOT NULL,              -- receiving address shown to user
    tx_hash         VARCHAR(120)    NULL,                  -- filled once payment confirmed
    status          ENUM('pending','confirmed','failed') NOT NULL DEFAULT 'pending',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at    DATETIME        NULL,
    PRIMARY KEY (id),
    FOREIGN KEY fk_deposit_user (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_deposit_status (status),
    INDEX idx_deposit_user   (user_id)
) ENGINE=InnoDB;

-- ─── Withdrawals ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS withdrawals (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL,
    coin            ENUM('XMR','BTC') NOT NULL,
    amount_usd      DECIMAL(18, 4)  NOT NULL,              -- USD value requested
    usd_rate        DECIMAL(18, 4)  NOT NULL,              -- rate at request time
    amount_coin     DECIMAL(24, 12) NOT NULL,              -- = amount_usd / usd_rate
    destination     VARCHAR(120)    NOT NULL,              -- user-supplied wallet address
    status          ENUM('pending','approved','rejected','sent') NOT NULL DEFAULT 'pending',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed_at    DATETIME        NULL,
    notes           TEXT            NULL,
    PRIMARY KEY (id),
    FOREIGN KEY fk_withdrawal_user (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_withdrawal_status (status),
    INDEX idx_withdrawal_user   (user_id)
) ENGINE=InnoDB;

-- ─── Investments ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investments (
    id              INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    user_id         INT UNSIGNED    NOT NULL,
    fund_id         INT UNSIGNED    NOT NULL,
    amount_usd      DECIMAL(18, 4)  NOT NULL,              -- USD invested
    status          ENUM('active','redeemed') NOT NULL DEFAULT 'active',
    invested_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    redeemed_at     DATETIME        NULL,
    PRIMARY KEY (id),
    FOREIGN KEY fk_inv_user (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY fk_inv_fund (fund_id) REFERENCES funds(id),
    INDEX idx_inv_user (user_id),
    INDEX idx_inv_fund (fund_id)
) ENGINE=InnoDB;
