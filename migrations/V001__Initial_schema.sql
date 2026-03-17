-- Baseline schema
--
-- Breaking migration policy:
-- - This file defines the full live schema for fresh databases.
-- - Python does not create business tables.
-- - New schema changes must be added as incremental V{n}__*.sql files.

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    date_cached TEXT
);

CREATE TABLE IF NOT EXISTS blocklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    total_errors INTEGER NOT NULL DEFAULT 0,
    streak_errors INTEGER NOT NULL DEFAULT 0,
    last_error_code TEXT,
    last_failed_at TEXT,
    blocklist_applied_at TEXT,
    UNIQUE(entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS albums (
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
    blacklist_id INTEGER,
    blocklisted INTEGER NOT NULL DEFAULT 0,
    date_cached TEXT,
    genres TEXT,
    genre_mapped INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id),
    FOREIGN KEY (blacklist_id) REFERENCES blocklist(id)
);

CREATE TABLE IF NOT EXISTS tracks (
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
    available_countries TEXT,
    alternative TEXT,
    contributors TEXT,
    md5_image TEXT,
    track_token TEXT,
    artist_id INTEGER,
    album_id INTEGER,
    blacklist_id INTEGER,
    blocklisted INTEGER NOT NULL DEFAULT 0,
    date_cached TEXT,
    genre_mapped INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artist_id) REFERENCES artists(id),
    FOREIGN KEY (album_id) REFERENCES albums(id),
    FOREIGN KEY (blacklist_id) REFERENCES blocklist(id)
);

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS album_genres (
    album_id INTEGER,
    genre_id INTEGER,
    FOREIGN KEY (album_id) REFERENCES albums (id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres (id) ON DELETE CASCADE,
    PRIMARY KEY (album_id, genre_id)
);

CREATE TABLE IF NOT EXISTS track_genres (
    track_id INTEGER,
    genre_id INTEGER,
    FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES genres (id) ON DELETE CASCADE,
    PRIMARY KEY (track_id, genre_id)
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER,
    source_name TEXT,
    date_cached TEXT,
    FOREIGN KEY (track_id) REFERENCES tracks (id),
    UNIQUE(track_id, source_name)
);

CREATE INDEX IF NOT EXISTS idx_blocklist_applied_at ON blocklist (blocklist_applied_at);
