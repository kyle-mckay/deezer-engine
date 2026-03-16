-- Add dedicated blocklist table and ID-based associations for tracks/albums.
-- entity_type: 'track' or 'album'
-- entity_id: matching track/albums primary key
-- total_errors: lifetime number of enrichment failures
-- streak_errors: consecutive failures since last success/reset
-- last_error_code: last API/transport error code or type
-- last_failed_at: ISO timestamp of most recent failure
-- blocklist_expires_at: ISO timestamp indicating when enrichment may be retried

CREATE TABLE IF NOT EXISTS blocklist (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		entity_type TEXT NOT NULL,
		entity_id INTEGER NOT NULL,
		total_errors INTEGER NOT NULL DEFAULT 0,
		streak_errors INTEGER NOT NULL DEFAULT 0,
		last_error_code TEXT,
		last_failed_at TEXT,
		blocklist_expires_at TEXT,
		UNIQUE (entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_blocklist_expires_at ON blocklist (blocklist_expires_at);

ALTER TABLE tracks ADD COLUMN blacklist_id INTEGER;
ALTER TABLE albums ADD COLUMN blacklist_id INTEGER;
ALTER TABLE tracks ADD COLUMN blocklisted INTEGER NOT NULL DEFAULT 0;
ALTER TABLE albums ADD COLUMN blocklisted INTEGER NOT NULL DEFAULT 0;

UPDATE tracks
SET blacklist_id = (
		SELECT b.id
		FROM blocklist b
		WHERE b.entity_type = 'track'
			AND b.entity_id = tracks.id
)
WHERE EXISTS (
		SELECT 1
		FROM blocklist b
		WHERE b.entity_type = 'track'
			AND b.entity_id = tracks.id
);

UPDATE tracks
SET blocklisted = CASE
	WHEN blacklist_id IS NOT NULL THEN 1
	ELSE 0
END;

UPDATE albums
SET blacklist_id = (
		SELECT b.id
		FROM blocklist b
		WHERE b.entity_type = 'album'
			AND b.entity_id = albums.id
)
WHERE EXISTS (
		SELECT 1
		FROM blocklist b
		WHERE b.entity_type = 'album'
			AND b.entity_id = albums.id
);

UPDATE albums
SET blocklisted = CASE
	WHEN blacklist_id IS NOT NULL THEN 1
	ELSE 0
END;
