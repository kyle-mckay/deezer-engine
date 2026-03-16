-- Add album_id column to tracks table if it doesn't already exist
-- SQLite will raise an error if column exists, which is handled by the migration system
ALTER TABLE tracks ADD COLUMN album_id INTEGER;
