USE ase3;

-- Run once after 074-symbol-discussions.sql on an existing database.
-- Fresh databases already have these indexes in init.sql.
ALTER TABLE community_discussion
    ADD INDEX ix_discussion_date (created_at DESC, id DESC),
    ADD INDEX ix_discussion_author_date (author_id, created_at DESC, id DESC);
