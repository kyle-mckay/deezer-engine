import os
import json
import time
import logging
import re
from utils.paths import get_cache_dir 
from utils.deezer_auth import get_tracks

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer playlist with local caching.
    source_data:
      - id: str (The numeric playlist ID)
      - retention: int (hours to keep cache, 0 for live)
    """
    playlist_id = source_data.get('id')
    retention_hrs = source_data.get('retention', 0)
    
    if not playlist_id:
        logger.error("Source type 'playlist' requires an 'id'.")
        return []

    # 1. Fetch metadata first to get the human-readable name
    try:
        playlist = client.get_playlist(playlist_id)
        # Sanitize name for a safe filename (remove special chars, replace spaces with underscores)
        clean_name = re.sub(r'[^\w\s-]', '', playlist.title).strip().replace(' ', '_')
    except Exception as e:
        logger.error(f"Error fetching playlist metadata for {playlist_id}: {e}")
        return []

    # 2. Update cache path with human-readable name
    cache_file = str(get_cache_dir() / f"playlist_{playlist_id}_{clean_name}.json")
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"--- Playlist Source Run: '{playlist.title}' ({playlist_id}) ---")
        logger.debug(f"Retention setting: {retention_hrs} hours")
        logger.debug(f"Cache file path: {os.path.abspath(cache_file)}")

    # 3. Cache Logic
    if os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        file_age_hrs = (time.time() - mtime) / 3600
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Cache found. Current age: {file_age_hrs:.2f}h")

        if retention_hrs > 0 and file_age_hrs < retention_hrs:
            logger.debug(f"Using cached version of '{playlist.title}' (Age: {file_age_hrs:.1f}h)")
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Loaded {len(cached_data)} tracks from cache.")
                return cached_data
            except Exception as e:
                logger.error(f"Failed to read playlist cache {playlist_id}: {e}")
        else:
            if logger.isEnabledFor(logging.DEBUG):
                reason = "retention set to 0" if retention_hrs == 0 else "cache expired"
                logger.debug(f"Refreshing from API because {reason}.")
    else:
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"No cache file exists for '{playlist.title}'.")

    # 4. API Logic
    try:
        logger.info(f"Fetching live tracks from playlist: '{playlist.title}'")

        playlist_var = f"playlist__{playlist.title}__{playlist.id}"
        tracks = get_tracks(playlist.get_tracks(),logger,playlist,playlist_var,cache_file)
            
        return tracks

    except Exception as e:
        logger.error(f"Error fetching tracks for '{playlist.title}': {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception(f"Traceback for playlist {playlist_id} failure:")
            
        # Fallback to expired cache as a safety net
        if os.path.exists(cache_file):
            logger.warning(f"Returning stale cache for '{playlist.title}' due to API error.")
            with open(cache_file, 'r') as f:
                return json.load(f)
        return []
