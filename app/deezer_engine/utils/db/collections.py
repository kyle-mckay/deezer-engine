# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Database-backed collection cache and sync helpers."""

import json
from datetime import datetime, timedelta

from utils.config import get_global_value
from utils.db.blocklist import blocklist_where_clause
from utils.db.fetch import fetch_entities_by
from utils.infrastructure.signals import shutdown_event
from .connection import get_connection


def fetch_collection(collection_names, logger=None, include_blocklisted=False):
	"""
	Retrieve all tracks and metadata associated with specific collection(s).

	For collection names prefixed with 'track__', directly query the tracks table
	by extracting the track ID. For regular collections, join with the collections table.

	Args:
		collection_names: Single collection name (str) or list of names
		logger: Optional logger instance
		include_blocklisted: Whether to include blocklisted tracks

	Returns:
		Single input: list of track dicts
		List input: dict mapping collection_name → list of track dicts
	"""
	# Normalize input to list internally
	is_single = isinstance(collection_names, str)
	names_to_fetch = [collection_names] if is_single else collection_names

	track_filter = blocklist_where_clause(include_blocklisted)
	result_map = {}
	track_to_collections = {}
	collection_to_track_ids = {}
	regular_collections = []

	# Pre-split collection names for batched track__ resolution and regular joins.
	for source_name in names_to_fetch:
		if not isinstance(source_name, str):
			if logger:
				logger.warning(f"Invalid collection name type: {type(source_name).__name__}")
			result_map[source_name] = []
			continue

		if source_name.startswith("track__"):
			track_id_parts = source_name.split("__")[1:]
			if not track_id_parts:
				if logger:
					logger.warning(f"Invalid track__ format: '{source_name}'")
				result_map[source_name] = []
				continue

			parsed_track_ids = []
			invalid_part = False
			for track_id_part in track_id_parts:
				if track_id_part == "":
					invalid_part = True
					break
				try:
					parsed_track_ids.append(str(int(track_id_part)))
				except ValueError:
					invalid_part = True
					break

			if invalid_part or not parsed_track_ids:
				if logger:
					logger.warning(f"Invalid track__ format: '{source_name}'")
				result_map[source_name] = []
				continue

			# Preserve the first-seen order while removing duplicates in a consolidated key.
			ordered_track_ids = list(dict.fromkeys(parsed_track_ids))
			collection_to_track_ids[source_name] = ordered_track_ids
			for track_id in ordered_track_ids:
				track_to_collections.setdefault(track_id, []).append(source_name)
		else:
			regular_collections.append(source_name)

	try:
		# Resolve track__ collections in one batch query against tracks table.
		if track_to_collections:
			track_rows = fetch_entities_by(
				"tracks",
				"id",
				"IN",
				list(track_to_collections.keys()),
				return_ids_only=False,
				blocklist_clause=track_filter,
				logger=logger,
			)
			rows_by_id = {str(row.get("id")): row for row in track_rows if row.get("id") is not None}

			parsed_rows_by_id = {}
			for track_id, row in rows_by_id.items():
				parsed_track = dict(row)
				if parsed_track.get("available_countries"):
					parsed_track["available_countries"] = json.loads(parsed_track["available_countries"])
				if parsed_track.get("contributors"):
					parsed_track["contributors"] = json.loads(parsed_track["contributors"])
				parsed_rows_by_id[track_id] = parsed_track

			for collection_key, ordered_track_ids in collection_to_track_ids.items():
				tracks_for_collection = [
					dict(parsed_rows_by_id[track_id])
					for track_id in ordered_track_ids
					if track_id in parsed_rows_by_id
				]
				result_map[collection_key] = tracks_for_collection
				if logger:
					logger.debug(
						f"DB: Retrieved {len(tracks_for_collection)} tracks for '{collection_key}' "
						"(batched direct tracks table)."
					)

		with get_connection() as conn:
			for source_name in regular_collections:
				query = f"""
				SELECT t.* FROM tracks t
				JOIN collections c ON t.id = c.track_id
					WHERE c.source_name = ?
						AND {track_filter};
				"""
				cursor = conn.execute(query, (source_name,))
				rows = cursor.fetchall()

				collection_data = []
				for row in rows:
					track = dict(row)
					if track.get("available_countries"):
						track["available_countries"] = json.loads(track["available_countries"])
					if track.get("contributors"):
						track["contributors"] = json.loads(track["contributors"])
					collection_data.append(track)

				result_map[source_name] = collection_data
				if logger:
					logger.debug(f"DB: Retrieved {len(collection_data)} tracks for '{source_name}'.")

			# Return appropriately typed result
			if is_single:
				return result_map[collection_names]
			else:
				return result_map

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Failed to fetch collections: {exc}")
		# Return consistent empty structure
		if is_single:
			return []
		else:
			return {name: [] for name in names_to_fetch}


