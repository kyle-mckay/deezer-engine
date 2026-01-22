import re
import logging
from utils.paths import get_cache_dir 
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data
from utils.config_loader import get_global_value

def get_sanitized_name(title):
    # Internal logic tracing for string manipulation
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer playlist with local caching.
    """
    logger.debug(">>> START: strategies.sources.playlists.run")
    
    try:
        # Configuration extraction logic
        playlist_id = None
        retention_hrs = 0
        if isinstance(source_data, dict):
            source_data = [source_data]
        playlist_id = source_data[0].get('id')
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        
        if not playlist_id:
            logger.error("Source type 'playlist' failed: missing 'id' in configuration.")
            return []

        # Logic Tracing: Metadata retrieval
        logger.debug(f"Fetching metadata for Playlist ID: {playlist_id}")
        
        try:
            playlist = client.get_playlist(playlist_id)
            clean_name = get_sanitized_name(playlist.title)
            cache_file = str(get_cache_dir() / f"playlist_{playlist_id}_{clean_name}.json")
            
            logger.debug(f"Sanitized playlist name: '{clean_name}' | Cache path: {cache_file}")
        except Exception as e:
            logger.error(f"Failed to retrieve playlist metadata: {e}")
            logger.debug("Stack trace:", exc_info=True)
            return []

        def fetch_playlist():
            # This logic is triggered only if cache is invalid
            logger.debug(f"Cache miss or expired. Initiating live fetch for '{playlist.title}'")
            context_name = f"playlist__{playlist.title}__{playlist.id}"
            return get_tracks(playlist.get_tracks(), logger, playlist, context_name, cache_file)

        # Process data
        tracks = handle_cached_data(cache_file, retention_hrs, logger, fetch_playlist, "playlist")

        if tracks:
            sample_ids = [t.get('id') for t in tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        return tracks

    except Exception as e:
        logger.error(f"Source execution failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []
    finally:
        logger.debug("<<< END: strategies.sources.playlists.run")