USE ase3;

-- Safe to run after migration 074, including databases that already have votes.
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
