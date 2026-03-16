-- Add FK constraints on tracks.album_id -> albums(id) and tracks.artist_id -> artists(id)
-- SQLite does not support ADD CONSTRAINT via ALTER TABLE, so the table must be rebuilt.
-- Also creates the artists placeholder table if it does not yet exist.

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

CREATE TABLE tracks_new (
    id INTEGER PRIMARY KEY,
    readable INTEGER,
    title TEXT,
    title_short TEXT,
    title_version TEXT,
    unseen INTEGER,
    isrc TEXT,
    link TEXT,
    share TEXT,
    duration INTEGER,
    track_position INTEGER,
    disk_number INTEGER,
    rank INTEGER,
    release_date TEXT,
    explicit_lyrics INTEGER,
    explicit_content_lyrics INTEGER,
    explicit_content_cover INTEGER,
    preview TEXT,
    bpm REAL,
    gain REAL,
    available_countries TEXT, -- JSON string
    alternative TEXT,         -- JSON string
    contributors TEXT,        -- JSON string
    md5_image TEXT,
    track_token TEXT,
    artist_id INTEGER,
    album_id INTEGER,
    date_cached TEXT,
    genre_mapped INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id),
    FOREIGN KEY (album_id) REFERENCES albums(id)
);

INSERT INTO tracks_new SELECT
    id, readable, title, title_short, title_version, unseen, isrc, link, share,
    duration, track_position, disk_number, rank, release_date, explicit_lyrics,
    explicit_content_lyrics, explicit_content_cover, preview, bpm, gain,
    available_countries, alternative, contributors, md5_image, track_token,
    artist_id, album_id, date_cached, genre_mapped
FROM tracks;

DROP TABLE tracks;

ALTER TABLE tracks_new RENAME TO tracks;

COMMIT;

PRAGMA foreign_keys = ON;
