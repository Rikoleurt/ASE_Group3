-- Additive, rerunnable migration. Select the application database before running.
-- Adds the admin and reviewer roles (#80) and makes the seeded dev account both.
-- MySQL has no ADD COLUMN IF NOT EXISTS, so each column is added only when missing.

SET @add_admin = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user' AND COLUMN_NAME = 'is_admin') = 0,
    'ALTER TABLE `user` ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE',
    'DO 0');
PREPARE statement FROM @add_admin;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @add_reviewer = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user' AND COLUMN_NAME = 'is_reviewer') = 0,
    'ALTER TABLE `user` ADD COLUMN is_reviewer BOOLEAN NOT NULL DEFAULT FALSE',
    'DO 0');
PREPARE statement FROM @add_reviewer;
EXECUTE statement;
DEALLOCATE PREPARE statement;

UPDATE `user` SET is_admin = TRUE, is_reviewer = TRUE WHERE username = 'dev';
