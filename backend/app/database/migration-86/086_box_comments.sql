-- Additive, rerunnable migration. Select the application database before running.
-- Needs migration-83 (corrected copies) first.

-- Comments on a corrected copy (#86): on one box (box_id), or on the whole copy (NULL).
-- Plain text, 1-2000 characters after trimming (the API checks); created_at is UTC.
CREATE TABLE IF NOT EXISTS box_comment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    set_id BIGINT UNSIGNED NOT NULL,
    box_id BIGINT UNSIGNED NULL,
    author_id BIGINT UNSIGNED NULL,
    body VARCHAR(2000) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX ix_box_comment_set (set_id, box_id, id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE,
    FOREIGN KEY (box_id) REFERENCES box(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
