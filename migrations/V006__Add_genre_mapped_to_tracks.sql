-- Add genre mapping confirmation flag to tracks table
-- 0 = not yet processed for genre mapping
-- 1 = genre mapping process completed for this track

ALTER TABLE tracks ADD COLUMN genre_mapped INTEGER NOT NULL DEFAULT 0;
