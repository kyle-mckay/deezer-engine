# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
from utils.infrastructure.paths import get_cache_dir
from utils.collections import handle_cached_data, get_collection_name
from utils.config import get_global_value
from utils.api.fetching import fetch_shallow_tracks

def requires_metadata(source_data=None):
    """
    No requirements to pull beyond user ID and arl for authentication
    """
    return False

def run(client, config, logger, source_data):
    """
    Fetches the user's favorite tracks with local caching.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        user_id = config.get('config', {}).get('user_id')
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        if not user_id:
            logger.warning("No User ID found in config; favorites fetch may fail or return empty.")
        
        # Define cache path based on user_id
        cache_file = str(get_cache_dir() / f"favorites_{user_id}.json")

        # Logic Tracing: Parameters
        masked_id = f"{user_id[0]}...{user_id[-1]}" if len(user_id) > 2 else "***"
        logger.debug(f"Source parameters: UserID={masked_id}, Retention={retention_hrs}h")
        logger.debug(f"Resolved cache path: {cache_file}")
        logger.info(f"Fetching tracks from favorites...")

        # Get collection name for database caching
        collection_name = get_collection_name(logger, "favorites", id=user_id)

        def fetch_favorites():
            """Called by handle_cached_data only if cache is invalid/missing."""
            logger.debug(f"Cache miss/expiry for User {masked_id}. Initiating live API fetch.")
            return fetch_shallow_tracks(client.get_user_tracks(user_id), logger)

        # Execution via Cache Manager (with database collection support)
        tracks = handle_cached_data(cache_file, retention_hrs, logger, fetch_favorites, "favorites", collection_name=collection_name)
        
        # Data Samples for Debugging
        if tracks:
            sample_titles = [t.get('title', 'Unknown') for t in tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_titles}")

        return tracks

    except Exception as e:
        logger.error(f"Failed to fetch favorites: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []