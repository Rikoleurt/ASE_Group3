CREATE DATABASE IF NOT EXISTS ase3
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ase3;

CREATE TABLE IF NOT EXISTS `user` (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_user_email UNIQUE (email),
    CONSTRAINT uq_user_username UNIQUE (username)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- Development account:
-- email: dev@ase3.com
-- password: dev
-- The plaintext password is NOT stored.
INSERT IGNORE INTO `user` (email, username, password)
VALUES (
    'dev@ase3.com',
    'dev',
    'pbkdf2_sha256$600000$c131c210dfbcd7f1103c170d34f25f56$200b07591435d567598aecf533471cd64e06fefa58c8c1332b56822a8c740c6c'
);

CREATE TABLE IF NOT EXISTS user_session (
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    INDEX ix_session_expiry (expires_at),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS analysis (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    format VARCHAR(4) NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    result_schema_version SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    result_json JSON NOT NULL,
    INDEX ix_analysis_user_date (user_id, created_at, id),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
