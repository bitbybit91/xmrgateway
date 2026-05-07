CREATE DATABASE IF NOT EXISTS `cryptoinvest` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `cryptoinvest`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `full_name` VARCHAR(255) NOT NULL,
  `kyc_status` ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  `login_attempts` TINYINT UNSIGNED NOT NULL DEFAULT 0,
  `locked_until` DATETIME NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `last_login` DATETIME NULL,
  INDEX `idx_email` (`email`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `funds` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `name` VARCHAR(255) NOT NULL,
  `slug` VARCHAR(100) NOT NULL UNIQUE,
  `description` TEXT NOT NULL,
  `min_investment_xmr` DECIMAL(20,12) NOT NULL DEFAULT 0.1,
  `apy_target` DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  `tier` TINYINT UNSIGNED NOT NULL DEFAULT 1,
  `active` TINYINT(1) NOT NULL DEFAULT 1,
  INDEX `idx_slug` (`slug`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `investments` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT UNSIGNED NOT NULL,
  `fund_id` INT UNSIGNED NOT NULL,
  `amount_xmr` DECIMAL(20,12) NOT NULL,
  `acceptxmr_invoice_id` VARCHAR(255) NOT NULL,
  `subaddress` VARCHAR(255) NULL,
  `status` ENUM('pending','confirmed','expired','cancelled') NOT NULL DEFAULT 'pending',
  `confirmations` INT UNSIGNED NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `confirmed_at` DATETIME NULL,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
  FOREIGN KEY (`fund_id`) REFERENCES `funds`(`id`),
  INDEX `idx_invoice` (`acceptxmr_invoice_id`),
  INDEX `idx_status` (`status`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `transactions` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `investment_id` INT UNSIGNED NOT NULL,
  `txid` VARCHAR(255) NOT NULL,
  `amount_xmr` DECIMAL(20,12) NOT NULL,
  `block_height` INT UNSIGNED NULL,
  `seen_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`investment_id`) REFERENCES `investments`(`id`),
  UNIQUE KEY `uk_txid` (`txid`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `sessions` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `user_id` INT UNSIGNED NOT NULL,
  `token` CHAR(128) NOT NULL,
  `ip` VARCHAR(45) NOT NULL,
  `user_agent` VARCHAR(512) NOT NULL,
  `expires_at` DATETIME NOT NULL,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`),
  UNIQUE KEY `uk_token` (`token`),
  INDEX `idx_expires` (`expires_at`)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `newsletter_subscribers` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `subscribed_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS `admin_users` (
  `id` INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(100) NOT NULL UNIQUE,
  `password_hash` VARCHAR(255) NOT NULL,
  `role` ENUM('admin','superadmin') NOT NULL DEFAULT 'admin',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Seed funds
INSERT IGNORE INTO `funds` (`name`, `slug`, `description`, `min_investment_xmr`, `apy_target`, `tier`, `active`) VALUES
('Venture Equity Fund', 'venture-equity', 'Our flagship fund targeting early-stage blockchain equity positions in the most promising Web3 infrastructure companies. We partner with founders building the next generation of decentralized protocols and applications.', 5.000000000000, 22.50, 1, 1),
('Early-Stage Token Fund', 'early-stage-token', 'Dedicated to early-stage token investments across DeFi, Layer 1, and Layer 2 protocols. We identify tokens with strong fundamentals before mainstream adoption, maximizing upside for investors.', 1.000000000000, 35.00, 2, 1),
('Liquid Token Fund', 'liquid-token', 'A liquid cryptocurrency portfolio optimized for risk-adjusted returns. Focused on established tokens with strong market liquidity, allowing for flexible entry and exit strategies.', 0.100000000000, 15.00, 3, 1);
