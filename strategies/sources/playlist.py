import re
import logging
from utils.paths import get_cache_dir 
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data
from utils.config_loader import get_global_value

def get_sanitized_name(title):
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer playlist with local caching.
    source_data:
      - id: str (The numeric playlist ID)
      - retention: int (hours to keep cache, 0 for live)
    """
    playlist_id = source_data.get('id')
    retention_hrs = source_data.get('retention', get_global_value('retention', default = 0))
    
    if not playlist_id:
        logger.error("Source type 'playlist' requires an 'id'.")
        return []

    # Get playlist name and data
    try:
        playlist = client.get_playlist(playlist_id)
        clean_name = get_sanitized_name(playlist.title)
        cache_file = str(get_cache_dir() / f"playlist_{playlist_id}_{clean_name}.json")
    except Exception as e:
        logger.error(f"Error fetching playlist metadata for {playlist_id}: {e}")
        return []

    def fetch_playlist():
        # called by handle_cached_data if cache is invalid/missing
        logger.info(f"Fetching tracks from playlist: '{playlist.title}'")
        context_name = f"playlist__{playlist.title}__{playlist.id}"
        return get_tracks(playlist.get_tracks(), logger, playlist, context_name, cache_file)

    # handle_cached_data will manage the file check, the fetch, and the write-to-disk
    return handle_cached_data(cache_file, retention_hrs, logger, fetch_playlist, "playlist")