USE ase3;

-- Run once after 061-community.sql. This SELECT reports titles that must be
-- renamed before migration. No discussion or comment is deleted or renamed.
SELECT TRIM(title) COLLATE utf8mb4_0900_as_ci AS duplicate_title, COUNT(*) AS occurrences
FROM community_discussion
GROUP BY TRIM(title) COLLATE utf8mb4_0900_as_ci
HAVING COUNT(*) > 1;

-- One atomic MySQL 8 ALTER: existing duplicate titles abort the entire change.
-- -1 represents the tablet itself; detection IDs are nonnegative (including 0).
ALTER TABLE community_discussion
    ADD COLUMN sign_id BIGINT NULL,
    ADD COLUMN target_key BIGINT GENERATED ALWAYS AS (COALESCE(sign_id, -1)) STORED,
    ADD COLUMN title_key VARCHAR(160) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_ci
        GENERATED ALWAYS AS (TRIM(title)) STORED,
    ADD CONSTRAINT ck_discussion_sign CHECK (sign_id IS NULL OR sign_id >= 0),
    ADD UNIQUE KEY uq_discussion_target (analysis_id, target_key),
    ADD UNIQUE KEY uq_discussion_title (title_key),
    DROP INDEX analysis_id;

CREATE TABLE IF NOT EXISTS community_vote (
    discussion_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    value TINYINT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (discussion_id, user_id),
    INDEX ix_vote_user (user_id),
    CONSTRAINT ck_vote_value CHECK (value IN (-1, 1)),
    FOREIGN KEY (discussion_id) REFERENCES community_discussion(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB;