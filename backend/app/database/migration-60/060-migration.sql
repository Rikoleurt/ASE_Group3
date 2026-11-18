CREATE TABLE IF NOT EXISTS analysis_comment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    analysis_id BIGINT UNSIGNED NOT NULL,
    author_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    body TEXT NOT NULL,
    INDEX ix_comment_analysis_date (analysis_id, created_at, id),
    INDEX ix_comment_author (author_id),
    FOREIGN KEY (analysis_id) REFERENCES analysis(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;