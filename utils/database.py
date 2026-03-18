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
from pathlib import Path
from .infrastructure.paths import get_data_dir
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
    try:
        if logger:
            logger.debug(f"Starting SQLite connection setup for database: {DB_PATH}")
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

def initialize_all(logger=None):
    """Initialize database by applying baseline + incremental SQL migrations only."""
    if logger:
        logger.debug("Starting database initialization (migrations).")

    run_migrations(logger)
    
    if logger:
        logger.debug("Database initialization completed.")

if __name__ == "__main__":
    from .infrastructure.logger import setup_logger
    test_logger = setup_logger(name="DB_Init_Test")
    initialize_all(test_logger)