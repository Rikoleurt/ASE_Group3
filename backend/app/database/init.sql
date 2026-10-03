CREATE DATABASE IF NOT EXISTS ase3
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ase3;

CREATE TABLE IF NOT EXISTS `user` (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_email (email)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;

-- Development account:
-- email: dev@ase3.com
-- password: dev
-- The plaintext password is NOT stored.
INSERT IGNORE INTO `user` (email, password)
VALUES (
    'dev@ase3.com',
    'pbkdf2_sha256$600000$c131c210dfbcd7f1103c170d34f25f56$200b07591435d567598aecf533471cd64e06fefa58c8c1332b56822a8c740c6c'
);