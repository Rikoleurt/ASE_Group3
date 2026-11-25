-- Additive, rerunnable migration. Select the application database before running.
-- Needs migration-workbench/202 first.

-- Scholars' workbench, story E: releases of editions, votes on them, the admin override, and
-- voting rights.

-- When an account was made (for the rule that new accounts wait a day before voting; accounts
-- made before this migration have NULL and count as old enough), and whether it may vote.
SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user' AND COLUMN_NAME = 'created_at') = 0,
    'ALTER TABLE `user` ADD COLUMN created_at DATETIME(6) NULL',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;
-- New accounts get the time they are made (existing ones keep NULL), with no change to sign-up.
ALTER TABLE `user` MODIFY COLUMN created_at DATETIME(6) NULL DEFAULT CURRENT_TIMESTAMP(6);

SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user' AND COLUMN_NAME = 'can_vote') = 0,
    'ALTER TABLE `user` ADD COLUMN can_vote BOOLEAN NOT NULL DEFAULT TRUE',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;

-- A release is a snapshot of an edition that never changes: votes, citations and exports point
-- at releases, so editing the edition afterwards cannot change what people backed or cited.
CREATE TABLE IF NOT EXISTS edition_release (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    set_id BIGINT UNSIGNED NOT NULL,
    number INT UNSIGNED NOT NULL,  -- 1, 2, ... per edition
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    title VARCHAR(120) NULL,
    notes VARCHAR(2000) NULL,
    version INT UNSIGNED NOT NULL,  -- the edition's version when released
    width INT UNSIGNED NOT NULL,
    height INT UNSIGNED NOT NULL,
    boxes JSON NOT NULL,  -- [{id, box, sign, source}]
    merged_from JSON NULL,
    contributors JSON NOT NULL,  -- usernames
    created_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL,
    CONSTRAINT uq_release_number UNIQUE (set_id, number),
    INDEX ix_release_tablet (tablet_slug, created_at),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One vote per user per tablet, for one release; changing it replaces it.
CREATE TABLE IF NOT EXISTS edition_vote (
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    release_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (tablet_slug, user_id),
    INDEX ix_vote_release (release_id),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (release_id) REFERENCES edition_release(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- An admin may choose a tablet's accepted edition over the vote, with a reason everyone sees.
-- Rows are kept: the current override is the latest one not cleared.
CREATE TABLE IF NOT EXISTS edition_override (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    release_id BIGINT UNSIGNED NOT NULL,
    admin_id BIGINT UNSIGNED NULL,
    comment VARCHAR(1000) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    cleared_at DATETIME(6) NULL,
    cleared_by BIGINT UNSIGNED NULL,
    clear_comment VARCHAR(1000) NULL,
    INDEX ix_override_tablet (tablet_slug, created_at),
    FOREIGN KEY (release_id) REFERENCES edition_release(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES `user`(id) ON DELETE SET NULL,
    FOREIGN KEY (cleared_by) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Every grant and removal of voting rights, with the admin's reason.
CREATE TABLE IF NOT EXISTS vote_right_change (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    admin_id BIGINT UNSIGNED NULL,
    granted BOOLEAN NOT NULL,
    reason VARCHAR(500) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX ix_vote_right_user (user_id, created_at),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
