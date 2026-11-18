-- Additive, rerunnable migration. Select the application database before running.
-- Keeps uploaded images (#81): a table for their records and a link from each analysis.
-- Analyses saved before this keep image_id NULL. MySQL has no ADD COLUMN IF NOT EXISTS,
-- so the column and its foreign key are added only when missing.

CREATE TABLE IF NOT EXISTS uploaded_image (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    owner_id BIGINT UNSIGNED NOT NULL,
    storage_key CHAR(32) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    format VARCHAR(4) NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    width INT UNSIGNED NOT NULL,
    height INT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT uq_uploaded_image_key UNIQUE (storage_key),
    INDEX ix_uploaded_image_owner (owner_id, created_at),
    FOREIGN KEY (owner_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET @add_column = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'analysis' AND COLUMN_NAME = 'image_id') = 0,
    'ALTER TABLE analysis ADD COLUMN image_id BIGINT UNSIGNED NULL',
    'DO 0');
PREPARE statement FROM @add_column;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @add_key = IF(
    (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'analysis' AND CONSTRAINT_NAME = 'fk_analysis_image') = 0,
    'ALTER TABLE analysis ADD CONSTRAINT fk_analysis_image FOREIGN KEY (image_id) REFERENCES uploaded_image(id) ON DELETE SET NULL',
    'DO 0');
PREPARE statement FROM @add_key;
EXECUTE statement;
DEALLOCATE PREPARE statement;
