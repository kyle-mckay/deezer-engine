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
    
    ## 1. Load Valid Cache
    #if retention_hrs > 0 and os.path.exists(cache_file):
    #    file_age = (time.time() - os.path.getmtime(cache_file)) / 3600
    #    if file_age < retention_hrs:
    #        with open(cache_file, 'r') as f:
    #            logger.debug(f"Valid {context} cache found (age: {file_age:.2f} hrs). Loading from cache.")
    #            return json.load(f)

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

def get_collection_name(logger, type, name=None, id=None):
    """Using the provided variables, attempts to determine the expected 'source_name' in the collections table for cache matching"""
    _log_tag = "utils.cache_manager.get_collection_name"
    logger.debug(f">>> START: {_log_tag}")
    if not type:
        logger.warning(f"Unable to determine collection name, source type is empty.")
        return "unknown"
    else:
        type = type.lower()
        prefix = f"{type}__"

    def _is_id_empty():
        if id:
            logger.debug("id '{id}' is NOT empty")
            return True
        else:
            logger.debug("id '{id}' IS empty")
            return False

    def _is_name_empty():
        if name:
            logger.debug("name '{name}' is NOT empty")
            return True
        else:
            logger.debug("name '{name}' IS empty")
            return False
    match type:
        case "favorites":
            collection = f"{type}"
        case "playlist" | "album" | "artist":
            if _is_id_empty():
                collection = f"{prefix}{id}"
            else:
                collection = "unknown"
        case "smarttracklist":
            if _is_name_empty():
                collection = f"{prefix}{name}"
            else:
                collection = "unknown"
    
    logger.debug(f"Collection name identified as: '{collection}'")

    logger.debug(f"<<< END: {_log_tag}")
    return collection