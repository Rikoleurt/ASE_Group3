-- Additive, rerunnable migration. Select the application database before running.

-- Tablets a user bookmarked (scholars' workbench, story K), listed first on the Tablets page.
CREATE TABLE IF NOT EXISTS tablet_bookmark (
    user_id BIGINT UNSIGNED NOT NULL,
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (user_id, tablet_slug),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
