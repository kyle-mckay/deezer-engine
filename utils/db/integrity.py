# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime
import shutil

from .connection import DB_PATH

def _backup_database(logger=None):
	"""Create a timestamped backup of the database before migrations."""
	if not DB_PATH.exists():
		if logger:
			logger.debug("Database: No existing database found, skipping backup.")
		return
	try:
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		backup_name = f"deezer_engine_backup_{timestamp}.db"
		backup_path = DB_PATH.parent / backup_name
		shutil.copy2(DB_PATH, backup_path)
		if logger:
			logger.info(f"Database: Backup created at {backup_name}")
			logger.debug(f"Database: Backup saved to {backup_path}")
	except Exception as e:
		if logger:
			logger.warning(f"Database: Failed to create backup - {e}")

def _run_foreign_key_check(conn, logger=None):
	"""Validate foreign key consistency after migrations complete."""
	violations = conn.execute("PRAGMA foreign_key_check").fetchall()
	if violations:
		if logger:
			logger.critical(f"Foreign key validation failed with {len(violations)} violation(s): {violations}")
		raise RuntimeError(f"Foreign key validation failed with {len(violations)} violation(s).")
	if logger:
		logger.debug("Foreign key validation passed.")

def _run_integrity_check(conn, logger=None):
	"""Validate low-level SQLite database integrity after migrations complete."""
	result = conn.execute("PRAGMA integrity_check").fetchone()
	integrity_status = result[0] if result else None
	if integrity_status != "ok":
		if logger:
			logger.critical(f"SQLite integrity check failed: {integrity_status}")
		raise RuntimeError(f"SQLite integrity check failed: {integrity_status}")
	if logger:
		logger.debug("SQLite integrity check passed.")