def is_collection_cached(collection_names, config, logger=None):
	"""
	Check whether collection(s) exist in DB and are within retention window.

	For collection names prefixed with 'track__', always returns True (always queryable
	from tracks table). For regular collections, checks retention window.

	Args:
		collection_names: Single collection name (str) or list of names
		config: Configuration dict with optional 'retention' key
		logger: Optional logger instance

	Returns:
		Single input: bool
		List input: dict mapping collection_name → bool
	"""
	# Normalize input to list internally
	is_single = isinstance(collection_names, str)
	names_to_check = [collection_names] if is_single else collection_names

	retention_hrs = config.get("retention", get_global_value("retention", default=0))
	result_map = {}

	try:
		with get_connection() as conn:
			for source_name in names_to_check:
				# track__ prefixed entries are always considered cached (direct tracks table)
				if source_name.startswith("track__"):
					result_map[source_name] = True
					if logger:
						logger.debug(f"Cache check: '{source_name}' (track__-prefixed, always cached)")
					continue

				# Regular retention window check
				if logger:
					logger.debug(f"Retention hours for '{source_name}': {retention_hrs}")

				query = """
				SELECT date_cached FROM collections
				WHERE source_name = ?
				ORDER BY date_cached DESC LIMIT 1;
				"""

				cursor = conn.execute(query, (source_name,))
				row = cursor.fetchone()

				if not row or not row["date_cached"]:
					result_map[source_name] = False
					if logger:
						logger.debug(f"Cache miss: '{source_name}' not found.")
					continue

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

				result_map[source_name] = is_valid

		# Return appropriately typed result
		if is_single:
			return result_map[collection_names]
		else:
			return result_map

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Cache validation failed: {exc}")
		# Return consistent empty structure (False for single, empty dict for list)
		if is_single:
			return False
		else:
			return {name: False for name in names_to_check}


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
	if shutdown_event.is_set():
		logger.debug("Shutdown event detected before DB sync. Aborting sync operation to prevent malformed collection.")
		return

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
		logger.debug("No collection_name provided; attempting to associate collection from track metadata.")

	# Filter out track__ prefixed entries; these are resolved directly from tracks table
	track_prefixed_pairs = {pair for pair in unique_pairs if pair[1].startswith("track__")}
	if track_prefixed_pairs:
		logger.debug(
			f"Skipping {len(track_prefixed_pairs)} track-prefixed collection entries from DB sync "
			"(resolved directly from tracks table)."
		)
		unique_pairs = {pair for pair in unique_pairs if not pair[1].startswith("track__")}

	if not unique_pairs:
		logger.debug("No non-track-prefixed pairs to sync to collections table.")
		return

	unique_track_ids = {track_id for track_id, _source in unique_pairs}
	logger.debug(f"DB: Syncing {len(unique_track_ids)} unique track IDs.")

	try:
		with get_connection() as conn:
			cursor = conn.cursor()
			date_time = datetime.now().isoformat()

			unique_pairs = {
				(track_id, source_name, date_time) for track_id, source_name in unique_pairs
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