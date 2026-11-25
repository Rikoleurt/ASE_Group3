-- Additive, rerunnable migration. Select the application database before running.

-- Notifications (scholars' workbench, story I): a message and a link for each person a change
-- concerns (a share, a comment on their copy, a mention, a vote, an override, a merge of their
-- boxes, their voting rights). Read ones are kept until the user's account is deleted.
CREATE TABLE IF NOT EXISTS notification (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    kind VARCHAR(20) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    actor_id BIGINT UNSIGNED NULL,
    message VARCHAR(300) NOT NULL,
    link VARCHAR(300) NULL,
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    created_at DATETIME(6) NOT NULL,
    read_at DATETIME(6) NULL,
    INDEX ix_notification_user (user_id, id),
    INDEX ix_notification_unread (user_id, read_at),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
