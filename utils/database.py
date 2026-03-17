# Copyright (C) 2026 kylemmkay
# Source: https://codeberg.org/kylemmkay/deezer-engine
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from .paths import get_data_dir
from .db_migrations import run_migrations

def get_db_path():
    """
    Resolves the database path: [Project Root]/db/deezer_engine.db
    Ensures the 'db' directory exists.
    """
    # Get the project root
    base_dir = get_data_dir().resolve()
    
    # Define the 'db' folder path
    db_folder = base_dir / 'db'
    
    # Create the directory if it doesn't exist
    if not db_folder.exists():
        db_folder.mkdir(parents=True, exist_ok=True)
        
    # Define the final file path
    db_path = db_folder / 'deezer_engine.db'
    
    return db_folder / 'deezer_engine.db'

DB_PATH = get_db_path()

def get_connection(logger=None):
    """
    Returns a connection to the SQLite database with foreign keys enabled.
    Accepts a logger instance for debugging.
    """
    if logger:
        logger.debug(">>> START: utils.database.get_connection")
        
    try:
        if not DB_PATH.parent.exists():
            if logger:
                logger.debug(f"Creating missing database directory: {DB_PATH.parent}")
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(DB_PATH))
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        
        if logger:
            logger.debug(f"Connected to SQLite database at: {DB_PATH}")
        return conn
    except Exception as e:
        if logger:
            logger.error(f"Failed to connect to database: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.get_connection")

def init_tracks_table(logger=None):
    """Initializes the tracks table based on the Deezer API schema."""
    if logger:
        logger.debug(">>> START: utils.database.init_tracks_table")
        
    query = """
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
        available_countries TEXT, -- JSON string
        alternative TEXT,         -- JSON string
        contributors TEXT,        -- JSON string
        md5_image TEXT,
        track_token TEXT,
        artist_id INTEGER,
        album_id INTEGER,
        blacklist_id INTEGER,
        blocklisted INTEGER NOT NULL DEFAULT 0,
        date_cached TEXT,          -- ISO 8601 format: YYYY-MM-DD
        FOREIGN KEY (artist_id) REFERENCES artists(id),
        FOREIGN KEY (album_id) REFERENCES albums(id),
        FOREIGN KEY (blacklist_id) REFERENCES blocklist(id)
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'tracks' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Tracks): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_tracks_table")

def init_collections_table(logger=None):
    """Initializes the collections table for tracking track sources."""
    if logger:
        logger.debug(">>> START: utils.database.init_collections_table")

    query = """
    CREATE TABLE IF NOT EXISTS collections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER,
        source_name TEXT,
        date_cached TEXT,
        FOREIGN KEY (track_id) REFERENCES tracks (id),
        UNIQUE(track_id, source_name)
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'collections' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Collections): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_collections_table")

def init_artists_table(logger=None):
    """Initializes the artists table for storing artist metadata."""
    if logger:
        logger.debug(">>> START: utils.database.init_artists_table")

    query = """
    CREATE TABLE IF NOT EXISTS artists (
        id INTEGER PRIMARY KEY,
        date_cached TEXT          -- ISO 8601 format: YYYY-MM-DD
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'artists' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Artists): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_artists_table")

def init_albums_table(logger=None):
    """Initializes the albums table for storing album metadata."""
    if logger:
        logger.debug(">>> START: utils.database.init_albums_table")

    query = """
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
        genre_id INTEGER,
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
        contributors TEXT, -- JSON string
        artist_id INTEGER,
        artist_name TEXT,
        blacklist_id INTEGER,
        blocklisted INTEGER NOT NULL DEFAULT 0,
        date_cached TEXT,
        UNIQUE(id),
        FOREIGN KEY (artist_id) REFERENCES artists(id),
        FOREIGN KEY (blacklist_id) REFERENCES blocklist(id)
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'albums' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Albums): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_albums_table")

def init_genres_table(logger=None):
    """Initializes the genres table for normalized genre storage."""
    if logger:
        logger.debug(">>> START: utils.database.init_genres_table")

    query = """
    CREATE TABLE IF NOT EXISTS genres (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'genres' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Genres): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_genres_table")

def init_album_genres_table(logger=None):
    """Initializes the album_genres junction table for album-genre relationships."""
    if logger:
        logger.debug(">>> START: utils.database.init_album_genres_table")

    query = """
    CREATE TABLE IF NOT EXISTS album_genres (
        album_id INTEGER,
        genre_id INTEGER,
        FOREIGN KEY (album_id) REFERENCES albums (id) ON DELETE CASCADE,
        FOREIGN KEY (genre_id) REFERENCES genres (id) ON DELETE CASCADE,
        PRIMARY KEY (album_id, genre_id)
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'album_genres' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Album_Genres): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_album_genres_table")

def init_track_genres_table(logger=None):
    """Initializes the track_genres denormalized cache table for track-genre relationships."""
    if logger:
        logger.debug(">>> START: utils.database.init_track_genres_table")

    query = """
    CREATE TABLE IF NOT EXISTS track_genres (
        track_id INTEGER,
        genre_id INTEGER,
        FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
        FOREIGN KEY (genre_id) REFERENCES genres (id) ON DELETE CASCADE,
        PRIMARY KEY (track_id, genre_id)
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'track_genres' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Track_Genres): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_track_genres_table")

def init_blocklist_table(logger=None):
    """Initializes the blocklist table for failed track/album metadata fetches."""
    if logger:
        logger.debug(">>> START: utils.database.init_blocklist_table")

    query = """
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
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.debug("Database: 'blocklist' table ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Critical Database Failure (Blocklist): {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.database.init_blocklist_table")

def initialize_all(logger=None):
    """Run all initialization functions for the database."""
    if logger:
        logger.debug(">>> START: utils.database.initialize_all")

    # Check if database already exists before initialization
    is_fresh = not DB_PATH.exists()
    
    # Initialize all tables (safe with CREATE TABLE IF NOT EXISTS)
    # artists and albums must be created before tracks due to FK constraints
    init_artists_table(logger)
    init_blocklist_table(logger)
    init_albums_table(logger)
    init_tracks_table(logger)
    init_genres_table(logger)
    init_album_genres_table(logger)
    init_track_genres_table(logger)
    init_collections_table(logger)
    
    # Run migrations to update existing schemas
    run_migrations(logger, is_fresh)
    
    if logger:
        logger.debug(f"Database: Initialized")
        logger.debug("<<< END: utils.database.initialize_all")

if __name__ == "__main__":
    from .logger import setup_logger
    test_logger = setup_logger(name="DB_Init_Test")
    initialize_all(test_logger)