# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Database-backed collection cache and sync helpers."""

import json
from datetime import datetime, timedelta

from utils.config import get_global_value
from utils.db.blocklist import blocklist_where_clause

from .connection import get_connection


def fetch_collection(source_name, logger=None, include_blocklisted=False):
	"""Retrieve all tracks and metadata associated with a specific source."""
	track_filter = blocklist_where_clause(include_blocklisted)
	query = f"""
	SELECT t.* FROM tracks t
	JOIN collections c ON t.id = c.track_id
		WHERE c.source_name = ?
			AND {track_filter};
	"""

	collection_data = []

	try:
		with get_connection() as conn:
			cursor = conn.execute(query, (source_name,))
			rows = cursor.fetchall()

			for row in rows:
				track = dict(row)

				if track.get("available_countries"):
					track["available_countries"] = json.loads(track["available_countries"])
				if track.get("contributors"):
					track["contributors"] = json.loads(track["contributors"])

				collection_data.append(track)

			if logger:
				logger.debug(f"DB: Retrieved {len(collection_data)} tracks for '{source_name}'.")

			return collection_data

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Failed to fetch '{source_name}': {exc}")
		return []


def is_collection_cached(source_name, config, logger=None):
	"""Check whether a collection exists in DB and is within retention window."""
	retention_hrs = config.get("retention", get_global_value("retention", default=0))
	if logger:
		logger.debug(f"Retention hours for '{source_name}': {retention_hrs}")

	query = """
	SELECT date_cached FROM collections
	WHERE source_name = ?
	ORDER BY date_cached DESC LIMIT 1;
	"""

	try:
		with get_connection() as conn:
			cursor = conn.execute(query, (source_name,))
			row = cursor.fetchone()

			if not row or not row["date_cached"]:
				if logger:
					logger.debug(f"Cache miss: '{source_name}' not found.")
				return False

			cache_time = datetime.fromisoformat(row["date_cached"])
			expiration_time = datetime.now() - timedelta(hours=retention_hrs)
			is_valid = cache_time > expiration_time

			if logger:
				if is_valid:
					logger.debug(
						f"Cache verify: Valid (Age: {cache_time} > Exp: {expiration_time})"
					)
				else:
					logger.debug(
						f"Cache verify: Expired (Age: {cache_time} < Exp: {expiration_time})"
					)

			return is_valid

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Cache validation failed: {exc}")
		return False


def validate_sync_integrity(original_tracks, synced_tracks, logger):
	"""Compare original fetched tracks with synced tracks from the database."""
	if not original_tracks or not synced_tracks:
		logger.warning("Sync validation skipped: One or both track lists are empty.")
		return

	original_ids = {str(track.get("id")) for track in original_tracks}
	synced_ids = {str(track.get("id")) for track in synced_tracks}

	logger.debug(f"Original track count: {len(original_ids)}, Synced track count: {len(synced_ids)}")

	missing_ids = original_ids - synced_ids
	if missing_ids:
		error_msg = (
			"Data integrity error: "
			f"{len(missing_ids)} tracks missing from synced collection. Missing IDs: {missing_ids}"
		)
		logger.error(error_msg)
		raise ValueError(error_msg)

	extra_ids = synced_ids - original_ids
	if extra_ids:
		error_msg = (
			"Data integrity error: "
			f"{len(extra_ids)} unexpected tracks in synced collection. Extra IDs: {extra_ids}"
		)
		logger.error(error_msg)
		raise ValueError(error_msg)

	if original_ids == synced_ids:
		logger.debug(
			"Sync validation passed: "
			f"All {len(original_ids)} track IDs match between original and synced data."
		)
		return

	error_msg = "Sync validation failed: Track ID mismatch detected."
	logger.error(error_msg)
	raise ValueError(error_msg)


def sync_to_collections(tracklist, logger, collection_name=None):
	"""Insert track IDs and collection mappings into database tables."""
	if not tracklist:
		if collection_name:
			try:
				with get_connection() as conn:
					cursor = conn.cursor()
					cursor.execute(
						"DELETE FROM collections WHERE source_name = ?",
						(collection_name,),
					)
					conn.commit()
					logger.debug(
						f"DB: Cleared {cursor.rowcount} cached tracks from '{collection_name}'."
					)
			except Exception as exc:
				logger.error(f"DB Sync failed: {exc}")
			return

		logger.debug("Sync skipped: No tracks provided in payload.")
		return

	if collection_name:
		unique_pairs = {(str(track["id"]), collection_name) for track in tracklist}
		logger.debug(f"Using provided collection_name: '{collection_name}' for all tracks.")
	else:
		unique_pairs = {
			(str(track["id"]), track.get("collection", "unknown")) for track in tracklist
		}

	unique_track_ids = {track_id for track_id, _source in unique_pairs}
	logger.debug(f"DB: Syncing {len(unique_track_ids)} unique track IDs.")

	try:
		with get_connection() as conn:
			cursor = conn.cursor()
			date_time = datetime.now().isoformat()

			if collection_name:
				unique_pairs = {
					(str(track["id"]), collection_name, date_time) for track in tracklist
				}
			else:
				unique_pairs = {
					(str(track["id"]), track.get("collection", "unknown"), date_time)
					for track in tracklist
				}

			unique_track_ids = {
				track_id for track_id, _source, _timestamp in unique_pairs
			}
			track_entries = [(track_id,) for track_id in unique_track_ids]
			cursor.executemany("INSERT OR IGNORE INTO tracks (id) VALUES (?)", track_entries)

			incoming_ids_by_collection = {}
			for track_id, source_name, _timestamp in unique_pairs:
				incoming_ids_by_collection.setdefault(source_name, set()).add(track_id)

			for source_name, incoming_ids in incoming_ids_by_collection.items():
				if incoming_ids:
					placeholders = ",".join("?" * len(incoming_ids))
					delete_query = (
						"DELETE FROM collections WHERE source_name = ? "
						f"AND track_id NOT IN ({placeholders})"
					)
					delete_params = [source_name, *sorted(incoming_ids)]
					cursor.execute(delete_query, delete_params)
				else:
					cursor.execute(
						"DELETE FROM collections WHERE source_name = ?",
						(source_name,),
					)

				if logger and cursor.rowcount > 0:
					logger.debug(
						f"DB: Removed {cursor.rowcount} stale tracks from ['{source_name}']"
					)

			collection_entries = [
				(track_id, source_name, timestamp)
				for track_id, source_name, timestamp in unique_pairs
			]
			cursor.executemany(
				"INSERT OR REPLACE INTO collections (track_id, source_name, date_cached) "
				"VALUES (?, ?, ?)",
				collection_entries,
			)

			conn.commit()
			logger.debug("DB: Transaction committed successfully.")
	except Exception as exc:
		logger.error(f"DB Sync failed: {exc}")