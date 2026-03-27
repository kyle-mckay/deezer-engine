# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import sqlite3
from pathlib import Path
from ..infrastructure.paths import get_data_dir

def get_db_path():
	"""
	Resolves the database path: [Project Root]/db/deezer_engine.db
	Ensures the 'db' directory exists.
	"""
	base_dir = get_data_dir().resolve()
	db_path = base_dir / 'db' / 'deezer_engine.db'
	return db_path

DB_PATH = get_db_path()

def get_connection(logger=None):
	"""
	Returns a connection to the SQLite database with foreign keys enabled.
	Accepts a logger instance for debugging.
	"""
	try:
		db_path = get_db_path()
		if logger:
			logger.debug(f"Starting SQLite connection setup for database: {db_path}")
		if not db_path.parent.exists():
			if logger:
				logger.debug(f"Creating missing database directory: {db_path.parent}")
			db_path.parent.mkdir(parents=True, exist_ok=True)
		conn = sqlite3.connect(str(db_path))
		conn.execute("PRAGMA foreign_keys = ON;")
		conn.row_factory = sqlite3.Row
		if logger:
			logger.debug(f"Connected to SQLite database at: {db_path}")
		return conn
	except Exception as e:
		if logger:
			logger.error(f"Failed to connect to database: {e}")
		raise

def initialize_all(logger=None):
	"""Initialize database by applying baseline + incremental SQL migrations only."""
	from .migrations import run_migrations
	if logger:
		logger.debug("Starting database initialization (migrations).")
	run_migrations(logger)
	if logger:
		logger.debug("Database initialization completed.")