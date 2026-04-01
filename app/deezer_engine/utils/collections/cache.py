# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Collection cache orchestration helpers."""

from utils.db.collections import (
	fetch_collection,
	is_collection_cached,
	sync_to_collections,
	validate_sync_integrity,
)


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