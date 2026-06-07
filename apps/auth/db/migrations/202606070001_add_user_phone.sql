-- +goose Up
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS phone_e164 TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS users_phone_e164_unique_idx
    ON users (phone_e164)
    WHERE phone_e164 IS NOT NULL;

-- +goose Down
DROP INDEX IF EXISTS users_phone_e164_unique_idx;

ALTER TABLE users
    DROP COLUMN IF EXISTS phone_e164;
