-- Add FK constraint on albums.artist_id -> artists(id)
-- SQLite does not support ADD CONSTRAINT via ALTER TABLE, so the table must be rebuilt.

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    date_cached TEXT
);

CREATE TABLE albums_new (
    id INTEGER PRIMARY KEY,
    title TEXT,
    upc TEXT,
    link TEXT,
    share TEXT,
    cover TEXT,
    cover_small TEXT,
    cover_medium TEXT,
    cover_big TEXT,
    cover_xl TEXT,
    md5_image TEXT,
    label TEXT,
    nb_tracks INTEGER,
    duration INTEGER,
    fans INTEGER,
    release_date TEXT,
    record_type TEXT,
    available INTEGER,
    tracklist TEXT,
    explicit_lyrics INTEGER,
    explicit_content_lyrics INTEGER,
    explicit_content_cover INTEGER,
    contributors TEXT,
    artist_id INTEGER,
    artist_name TEXT,
    date_cached TEXT,
    genres TEXT,
    genre_mapped INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id)
);

INSERT INTO albums_new SELECT
    id, title, upc, link, share, cover,
    cover_small, cover_medium, cover_big, cover_xl,
    md5_image, label, nb_tracks, duration, fans,
    release_date, record_type, available, tracklist,
    explicit_lyrics, explicit_content_lyrics, explicit_content_cover,
    contributors, artist_id, artist_name, date_cached,
    genres, genre_mapped
FROM albums;

DROP TABLE albums;

ALTER TABLE albums_new RENAME TO albums;

COMMIT;

PRAGMA foreign_keys = ON;
