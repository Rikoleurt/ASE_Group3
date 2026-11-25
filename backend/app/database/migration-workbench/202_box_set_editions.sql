-- Additive, rerunnable migration. Select the application database before running.
-- Needs migration-workbench/201 first.

-- A merged edition (scholars' workbench, story D) lists the versions it was merged from:
-- [{"key": "copy:4", "kind": "copy", "title": ..., "owner": "anouk", "version": 7}, ...].
SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box_set' AND COLUMN_NAME = 'merged_from') = 0,
    'ALTER TABLE box_set ADD COLUMN merged_from JSON NULL AFTER kind',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;
