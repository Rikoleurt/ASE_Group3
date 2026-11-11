-- Additive, rerunnable migration. Select the application database before running.
-- One comment is written once and attached to many glyph occurrences.
-- Bodies are plain text, 1-2000 characters after trimming (enforced by the API);
-- created_at is UTC. tablet_id is the URL-safe corpus slug, e.g. 'HT-13'.

CREATE TABLE IF NOT EXISTS glyph_annotation (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    author_id BIGINT UNSIGNED NOT NULL,
    sign_id VARCHAR(12) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    body VARCHAR(2000) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX ix_glyph_annotation_sign (sign_id, created_at, id),
    INDEX ix_glyph_annotation_author (author_id, created_at),
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS glyph_annotation_target (
    annotation_id BIGINT UNSIGNED NOT NULL,
    tablet_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    position INT UNSIGNED NOT NULL,
    PRIMARY KEY (annotation_id, tablet_id, position),
    INDEX ix_glyph_target_occurrence (tablet_id, position),
    FOREIGN KEY (annotation_id) REFERENCES glyph_annotation(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
