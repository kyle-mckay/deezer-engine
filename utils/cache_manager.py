import os
import json
import time
import logging
from utils.paths import get_cache_dir
from utils.db_manager import sync_to_collections

def handle_cached_data(cache_file, retention_hrs, logger, fetch_callback, context, fallback_on_error=True):
    """
    Generic cache handler. 
    1. Checks if valid cache exists.
    2. If not, runs source workers fetch function.
    3. If fetch fails, falls back to expired cache.
    """
    logger.debug(f"Handling cache for context '{context}' with retention {retention_hrs} hours.")
    logger.debug(f"Target cache file: {os.path.abspath(cache_file)}")
    
    # 1. Load Valid Cache
    if retention_hrs > 0 and os.path.exists(cache_file):
        file_age = (time.time() - os.path.getmtime(cache_file)) / 3600
        if file_age < retention_hrs:
            with open(cache_file, 'r') as f:
                logger.debug(f"Valid {context} cache found (age: {file_age:.2f} hrs). Loading from cache.")
                return json.load(f)

    # 2. Fetch Fresh Data
    try:
        data = fetch_callback()
        if data: # Only cache if we actually got results
            logger.debug(f"Caching fresh {context} data to collections.")

        return data
    except Exception as e:
        logger.error(f"Failed to fetch data for {context}, checking for fallback: {e}")
        if os.path.exists(cache_file):
            logger.debug(f"Falling back to expired cache for {context}.")
            with open(cache_file, 'r') as f:
                return json.load(f)
        else:
            logger.warn(f"No cache available to fall back on for {context}.")
        return []