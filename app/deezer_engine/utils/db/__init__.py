# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Database utility package exports."""

from .blocklist import (
	blocklist_where_clause,
	get_album_ids_for_unavailable_tracks,
	mark_album_metadata_fetch_failed,
	mark_track_metadata_fetch_failed,
	release_expired_blocklisted_entities,
)
from .cache import (
	mark_fully_populated_albums_as_cached,
	mark_fully_populated_artists_as_cached,
	mark_fully_populated_tracks_as_cached,
)
from .collections import (
	fetch_collection,
	is_collection_cached,
	sync_to_collections,
	validate_sync_integrity,
)
from .connection import DB_PATH, get_connection, get_db_path, initialize_all
from .fetch import fetch_entities_by
from .integrity import backup_database, foreign_key_check, integrity_check
from .migrations import run_migrations

__all__ = [
	"DB_PATH",
	"backup_database",
	"blocklist_where_clause",
	"fetch_collection",
	"fetch_entities_by",
	"foreign_key_check",
	"get_album_ids_for_unavailable_tracks",
	"get_connection",
	"get_db_path",
	"initialize_all",
	"integrity_check",
	"is_collection_cached",
	"mark_album_metadata_fetch_failed",
	"mark_fully_populated_albums_as_cached",
	"mark_fully_populated_artists_as_cached",
	"mark_fully_populated_tracks_as_cached",
	"mark_track_metadata_fetch_failed",
	"release_expired_blocklisted_entities",
	"run_migrations",
	"sync_to_collections",
	"validate_sync_integrity",
]