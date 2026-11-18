-- Additive, rerunnable migration. Select the application database before running.
-- Needs migration-81 (uploaded images) first.

-- Corrected copies of a tablet's boxes (#83): one per user per upload or corpus tablet.
-- Exactly one of analysis_id and tablet_slug is set (the API ensures it: MySQL allows no CHECK on
-- a column with ON DELETE CASCADE). `version` goes up by one per save; an older one is refused.
CREATE TABLE IF NOT EXISTS box_set (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    owner_id BIGINT UNSIGNED NOT NULL,
    analysis_id BIGINT UNSIGNED NULL,
    tablet_slug VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    start ENUM('model', 'scholar') NOT NULL,
    version INT UNSIGNED NOT NULL DEFAULT 0,
    width INT UNSIGNED NOT NULL,
    height INT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    CONSTRAINT uq_box_set_analysis UNIQUE (owner_id, analysis_id),
    CONSTRAINT uq_box_set_tablet UNIQUE (owner_id, tablet_slug),
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
    INDEX ix_box_set (set_id, id),
    FOREIGN KEY (set_id) REFERENCES box_set(id) ON DELETE CASCADE
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
