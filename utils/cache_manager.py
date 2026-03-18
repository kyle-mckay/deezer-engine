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
import os
import json
import time
import logging
from utils.infrastructure.paths import get_cache_dir
from utils.db_manager import sync_to_collections, fetch_collection, validate_sync_integrity, is_collection_cached

def handle_cached_data(cache_file, retention_hrs, logger, fetch_callback, context, collection_name=None, fallback_on_error=True):
    """
    Generic cache handler that uses the database collections system.
    1. Checks if valid cache exists in the collections database.
    2. If not, runs source workers fetch function.
    3. If fetch fails and fallback_on_error=True, falls back to expired cache in DB.
    
    Args:
        cache_file: Legacy parameter (ignored) - kept for backward compatibility
        retention_hrs: Cache retention period in hours
        logger: Logger instance
        fetch_callback: Function that fetches fresh data
        context: Context name for logging
        collection_name: Name of the collection in DB (required for DB lookups)
        fallback_on_error: If True, return expired cache on fetch failure
    """
    logger.debug(
        f"Starting cache handling for context='{context}', retention_hrs={retention_hrs}, "
        f"collection_name='{collection_name}', fallback_on_error={fallback_on_error}"
    )
    if collection_name:
        logger.debug(f"Collection name: '{collection_name}'")
    else:
        logger.debug(f"Warning: No collection_name provided for '{context}'. DB cache lookup will be skipped.")
    
    # 1. Try to load valid cache from collections database (if collection_name provided)
    if collection_name and retention_hrs > 0:
        try:
            if is_collection_cached(collection_name, {'retention': retention_hrs}, logger):
                cached_data = fetch_collection(collection_name, logger)
                if cached_data:
                    logger.debug(f"Valid cache found in collections for '{collection_name}'. Loading {len(cached_data)} tracks from DB cache.")
                    logger.debug(f"Cache handling completed for context='{context}' using valid DB cache with {len(cached_data)} tracks.")
                    return cached_data
        except Exception as e:
            logger.debug(f"DB cache lookup failed for '{collection_name}': {e}")

    # 2. Fetch Fresh Data
    try:
        data = fetch_callback()
        if collection_name:
            logger.debug(f"Caching fresh {context} data to collections.")
            sync_to_collections(data, logger, collection_name)
        elif data: # Only cache if we actually got results
            logger.debug(f"Caching fresh {context} data to collections.")
            sync_to_collections(data, logger)
            
            # Validate sync integrity by comparing with fresh fetch from DB
        if collection_name:
            try:
                synced_data = fetch_collection(collection_name, logger)
                validate_sync_integrity(data, synced_data, logger)
            except ValueError as integrity_error:
                logger.warning(f"Sync integrity check failed for '{collection_name}'. Using fresh data for this run: {integrity_error}")

        logger.debug(f"Cache handling completed for context='{context}' using fresh data with {len(data)} tracks.")
        return data
    except Exception as e:
        logger.error(f"Failed to fetch data for {context}, checking for fallback: {e}")
        
        # 3. Fallback: Try to return expired cache from DB
        if fallback_on_error and collection_name:
            try:
                expired_data = fetch_collection(collection_name, logger)
                if expired_data:
                    logger.debug(f"Falling back to expired cache for '{collection_name}' ({len(expired_data)} tracks).")
                    logger.debug(f"Cache handling completed for context='{context}' using expired DB fallback with {len(expired_data)} tracks.")
                    return expired_data
            except Exception as fallback_e:
                logger.debug(f"Fallback to expired DB cache failed: {fallback_e}")
        
        # 4. If collection_name not provided, try old file-based fallback for compatibility
        if fallback_on_error and os.path.exists(cache_file):
            try:
                logger.debug(f"Falling back to physical cache file: {cache_file}")
                with open(cache_file, 'r') as f:
                    file_data = json.load(f)
                logger.debug(f"Cache handling completed for context='{context}' using file fallback with {len(file_data)} tracks.")
                return file_data
            except Exception as file_e:
                logger.debug(f"Physical cache file fallback failed: {file_e}")
        
        logger.warning(f"No cache available to fall back on for {context}.")
        logger.debug(f"Cache handling completed for context='{context}' with empty result.")
        return []

def get_collection_name(logger, type, name=None, id=None):
    """Using the provided variables, attempts to determine the expected 'source_name' in the collections table for cache matching"""
    logger.debug(f"Resolving collection name for type='{type}', name='{name}', id='{id}'")
    if not type:
        logger.warning(f"Unable to determine collection name, source type is empty.")
        return "unknown"
    else:
        type = type.lower()
        prefix = f"{type}__"

    def _has_id():
        """Returns True if id is provided and not empty"""
        if id:
            logger.debug(f"id '{id}' is provided")
            return True
        else:
            logger.debug(f"id is empty or None")
            return False

    def _has_name():
        """Returns True if name is provided and not empty"""
        if name:
            logger.debug(f"name '{name}' is provided")
            return True
        else:
            logger.debug(f"name is empty or None")
            return False
    
    collection = "unknown"
    match type:
        case "favorites" | "history":
            collection = f"{type}"
        case "playlist" | "album" | "artist":
            if _has_id():
                collection = f"{prefix}{id}"
            else:
                collection = "unknown"
        case "smarttracklist":
            if _has_name():
                collection = f"{prefix}{name}"
            else:
                collection = "unknown"
        case "file":
            if _has_name():
                collection = f"{prefix}{name}"
            else:
                collection = "unknown"
    
    logger.debug(f"Collection name identified as: '{collection}'")
    return collection