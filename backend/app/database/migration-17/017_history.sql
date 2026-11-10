-- Additive, rerunnable migration. Select the application database before running.

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
