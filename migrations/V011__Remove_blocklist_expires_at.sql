-- Remove the now unused blocklist_expires_at column.

DROP INDEX IF EXISTS idx_blocklist_expires_at;

ALTER TABLE blocklist DROP COLUMN IF EXISTS blocklist_expires_at;
