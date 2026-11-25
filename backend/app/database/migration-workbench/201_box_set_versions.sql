-- Additive, rerunnable migration. Select the application database before running.
-- Needs migration-83 and migration-84 first.

-- Several copies of a tablet per user (scholars' workbench, story C): each may have a title, and
-- an edition (a copy merged from several versions, story D) is marked by `kind`. The rule of one
-- copy per user per tablet goes; one per user per upload stays.

SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box_set' AND COLUMN_NAME = 'title') = 0,
    'ALTER TABLE box_set ADD COLUMN title VARCHAR(120) NULL AFTER tablet_slug',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box_set' AND COLUMN_NAME = 'kind') = 0,
    "ALTER TABLE box_set ADD COLUMN kind ENUM('copy', 'edition') NOT NULL DEFAULT 'copy' AFTER title",
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;

-- The versions of a tablet are listed by tablet; the owner's foreign key keeps the
-- (owner_id, analysis_id) index, so the old unique key can go.
SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.STATISTICS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box_set' AND INDEX_NAME = 'ix_box_set_tablet') = 0,
    'ALTER TABLE box_set ADD INDEX ix_box_set_tablet (tablet_slug, updated_at)',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box_set' AND CONSTRAINT_NAME = 'uq_box_set_tablet') = 1,
    'ALTER TABLE box_set DROP INDEX uq_box_set_tablet',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;

-- Where each box came from, for credit in merged editions and for following a box back to the
-- scholars' sign: the scholars' or the model's box it started as (source_box_id is the sign's id
-- there), or a box of another copy at a version. NULL for boxes drawn by hand.
SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box' AND COLUMN_NAME = 'source_kind') = 0,
    "ALTER TABLE box ADD COLUMN source_kind ENUM('scholar', 'model', 'copy') NULL, "
    'ADD COLUMN source_set_id BIGINT UNSIGNED NULL, ADD COLUMN source_box_id BIGINT UNSIGNED NULL, '
    'ADD COLUMN source_version INT UNSIGNED NULL, ADD COLUMN source_author_id BIGINT UNSIGNED NULL',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;
