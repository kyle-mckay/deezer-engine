import os
import json
import time
import logging
from utils.paths import get_cache_dir
from utils.deezer_auth import get_tracks

def run(client, config, logger, source_data):
    """
    Fetches the user's favorite tracks.
    source_data keys: 
      - retention: int (hours to keep cache, 0 for live)
    """
    user_id = config.get('config', {}).get('user_id')
    retention_hrs = source_data.get('retention', 0)
    
    # Define cache path based on user_id
    cache_file = str(get_cache_dir() / f"favorites_{user_id}.json")
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Favorites Source Initialization: UserID={user_id}, Retention={retention_hrs}h")
        logger.debug(f"Target cache file: {os.path.abspath(cache_file)}")

    # 1. Check Cache Validity
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        file_age_hrs = (time.time() - mtime) / 3600
        
        logger.debug(f"Cache file found. Age: {file_age_hrs:.2f} hours.")

        if retention_hrs > 0 and file_age_hrs < retention_hrs:
            logger.debug(f"Using cached favorites (Age: {file_age_hrs:.1f}h)")
            try:
                with open(cache_file, 'r') as f:
                    cached_tracks = json.load(f)
                logger.debug(f"Successfully loaded {len(cached_tracks)} tracks from cache.")
                return cached_tracks
            except Exception as e:
                logger.error(f"Failed to read cache file even though it exists: {e}")
        else:
            if logger.isEnabledFor(logging.DEBUG):
                reason = "retention is 0" if retention_hrs == 0 else "cache expired"
                logger.debug(f"Ignoring cache because {reason}.")
    else:
        logger.debug("No cache file exists for favorites.")

    # 2. Fetch Live from Deezer
    logger.info(f"Fetching live favorites from Deezer API for User {user_id}...")
    try:
        # `get_user_tracks` yields a PaginatedList that auto-paginates when iterated
        logger.debug("Calling client.get_user_tracks()... auto-pagination will start now.")

        tracks = get_tracks(client.get_user_tracks(user_id),logger,"favorites",user_id,cache_file)
            
        return tracks

    except Exception as e:
        logger.error(f"Failed to fetch favorites: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Full traceback for API failure:")
            
        # Fallback to cache if available, even if expired
        if os.path.exists(cache_file):
            logger.warning("Falling back to expired cache due to API error.")
            try:
                with open(cache_file, 'r') as f:
                    fallback_ids = json.load(f)
                logger.info(f"Fallback successful: Loaded {len(fallback_ids)} IDs from expired cache.")
                return fallback_ids
            except Exception as read_err:
                logger.error(f"Fallback failed: Could not read cache. {read_err}")
        raise e