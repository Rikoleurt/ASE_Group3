USE ase3;

SELECT username, COUNT(*) AS account_count
FROM `user`
GROUP BY username
HAVING COUNT(*) > 1;

DELETE duplicate_account
FROM `user` AS duplicate_account
INNER JOIN `user` AS kept_account
    ON duplicate_account.username = kept_account.username
    AND duplicate_account.id > kept_account.id;

SELECT ROW_COUNT() AS deleted_duplicate_accounts;

-- DDL commits implicitly in MySQL; a later ALTER failure does not undo DELETE.
ALTER TABLE `user`
ADD CONSTRAINT uq_user_username UNIQUE (username);
