import logging
import os
from utils.paths import get_cache_dir
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data
from utils.config_loader import get_global_value

def run(client, config, logger, source_data):
    """
    Fetches the user's favorite tracks with local caching.
    """
    logger.debug(">>> START: strategies.sources.favorites.run")
    
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        user_id = config.get('config', {}).get('user_id')
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        
        # Define cache path based on user_id
        cache_file = str(get_cache_dir() / f"favorites_{user_id}.json")

        # Logic Tracing: Parameters
        logger.debug(f"Source parameters: UserID={user_id}, Retention={retention_hrs}h")
        logger.debug(f"Resolved cache path: {cache_file}")

        if not user_id:
            logger.warning("No User ID found in config; favorites fetch may fail or return empty.")

        def fetch_favorites():
            """Called by handle_cached_data only if cache is invalid/missing."""
            logger.debug(f"Cache miss/expiry for User {user_id}. Initiating live API fetch.")
            context_name = f"favorites__{user_id}"
            return get_tracks(client.get_user_tracks(user_id), logger, "favorites", user_id, cache_file)

        # Execution via Cache Manager
        tracks = handle_cached_data(cache_file, retention_hrs, logger, fetch_favorites, "favorites")
        
        # Data Samples for Debugging
        if tracks:
            sample_titles = [t.get('title', 'Unknown') for t in tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_titles}")

        return tracks

    except Exception as e:
        logger.error(f"Failed to fetch favorites: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []
        
    finally:
        logger.debug("<<< END: strategies.sources.favorites.run")