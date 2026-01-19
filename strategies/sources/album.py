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
    Fetches tracks from a specific Deezer album with local caching.
    source_data:
      - id: str (The numeric album ID)
      - retention: int (hours to keep cache, 0 for live)
    """
    logger.debug("------ sources.album START ------")
    album_id = source_data.get('id')
    retention_hrs = source_data.get('retention', get_global_value('retention', default = 0))
    
    if not album_id:
        logger.error("Source type 'album' requires an 'id'.")
        return []

    # Get album name and data
    try:
        album = client.get_album(album_id)
        clean_name = get_sanitized_name(album.title)
        cache_file = str(get_cache_dir() / f"album_{album_id}_{clean_name}.json")
    except Exception as e:
        logger.error(f"Error fetching album metadata for {album_id}: {e}")
        return []

    def fetch_album():
        # called by handle_cached_data if cache is invalid/missing
        logger.info(f"Fetching tracks from album: '{album.title}'")
        context_name = f"album__{album.title}__{album.id}"
        return get_tracks(album.get_tracks(), logger, album, context_name, cache_file)

    # handle_cached_data will manage the file check, the fetch, and the write-to-disk
    tracks = handle_cached_data(cache_file, retention_hrs, logger, fetch_album, "album")
    
    logger.debug("------ sources.album START ------")
    return tracks