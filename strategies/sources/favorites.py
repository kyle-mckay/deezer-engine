import logging
import os
from utils.paths import get_cache_dir
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data
from utils.config_loader import get_global_value

def run(client, config, logger, source_data):
    """
    Fetches the user's favorite tracks.
    source_data keys: 
      - retention: int (hours to keep cache, 0 for live)
    """
    user_id = config.get('config', {}).get('user_id')
    retention_hrs = source_data.get('retention', get_global_value('retention', default = 0))
    
    # Define cache path based on user_id
    cache_file = str(get_cache_dir() / f"favorites_{user_id}.json")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Favorites Source Initialization: UserID={user_id}, Retention={retention_hrs}h")
        logger.debug(f"Target cache file: {os.path.abspath(cache_file)}")

    def fetch_favorites():
        # called by handle_cached_data if cache is invalid/missing
        logger.info(f"Fetching tracks from favorites for User: '{user_id}'")
        return get_tracks(client.get_user_tracks(user_id), logger, "favorites", user_id, cache_file)

    # handle_cached_data will manage the file check, the fetch, and the write-to-disk
    return handle_cached_data(cache_file, retention_hrs, logger, fetch_favorites, "favorites")