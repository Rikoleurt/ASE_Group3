-- Additive, rerunnable migration. Select the application database before running.

-- Epigraphic marks on a box (scholars' workbench, story F), as JSON:
-- {certainty: certain|uncertain|illegible, damage: none|partial|restored, alternatives: [sign IDs],
--  word_end: bool, line: int|null, seq: int|null}. NULL reads as no marks.
SET @statement = IF(
    (SELECT COUNT(*) FROM information_schema.COLUMNS
     WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'box' AND COLUMN_NAME = 'marks') = 0,
    'ALTER TABLE box ADD COLUMN marks JSON NULL',
    'DO 0');
PREPARE statement FROM @statement;
EXECUTE statement;
DEALLOCATE PREPARE statement;
