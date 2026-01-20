import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from .paths import get_data_dir

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
    try:
        if not DB_PATH.parent.exists():
            if logger:
                logger.debug(f"Creating database directory: {DB_PATH.parent}")
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(DB_PATH))
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        
        if logger:
            logger.debug(f"Connected to SQLite database at {DB_PATH}")
        return conn
    except Exception as e:
        if logger:
            logger.error(f"Failed to connect to database: {e}")
        raise

def init_tracks_table(logger=None):
    """Initializes the tracks table based on the Deezer API schema."""
    if logger:
        logger.debug("Initializing 'tracks' table...")
        
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
        date_cached TEXT          -- ISO 8601 format: YYYY-MM-DD
    );
    """
    try:
        with get_connection(logger) as conn:
            conn.execute(query)
            if logger:
                logger.info("Database: 'tracks' table is ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Database initialization failed: {e}")
        raise

def init_collections_table(logger=None):
    """Initializes the collections table for tracking track sources."""
    if logger:
        logger.debug("Initializing 'collections' table...")

    # id: Primary Key (Auto-incrementing)
    # track_id: References tracks(id)
    # source_name: The source (e.g., 'playlist_name', 'liked_songs')
    # Unique constraint ensures we don't duplicate a track within the same source
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
                logger.info("Database: 'collections' table is ready.")
    except Exception as e:
        if logger:
            logger.critical(f"Database: Failed to initialize 'collections' table: {e}")
        raise

def initialize_all(logger=None):
    """Run all initialization functions for the database."""
    init_tracks_table(logger)
    init_collections_table(logger)

if __name__ == "__main__":
    from .logger import setup_logger
    test_logger = setup_logger(name="DB_Init_Test")
    initialize_all(test_logger)