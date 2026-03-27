-- V002__add_all_headers_from_api.sql
-- Migration: Add all known API fields to tracks, albums, and artists tables

-- Temporarily disable foreign key constraints to allow schema changes
PRAGMA foreign_keys=OFF;

-- Tracks Table: Add new columns
ALTER TABLE tracks ADD COLUMN album_name TEXT;
ALTER TABLE tracks ADD COLUMN artist_name TEXT;

-- Artists table: Create a new version with the full schema
CREATE TABLE artists_new (
    id INTEGER PRIMARY KEY,
    "name" TEXT,
    link TEXT,
    share TEXT,
    picture TEXT,
    picture_small TEXT,
    picture_medium TEXT,
    picture_big TEXT,
    picture_xl TEXT,
    nb_album INTEGER,
    nb_fan INTEGER,
    radio INTEGER,
    tracklist TEXT,
    date_cached TEXT,
    blacklist_id INTEGER,
    blocklisted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (blacklist_id) REFERENCES blocklist(id)
);

-- Populate the new artists table
-- Collects all unique IDs from the old table and any child references in tracks/albums
INSERT INTO artists_new (id, date_cached)
SELECT id, date_cached FROM (
    SELECT id, date_cached FROM artists WHERE id IS NOT NULL
    UNION
    SELECT artist_id as id, NULL as date_cached FROM albums WHERE artist_id IS NOT NULL
    UNION
    SELECT artist_id as id, NULL as date_cached FROM tracks WHERE artist_id IS NOT NULL
);

-- Drop original and rename new table to 'artists'
-- Ensures that tracks/albums point to the new table by name once keys are re-enabled
DROP TABLE artists;
ALTER TABLE artists_new RENAME TO artists;

-- CLEANUP: Ensure referential integrity for the blocklist
UPDATE artists SET blacklist_id = NULL WHERE blacklist_id NOT IN (SELECT id FROM blocklist);
UPDATE tracks SET blacklist_id = NULL WHERE blacklist_id NOT IN (SELECT id FROM blocklist);
UPDATE albums SET blacklist_id = NULL WHERE blacklist_id NOT IN (SELECT id FROM blocklist);

-- Re-enable foreign key constraints
PRAGMA foreign_keys=ON;