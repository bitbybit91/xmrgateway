-- =============================================================================
-- Crypto Investment Platform — Database Schema
-- Engine: MariaDB / MySQL 8+
-- Charset: utf8mb4
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `users` (
  `id`                        INT UNSIGNED     NOT NULL AUTO_INCREMENT,
  `name`                      VARCHAR(120)     NOT NULL,
  `email`                     VARCHAR(191)     NOT NULL,
  `password_hash`             VARCHAR(255)     NOT NULL,
  `phone`                     VARCHAR(30)               DEFAULT NULL,
  `role`                      ENUM('user','admin')      NOT NULL DEFAULT 'user',
  `status`                    ENUM('pending','active','suspended','banned') NOT NULL DEFAULT 'pending',
  `email_verified_at`         DATETIME                  DEFAULT NULL,
  `email_verification_token`  VARCHAR(128)              DEFAULT NULL,
  `password_reset_token`      VARCHAR(128)              DEFAULT NULL,
  `password_reset_expires`    DATETIME                  DEFAULT NULL,
  `two_factor_secret`         VARCHAR(64)               DEFAULT NULL,
  `referral_code`             VARCHAR(16)               DEFAULT NULL,
  `referred_by`               INT UNSIGNED              DEFAULT NULL,
  `created_at`                DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`                DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_users_email`         (`email`),
  UNIQUE KEY `uq_users_referral_code` (`referral_code`),
  KEY `idx_users_status`  (`status`),
  KEY `idx_users_role`    (`role`),
  CONSTRAINT `fk_users_referred_by` FOREIGN KEY (`referred_by`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- plans
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `plans` (
  `id`               INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `name`             VARCHAR(100)    NOT NULL,
  `slug`             VARCHAR(100)    NOT NULL,
  `description`      TEXT                     DEFAULT NULL,
  `min_amount_usd`   DECIMAL(15,2)   NOT NULL DEFAULT '100.00',
  `max_amount_usd`   DECIMAL(15,2)   NOT NULL DEFAULT '1000000.00',
  `daily_roi_percent` DECIMAL(8,4)   NOT NULL DEFAULT '0.0800',
  `duration_days`    SMALLINT UNSIGNED NOT NULL DEFAULT 30,
  `type`             ENUM('venture','early_token','liquid_token') NOT NULL DEFAULT 'liquid_token',
  `is_active`        TINYINT(1)      NOT NULL DEFAULT 1,
  `created_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_plans_slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- investments
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `investments` (
  `id`            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `user_id`       INT UNSIGNED    NOT NULL,
  `plan_id`       INT UNSIGNED    NOT NULL,
  `amount_usd`    DECIMAL(15,2)   NOT NULL,
  `amount_xmr`    BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'piconeros',
  `status`        ENUM('pending_payment','active','matured','withdrawn','cancelled') NOT NULL DEFAULT 'pending_payment',
  `start_date`    DATETIME                 DEFAULT NULL,
  `end_date`      DATETIME                 DEFAULT NULL,
  `total_roi_usd` DECIMAL(15,4)   NOT NULL DEFAULT '0.0000',
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_investments_user`   (`user_id`),
  KEY `idx_investments_plan`   (`plan_id`),
  KEY `idx_investments_status` (`status`),
  CONSTRAINT `fk_investments_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_investments_plan` FOREIGN KEY (`plan_id`) REFERENCES `plans` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- transactions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `transactions` (
  `id`                     INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `user_id`                INT UNSIGNED    NOT NULL,
  `investment_id`          INT UNSIGNED             DEFAULT NULL,
  `type`                   ENUM('deposit','roi','withdrawal','refund') NOT NULL,
  `amount_usd`             DECIMAL(15,4)   NOT NULL DEFAULT '0.0000',
  `amount_xmr`             BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'piconeros',
  `acceptxmr_invoice_id`   VARCHAR(64)              DEFAULT NULL,
  `status`                 ENUM('pending','confirmed','failed','expired') NOT NULL DEFAULT 'pending',
  `confirmations`          INT UNSIGNED    NOT NULL DEFAULT 0,
  `confirmations_required` INT UNSIGNED    NOT NULL DEFAULT 2,
  `callback_payload`       JSON                     DEFAULT NULL,
  `created_at`             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`             DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_transactions_user`       (`user_id`),
  KEY `idx_transactions_investment` (`investment_id`),
  KEY `idx_transactions_invoice`    (`acceptxmr_invoice_id`),
  KEY `idx_transactions_status`     (`status`),
  CONSTRAINT `fk_transactions_user`       FOREIGN KEY (`user_id`)       REFERENCES `users`       (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_transactions_investment` FOREIGN KEY (`investment_id`) REFERENCES `investments` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- payouts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `payouts` (
  `id`                  INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `user_id`             INT UNSIGNED    NOT NULL,
  `investment_id`       INT UNSIGNED             DEFAULT NULL,
  `amount_usd`          DECIMAL(15,2)   NOT NULL,
  `amount_xmr`          BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'piconeros',
  `destination_address` VARCHAR(120)             DEFAULT NULL,
  `status`              ENUM('pending','approved','processing','completed','rejected') NOT NULL DEFAULT 'pending',
  `admin_note`          TEXT                     DEFAULT NULL,
  `approved_by`         INT UNSIGNED             DEFAULT NULL,
  `created_at`          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_payouts_user`        (`user_id`),
  KEY `idx_payouts_investment`  (`investment_id`),
  KEY `idx_payouts_status`      (`status`),
  CONSTRAINT `fk_payouts_user`        FOREIGN KEY (`user_id`)       REFERENCES `users`       (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_payouts_investment`  FOREIGN KEY (`investment_id`) REFERENCES `investments` (`id`) ON DELETE SET NULL,
  CONSTRAINT `fk_payouts_approved_by` FOREIGN KEY (`approved_by`)   REFERENCES `users`       (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- kyc_documents
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `kyc_documents` (
  `id`          INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  `user_id`     INT UNSIGNED    NOT NULL,
  `type`        ENUM('passport','drivers_license','national_id','utility_bill') NOT NULL,
  `file_path`   VARCHAR(255)    NOT NULL,
  `status`      ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',
  `reviewer_id` INT UNSIGNED             DEFAULT NULL,
  `notes`       TEXT                     DEFAULT NULL,
  `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_kyc_user` (`user_id`),
  CONSTRAINT `fk_kyc_user`     FOREIGN KEY (`user_id`)     REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_kyc_reviewer` FOREIGN KEY (`reviewer_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- audit_logs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `audit_logs` (
  `id`          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `user_id`     INT UNSIGNED             DEFAULT NULL,
  `action`      VARCHAR(100)    NOT NULL,
  `entity_type` VARCHAR(60)              DEFAULT NULL,
  `entity_id`   INT UNSIGNED             DEFAULT NULL,
  `old_values`  JSON                     DEFAULT NULL,
  `new_values`  JSON                     DEFAULT NULL,
  `ip_address`  VARCHAR(45)              DEFAULT NULL,
  `user_agent`  VARCHAR(255)             DEFAULT NULL,
  `created_at`  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_audit_user`   (`user_id`),
  KEY `idx_audit_action` (`action`),
  KEY `idx_audit_entity` (`entity_type`, `entity_id`),
  CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- settings  (key→value store)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `settings` (
  `key`        VARCHAR(100) NOT NULL,
  `value`      TEXT                  DEFAULT NULL,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- newsletter_subscribers
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `newsletter_subscribers` (
  `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `email`      VARCHAR(191) NOT NULL,
  `name`       VARCHAR(120)          DEFAULT NULL,
  `status`     ENUM('active','unsubscribed') NOT NULL DEFAULT 'active',
  `token`      VARCHAR(64)           DEFAULT NULL,
  `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_newsletter_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- roi_accruals
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `roi_accruals` (
  `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `investment_id` INT UNSIGNED    NOT NULL,
  `amount_usd`    DECIMAL(15,4)   NOT NULL,
  `accrual_date`  DATE            NOT NULL,
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_roi_investment` (`investment_id`),
  KEY `idx_roi_date`       (`accrual_date`),
  CONSTRAINT `fk_roi_investment` FOREIGN KEY (`investment_id`) REFERENCES `investments` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- sessions  (PHP DB-backed sessions)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS `sessions` (
  `id`            VARCHAR(128)    NOT NULL,
  `user_id`       INT UNSIGNED             DEFAULT NULL,
  `payload`       MEDIUMTEXT      NOT NULL,
  `last_activity` INT UNSIGNED    NOT NULL,
  `ip_address`    VARCHAR(45)              DEFAULT NULL,
  `user_agent`    VARCHAR(255)             DEFAULT NULL,
  `created_at`    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_sessions_user`     (`user_id`),
  KEY `idx_sessions_activity` (`last_activity`),
  CONSTRAINT `fk_sessions_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Default investment plans
INSERT IGNORE INTO `plans` (`name`, `slug`, `description`, `min_amount_usd`, `max_amount_usd`, `daily_roi_percent`, `duration_days`, `type`, `is_active`) VALUES
('Liquid Tokens',      'liquid_tokens', 'Access to a diversified portfolio of liquid crypto tokens with daily returns.', 100.00,   50000.00,  0.0800, 30,  'liquid_token', 1),
('Early Stage Tokens', 'early_tokens',  'Early access to high-potential token projects before public listing.',          500.00,  100000.00,  0.1500, 90,  'early_token',  1),
('Venture Equity',     'venture',       'Institutional-grade venture investments in leading blockchain companies.',     5000.00, 500000.00,  0.2500, 180, 'venture',      1);

-- Default settings
INSERT IGNORE INTO `settings` (`key`, `value`) VALUES
('site_name',          'Pantera Capital Crypto'),
('site_tagline',       'First institutional-grade crypto investment platform.'),
('aum_usd',            '2500000000'),
('total_strategies',   '3'),
('total_investments',  '350'),
('total_countries',    '35'),
('accent_color',       '#C9A227'),
('contact_email',      'contact@cryptoinvest.local');

-- Admin user (password updated by install.sh via UPDATE)
INSERT IGNORE INTO `users` (`name`, `email`, `password_hash`, `role`, `status`, `email_verified_at`, `referral_code`) VALUES
('Admin', 'admin@cryptoinvest.local', 'PLACEHOLDER', 'admin', 'active', NOW(), 'ADMIN0001');

SET FOREIGN_KEY_CHECKS = 1;
