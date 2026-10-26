SELECT username, COUNT(*) AS account_count
FROM user
GROUP BY username
HAVING COUNT(*) > 1;

-- Resolves the bug
ALTER TABLE user
ADD CONSTRAINT uq_user_username UNIQUE (username);
