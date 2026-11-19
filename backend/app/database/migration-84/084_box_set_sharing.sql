-- Additive, rerunnable migration. Select the application database before running.
-- Needs migration-83 (corrected copies) first. Sharing corrected copies (#84).

SET @add_column = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box_set' AND COLUMN_NAME = 'everyone') = 0,
    "ALTER TABLE box_set ADD COLUMN everyone ENUM('none', 'view', 'comment', 'edit') NOT NULL DEFAULT 'none' AFTER version",
    'DO 0');
PREPARE statement FROM @add_column;
EXECUTE statement;
DEALLOCATE PREPARE statement;

-- People a corrected copy is shared with (#84), each at one level. The copy's level for
-- everyone logged in is box_set.everyone; a user gets the higher of the two.
CREATE TABLE IF NOT EXISTS box_set_share (
    set_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    permission ENUM('view', 'comment', 'edit', 'manage') NOT NULL,
    granted_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (set_id, user_id),
    INDEX ix_box_set_share_user (user_id, set_id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
