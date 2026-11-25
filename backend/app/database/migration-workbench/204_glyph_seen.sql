-- Additive, rerunnable migration. Select the application database before running.

-- When each user last opened each corpus glyph (scholars' workbench, story I), so a glyph shows a
-- bubble with the activity on it since. glyph_key is "<tablet slug>:<position>" (the scholars'
-- transcription position, as glyph annotations use).
CREATE TABLE IF NOT EXISTS glyph_seen (
    user_id BIGINT UNSIGNED NOT NULL,
    glyph_key VARCHAR(80) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    seen_at DATETIME(6) NOT NULL,
    PRIMARY KEY (user_id, glyph_key),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
