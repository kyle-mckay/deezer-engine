-- Add genre-related columns to albums table
-- genres: stores original Deezer genres payload as JSON backup
-- genre_mapped: confirms genre normalization pass completed for album

ALTER TABLE albums ADD COLUMN genres TEXT;
ALTER TABLE albums ADD COLUMN genre_mapped INTEGER NOT NULL DEFAULT 0;
