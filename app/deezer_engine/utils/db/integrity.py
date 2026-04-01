# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime
import shutil

from .connection import get_db_path

def _backup_database(logger=None):
	"""Create a timestamped backup of the database before migrations."""
	db_path = get_db_path()
	if not db_path.exists():
		if logger:
			logger.debug("Database: No existing database found, skipping backup.")
		return
	try:
		timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
		backup_name = f"deezer_engine_backup_{timestamp}.db"
		backup_path = db_path.parent / backup_name
		shutil.copy2(db_path, backup_path)
		if logger:
			logger.info(f"Database: Backup created at {backup_name}")
			logger.debug(f"Database: Backup saved to {backup_path}")
	except Exception as e:
		if logger:
			logger.warning(f"Database: Failed to create backup - {e}")

def _restore_database(logger=None):
	"""
	Restore the database from the most recent backup file.
	"""
	import re
	db_path = get_db_path()
	backup_dir = db_path.parent
	pattern = re.compile(r"^deezer_engine_backup_\d{8}_\d{6}\.db$")
	backups = [f for f in backup_dir.iterdir() if f.is_file() and pattern.match(f.name)]
	backups.sort(reverse=True)
	if not backups:
		if logger:
			logger.critical("No backup file found to restore database.")
		raise RuntimeError("No backup file found to restore database.")
	latest_backup = backups[0]
	today_str = datetime.now().strftime("%Y%m%d")
	match = re.match(r"deezer_engine_backup_(\d{8})_\d{6}\.db$", latest_backup.name)
	if match:
		backup_date = match.group(1)
		if backup_date != today_str and logger:
			logger.warning(f"The last database backup was not made today, restoring an old version. {latest_backup.name}")
	try:
		shutil.copy2(latest_backup, db_path)
		if logger:
			logger.critical(f"Database restored from backup: {latest_backup}")
	except Exception as e:
		if logger:
			logger.critical(f"Failed to restore database from backup: {e}")
		raise
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


def backup_database(logger=None):
	"""Public wrapper for creating a timestamped database backup."""
	return _backup_database(logger)


def foreign_key_check(conn, logger=None):
	"""Public wrapper for validating foreign key consistency."""
	return _run_foreign_key_check(conn, logger)


def integrity_check(conn, logger=None):
	"""Public wrapper for validating SQLite integrity."""
	return _run_integrity_check(conn, logger)