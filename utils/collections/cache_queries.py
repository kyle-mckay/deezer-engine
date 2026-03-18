# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from datetime import datetime, timedelta

from utils.config_loader import get_global_value
from utils.database import get_connection
from utils.collections.sync import sync_to_collections, validate_sync_integrity


def _blocklist_where_clause(include_blocklisted):
	"""Return SQL predicate for including or excluding blocklisted entities."""
	return "1=1" if include_blocklisted else "COALESCE(blocklisted, 0) = 0"


def fetch_collection(source_name, logger=None, include_blocklisted=False):
	"""Retrieve all tracks and metadata associated with a specific source."""
	track_filter = _blocklist_where_clause(include_blocklisted)
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


def handle_cached_data(
	cache_file,
	retention_hrs,
	logger,
	fetch_callback,
	context,
	collection_name=None,
	fallback_on_error=True,
):
	"""
	Generic cache handler that uses the collections database only.

	`cache_file` is retained for backwards-compatible signatures but is not used.
	"""
	logger.debug(
		f"Starting cache handling for context='{context}', retention_hrs={retention_hrs}, "
		f"collection_name='{collection_name}', fallback_on_error={fallback_on_error}"
	)
	if collection_name:
		logger.debug(f"Collection name: '{collection_name}'")
	else:
		logger.debug(
			f"Warning: No collection_name provided for '{context}'. DB cache lookup will be skipped."
		)

	if collection_name and retention_hrs > 0:
		try:
			if is_collection_cached(collection_name, {"retention": retention_hrs}, logger):
				cached_data = fetch_collection(collection_name, logger)
				if cached_data:
					logger.debug(
						f"Valid cache found in collections for '{collection_name}'. "
						f"Loading {len(cached_data)} tracks from DB cache."
					)
					logger.debug(
						f"Cache handling completed for context='{context}' "
						f"using valid DB cache with {len(cached_data)} tracks."
					)
					return cached_data
		except Exception as exc:
			logger.debug(f"DB cache lookup failed for '{collection_name}': {exc}")

	try:
		data = fetch_callback()
		if collection_name:
			logger.debug(f"Caching fresh {context} data to collections.")
			sync_to_collections(data, logger, collection_name)
		elif data:
			logger.debug(f"Caching fresh {context} data to collections.")
			sync_to_collections(data, logger)

		if collection_name:
			try:
				synced_data = fetch_collection(collection_name, logger)
				validate_sync_integrity(data, synced_data, logger)
			except ValueError as integrity_error:
				logger.warning(
					f"Sync integrity check failed for '{collection_name}'. "
					f"Using fresh data for this run: {integrity_error}"
				)

		logger.debug(
			f"Cache handling completed for context='{context}' using fresh data with {len(data)} tracks."
		)
		return data
	except Exception as exc:
		logger.error(f"Failed to fetch data for {context}, checking for fallback: {exc}")

		if fallback_on_error and collection_name:
			try:
				expired_data = fetch_collection(collection_name, logger)
				if expired_data:
					logger.debug(
						f"Falling back to expired cache for '{collection_name}' "
						f"({len(expired_data)} tracks)."
					)
					logger.debug(
						f"Cache handling completed for context='{context}' "
						f"using expired DB fallback with {len(expired_data)} tracks."
					)
					return expired_data
			except Exception as fallback_exc:
				logger.debug(f"Fallback to expired DB cache failed: {fallback_exc}")

		logger.warning(f"No cache available to fall back on for {context}.")
		logger.debug(f"Cache handling completed for context='{context}' with empty result.")
		return []