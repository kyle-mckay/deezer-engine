# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
from pathlib import Path
from datetime import datetime
import shutil

from __version__ import __version__
from .connection import get_connection, DB_PATH
MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "migrations"

"""
Database migration runner.

Migration policy:
- The `migrations/` directory is the single source of truth for schema shape.
- `V001__*.sql` is the current baseline schema for fresh databases.
- Higher versions are incremental migrations from that baseline.
- Migration execution is strict: any SQL failure aborts the current version.
- Post-migration validation runs `PRAGMA foreign_key_check` and `PRAGMA integrity_check`.
"""

def _parse_migration_file(filename):
	match = re.match(r'V(\d+)__(.+)\.sql$', filename)
	if not match:
		return None
	version = int(match.group(1))
	description = match.group(2).replace('_', ' ')
	return version, description

def _init_schema_version_table(logger=None):
	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()
			cursor.execute("""
				CREATE TABLE IF NOT EXISTS schema_version (
					version INTEGER PRIMARY KEY,
					description TEXT NOT NULL,
					applied_at TEXT NOT NULL,
					script_version TEXT NOT NULL
				)
			""")
			conn.commit()
			if logger:
				logger.debug("Database: 'schema_version' table ready.")
	except Exception as e:
		if logger:
			logger.critical(f"Critical Database Failure (Schema_Version): {e}")
		raise

def _get_applied_versions(logger=None):
	try:
		with get_connection(logger) as conn:
			cursor = conn.execute("SELECT version FROM schema_version")
			return {row[0] for row in cursor.fetchall()}
	except Exception as e:
		if logger:
			logger.debug(f"Error retrieving applied migrations: {e}")
		return set()

def _get_all_migrations(logger=None):
	if not MIGRATIONS_DIR.is_dir():
		if logger:
			logger.warning(f"Database: Migrations directory not found at {MIGRATIONS_DIR}")
		return []
	migrations = []
	for filename in sorted(os.listdir(MIGRATIONS_DIR)):
		parsed = _parse_migration_file(filename)
		if parsed:
			version, description = parsed
			migrations.append({
				'version': version,
				'description': description,
				'filename': filename,
				'filepath': MIGRATIONS_DIR / filename
			})
	migrations.sort(key=lambda m: m['version'])
	return migrations

def _validate_migration_index(migrations, logger=None):
	seen = set()
	duplicates = set()
	for migration in migrations:
		version = migration['version']
		if version in seen:
			duplicates.add(version)
		seen.add(version)
	if duplicates:
		dupes = ", ".join(str(v) for v in sorted(duplicates))
		if logger:
			logger.critical(f"Duplicate migration versions detected: {dupes}")
		raise RuntimeError(f"Duplicate migration versions detected: {dupes}")
	if logger:
		logger.debug("Migration index validation passed.")

def _validate_known_applied_versions(applied_versions, discovered_versions, logger=None):
	unknown = applied_versions - discovered_versions
	if unknown:
		unknown_str = ", ".join(str(v) for v in sorted(unknown))
		if logger:
			logger.critical(
				"Database contains applied migrations not present in this migration baseline: "
				f"{unknown_str}. Delete the existing database file and allow Deezer Engine to recreate it."
			)
		raise RuntimeError(
			"Database contains applied migrations that are not present in this code version "
			f"({unknown_str}). This release uses a new migration baseline. "
		)
	if logger:
		logger.debug("Applied migration versions are compatible with current migration set.")

def run_migrations(logger=None):
	pre_migration_db_exists = DB_PATH.exists()
	pre_migration_db_size = DB_PATH.stat().st_size if pre_migration_db_exists else 0
	is_fresh_or_empty_db = (not pre_migration_db_exists) or pre_migration_db_size == 0
	if logger and is_fresh_or_empty_db:
		logger.debug(
			"Database: Fresh/empty database initialization detected; schema will be created from baseline migrations."
		)
	_init_schema_version_table(logger)
	migrations = _get_all_migrations(logger)
	_validate_migration_index(migrations, logger)
	applied_versions = _get_applied_versions(logger)
	discovered_versions = {m['version'] for m in migrations}
	_validate_known_applied_versions(applied_versions, discovered_versions, logger)
	pending = [m for m in migrations if m['version'] not in applied_versions]
	if logger:
		logger.debug(
			"Database: Migration run started "
			f"(pending_count={len(pending)}, discovered_count={len(discovered_versions)}, "
			f"applied_count={len(applied_versions)}, db_exists={pre_migration_db_exists}, "
			f"db_size_bytes={pre_migration_db_size})"
		)
	if logger:
		logger.debug(f"Database: Using migrations from {MIGRATIONS_DIR}")
	if not pending:
		if logger:
			logger.debug("Database: No pending migrations")
	else:
		if logger:
			logger.info(f"Database: {len(pending)} pending migrations found")
	from .integrity import _backup_database, _run_foreign_key_check, _run_integrity_check, _restore_database
	if pending and pre_migration_db_exists and pre_migration_db_size > 0:
		_backup_database(logger)
	elif pending and logger and is_fresh_or_empty_db:
		logger.debug("Database: Skipping pre-migration backup for fresh/empty database.")
	executed_count = 0
	run_failed = False
	try:
		with get_connection(logger) as conn:
			for migration in pending:
				version = migration['version']
				description = migration['description']
				filepath = migration['filepath']
				if logger:
					logger.debug(f"Applying database patch: {version} - {description}")
				try:
					sql = filepath.read_text(encoding="utf-8")
					cursor = conn.cursor()
					cursor.executescript(sql)
					timestamp = datetime.now().isoformat()
					cursor.execute(
						"INSERT INTO schema_version (version, description, applied_at, script_version) VALUES (?, ?, ?, ?)",
						(version, description, timestamp, __version__)
					)
					conn.commit()
					executed_count += 1
					if logger:
						logger.info(f"Applied database patch: {version} - {description}")
				except Exception as e:
					conn.rollback()
					if logger:
						logger.critical(f"Migration {version} failed: {e}")
					raise
			_run_foreign_key_check(conn, logger)
			_run_integrity_check(conn, logger)
			if logger:
				if pending:
					logger.info("Database: Migration validation checks passed")
				else:
					logger.debug("Database: Migration validation checks passed")
	except Exception as e:
		run_failed = True
		if logger:
			logger.critical(f"Database migrations failed: {e}")
		try:
			_restore_database(logger)
		except Exception as restore_exc:
			if logger:
				logger.critical(f"Automatic database restore failed: {restore_exc}")
		raise
	finally:
		if logger:
			log_message = (
				"Database: Migration run completed "
				f"(status={'failed' if run_failed else 'ok'}, executed_count={executed_count}, "
				f"pending_count={len(pending)})"
			)
			if run_failed or executed_count == 0:
				logger.debug(log_message)
			else:
				logger.info(log_message)