-- Track the timestamp when blocklisting is actively applied.
-- This enables release logic to use a dynamic blocklist_expiry_days value
-- instead of relying on a precomputed expiry date.

ALTER TABLE blocklist ADD COLUMN blocklist_applied_at TEXT;

-- Backfill from existing failure/blocklist timestamps where available.
UPDATE blocklist
SET blocklist_applied_at = COALESCE(blocklist_applied_at, last_failed_at)
WHERE blocklist_applied_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_blocklist_applied_at ON blocklist (blocklist_applied_at);
