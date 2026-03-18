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
"""
Database migration runner.

Migration policy:
- The `migrations/` directory is the single source of truth for schema shape.
- `V001__*.sql` is the current baseline schema for fresh databases.
- Higher versions are incremental migrations from that baseline.
- Migration execution is strict: any SQL failure aborts the current version.
- Post-migration validation runs `PRAGMA foreign_key_check` and `PRAGMA integrity_check`.
"""
import os
import re
from pathlib import Path
from datetime import datetime
import shutil

from __version__ import __version__

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _parse_migration_file(filename):
    """Parse V{number}__{description}.sql format. Returns (version, description) or None."""
    match = re.match(r'V(\d+)__(.+)\.sql$', filename)
    if not match:
        return None
    version = int(match.group(1))
    description = match.group(2).replace('_', ' ')
    return version, description


def _init_schema_version_table(logger=None):
    """Initializes the schema_version table if it doesn't exist."""
    from .database import get_connection
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
    """Get set of all applied migration versions."""
    from .database import get_connection
    
    try:
        with get_connection(logger) as conn:
            cursor = conn.execute("SELECT version FROM schema_version")
            return {row[0] for row in cursor.fetchall()}
    except Exception as e:
        if logger:
            logger.debug(f"Error retrieving applied migrations: {e}")
        return set()


def _get_all_migrations(logger=None):
    """Scan migrations directory and return all migrations in ascending version order."""
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
    """Fail fast on duplicate migration versions."""
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
    """
    Breaking-change guard.
    If DB contains versions not present in current migrations, user must recreate DB.
    """
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

def _backup_database(logger=None):
    """Create a timestamped backup of the database before migrations."""
    from .database import DB_PATH

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


def run_migrations(logger=None):
    """Apply pending SQL migrations from `migrations/` in strict version order."""
    from .database import get_connection
    from .database import DB_PATH

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
        logger.debug(f"Database: Using migrations from {MIGRATIONS_DIR}")
    
    if not pending:
        if logger:
            logger.debug("Database: No pending migrations")
    else:
        if logger:
            logger.info(f"Database: {len(pending)} pending migrations found")

    if pending and pre_migration_db_exists and pre_migration_db_size > 0:
        _backup_database(logger)
    elif pending and logger and is_fresh_or_empty_db:
        logger.debug("Database: Skipping pre-migration backup for fresh/empty database.")

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
        if logger:
            logger.critical(f"Database migrations failed: {e}")
        raise
    finally:
        if logger:
            logger.debug("Database: All migrations completed.")

