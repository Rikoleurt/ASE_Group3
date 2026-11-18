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
    analysis_id BIGINT UNSIGNED NOT NULL UNIQUE,
    author_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(160) NOT NULL,
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
