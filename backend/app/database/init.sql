CREATE DATABASE IF NOT EXISTS ase3
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ase3;

CREATE TABLE IF NOT EXISTS `user` (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,     -- manages roles on the admin page
    is_reviewer BOOLEAN NOT NULL DEFAULT FALSE,  -- reviews sign corrections (SIGN_REVIEWERS also grants it)
    PRIMARY KEY (id),
    CONSTRAINT uq_user_email UNIQUE (email),
    CONSTRAINT uq_user_username UNIQUE (username)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- Development account:
-- email: dev@ase3.com
-- password: dev
-- The plaintext password is NOT stored. It is an admin and a reviewer.
INSERT IGNORE INTO `user` (email, username, password, is_admin, is_reviewer)
VALUES (
    'dev@ase3.com',
    'dev',
    'pbkdf2_sha256$600000$c131c210dfbcd7f1103c170d34f25f56$200b07591435d567598aecf533471cd64e06fefa58c8c1332b56822a8c740c6c',
    TRUE,
    TRUE
);

CREATE TABLE IF NOT EXISTS user_session (
    token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    expires_at DATETIME(6) NOT NULL,
    INDEX ix_session_expiry (expires_at),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS analysis (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    filename VARCHAR(255) NOT NULL,
    format VARCHAR(4) NOT NULL,
    size_bytes BIGINT UNSIGNED NOT NULL,
    result_schema_version SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    result_json JSON NOT NULL,
    INDEX ix_analysis_user_date (user_id, created_at, id),
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Corrected copies of a tablet's boxes (#83): one per user per upload, several per corpus tablet.
-- Exactly one of analysis_id and tablet_slug is set (the API ensures it: MySQL allows no CHECK on
-- a column with ON DELETE CASCADE). `version` goes up by one per save; an older one is refused.
CREATE TABLE IF NOT EXISTS box_set (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    owner_id BIGINT UNSIGNED NOT NULL,
    analysis_id BIGINT UNSIGNED NULL,
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    title VARCHAR(120) NULL,  -- several copies of a tablet per user may each have a title (workbench)
    kind ENUM('copy', 'edition') NOT NULL DEFAULT 'copy',  -- an edition is merged from several versions
    merged_from JSON NULL,  -- an edition's sources: [{key, kind, title, owner, version}]
    start ENUM('model', 'scholar') NOT NULL,
    version INT UNSIGNED NOT NULL DEFAULT 0,
    everyone ENUM('none', 'view', 'comment', 'edit') NOT NULL DEFAULT 'none',  -- access for all logged-in users (#84)
    width INT UNSIGNED NOT NULL,
    height INT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT uq_box_set_analysis UNIQUE (owner_id, analysis_id),
    INDEX ix_box_set_tablet (tablet_slug, updated_at),
    FOREIGN KEY (owner_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES analysis(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Coordinates are fractions of the image size. A deleted box is kept (deleted = TRUE) so
-- that undoing the delete can bring it back.
CREATE TABLE IF NOT EXISTS box (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    set_id BIGINT UNSIGNED NOT NULL,
    x DOUBLE NOT NULL,
    y DOUBLE NOT NULL,
    w DOUBLE NOT NULL,
    h DOUBLE NOT NULL,
    sign VARCHAR(32) NULL,
    deleted BOOLEAN NOT NULL DEFAULT FALSE,
    origin ENUM('model', 'scholar', 'user') NOT NULL,
    -- As the model or the scholars drew it, to tell what the user changed; NULL for drawn boxes.
    original_x DOUBLE NULL,
    original_y DOUBLE NULL,
    original_w DOUBLE NULL,
    original_h DOUBLE NULL,
    model_sign VARCHAR(32) NULL,
    model_confidence DOUBLE NULL,
    candidates JSON NULL,
    -- Where the box came from (workbench): the scholars' or model's sign it started as, or another
    -- copy's box at a version; its author is credited in merged editions. NULL for drawn boxes.
    source_kind ENUM('scholar', 'model', 'copy') NULL,
    source_set_id BIGINT UNSIGNED NULL,
    source_box_id BIGINT UNSIGNED NULL,
    source_version INT UNSIGNED NULL,
    source_author_id BIGINT UNSIGNED NULL,
    INDEX ix_box_set (set_id, id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- People a corrected copy is shared with (#84), each at one level. The copy's level for
-- everyone logged in is box_set.everyone; a user gets the higher of the two.
CREATE TABLE IF NOT EXISTS box_set_share (
    set_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    permission ENUM('view', 'comment', 'edit', 'manage') NOT NULL,
    granted_by BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (set_id, user_id),
    INDEX ix_box_set_share_user (user_id, set_id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Every change to a copy: who, when, and the box before and after ({box, sign, deleted}).
CREATE TABLE IF NOT EXISTS box_change (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    set_id BIGINT UNSIGNED NOT NULL,
    author_id BIGINT UNSIGNED NULL,
    created_at DATETIME(6) NOT NULL,
    version INT UNSIGNED NOT NULL,
    action ENUM('add', 'update', 'delete', 'revert') NOT NULL,
    box_id BIGINT UNSIGNED NOT NULL,
    before_state JSON NULL,
    after_state JSON NOT NULL,
    reverts_id BIGINT UNSIGNED NULL,
    reverted_by_id BIGINT UNSIGNED NULL,
    INDEX ix_box_change_set (set_id, id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE SET NULL,
    FOREIGN KEY (box_id) REFERENCES box(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Comments on a corrected copy (#86): on one box (box_id), or on the whole copy (NULL).
-- Plain text, 1-2000 characters after trimming (the API checks); created_at is UTC.
CREATE TABLE IF NOT EXISTS box_comment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    set_id BIGINT UNSIGNED NOT NULL,
    box_id BIGINT UNSIGNED NULL,
    author_id BIGINT UNSIGNED NULL,
    body VARCHAR(2000) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX ix_box_comment_set (set_id, box_id, id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE,
    FOREIGN KEY (box_id) REFERENCES box(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- One comment is written once and attached to many glyph occurrences.
-- Bodies are plain text, 1-2000 characters after trimming (enforced by the API);
-- created_at is UTC. tablet_id is the URL-safe corpus slug, e.g. 'HT-13'.

CREATE TABLE IF NOT EXISTS glyph_annotation (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    author_id BIGINT UNSIGNED NOT NULL,
    sign_id VARCHAR(12) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    body VARCHAR(2000) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX ix_glyph_annotation_sign (sign_id, created_at, id),
    INDEX ix_glyph_annotation_author (author_id, created_at),
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS glyph_annotation_target (
    annotation_id BIGINT UNSIGNED NOT NULL,
    tablet_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    position INT UNSIGNED NOT NULL,
    PRIMARY KEY (annotation_id, tablet_id, position),
    INDEX ix_glyph_target_occurrence (tablet_id, position),
    FOREIGN KEY (annotation_id) REFERENCES glyph_annotation(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sign_correction (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    analysis_id BIGINT UNSIGNED NOT NULL,
    author_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    sign_id INT UNSIGNED NOT NULL,
    box_x DOUBLE NOT NULL,
    box_y DOUBLE NOT NULL,
    box_w DOUBLE NOT NULL,
    box_h DOUBLE NOT NULL,
    original_sign VARCHAR(32) NULL,
    original_label VARCHAR(64) NOT NULL,
    original_confidence DOUBLE NOT NULL,
    model_version VARCHAR(255) NOT NULL,
    image_width INT UNSIGNED NOT NULL,
    image_height INT UNSIGNED NOT NULL,
    proposed_sign VARCHAR(32) NULL,
    uncertain BOOLEAN NOT NULL DEFAULT FALSE,
    note VARCHAR(500) NULL,
    status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'pending',
    reviewer_id BIGINT UNSIGNED NULL,
    reviewed_at DATETIME(6) NULL,
    INDEX ix_correction_status_date (status, created_at, id),
    INDEX ix_correction_analysis_sign (analysis_id, sign_id),
    FOREIGN KEY (analysis_id) REFERENCES analysis(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES `user`(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analysis_comment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    analysis_id BIGINT UNSIGNED NOT NULL,
    author_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    body TEXT NOT NULL,
    INDEX ix_comment_analysis_date (analysis_id, created_at, id),
    INDEX ix_comment_author (author_id),
    FOREIGN KEY (analysis_id) REFERENCES analysis(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

USE ase3;

-- Existing analyses have no row here: their original pixels cannot be recovered.
CREATE TABLE IF NOT EXISTS analysis_image (
    analysis_id BIGINT UNSIGNED NOT NULL PRIMARY KEY,
    storage_key VARCHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL UNIQUE,
    FOREIGN KEY (analysis_id) REFERENCES analysis(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS community_discussion (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    analysis_id BIGINT UNSIGNED NOT NULL,
    sign_id BIGINT NULL,
    target_key BIGINT GENERATED ALWAYS AS (COALESCE(sign_id, -1)) STORED,
    author_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(160) NOT NULL,
    title_key VARCHAR(160) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_ci
        GENERATED ALWAYS AS (TRIM(title)) STORED,
    CONSTRAINT ck_discussion_sign CHECK (sign_id IS NULL OR sign_id >= 0),
    UNIQUE KEY uq_discussion_target (analysis_id, target_key),
    UNIQUE KEY uq_discussion_title (title_key),
    INDEX ix_discussion_date (created_at DESC, id DESC),
    INDEX ix_discussion_author_date (author_id, created_at DESC, id DESC),
    created_at DATETIME(6) NOT NULL,
    FOREIGN KEY (analysis_id) REFERENCES analysis(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS community_comment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    discussion_id BIGINT UNSIGNED NOT NULL,
    author_id BIGINT UNSIGNED NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX ix_community_comment_date (discussion_id, created_at, id),
    FOREIGN KEY (discussion_id) REFERENCES community_discussion(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES `user`(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- analysis_comment remains private. Do not copy it into community_comment.

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
