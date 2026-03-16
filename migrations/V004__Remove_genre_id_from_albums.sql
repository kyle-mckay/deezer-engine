-- Remove genre_id from albums table and use genre junction table instead
-- Genres are now stored in the genres table with many-to-many relationships in album_genres

ALTER TABLE albums DROP COLUMN genre_id;
