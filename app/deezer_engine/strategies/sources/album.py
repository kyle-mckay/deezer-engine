# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import logging
from utils.infrastructure.paths import get_cache_dir 
from utils.collections import handle_cached_data, get_collection_name
from utils.config import get_global_value
from utils.api.fetching import fetch_shallow_tracks

# Headers returned from Albums:
# Returns: id, readable, title, title_short, title_version, link, isrc, duration,
# track_position, disk_number, rank, explicit_lyrics, explicit_content_lyrics,
# explicit_content_cover, preview, md5_image, artist, album, type.
# Not returned: share, release_date, bpm, gain, available_countries,
# contributors, track_token, time_add, playlist.

def requires_metadata(source_data=None):
    """
    Album source only requires entity ID to fetch tracks
    """
    return False

def get_sanitized_name(title):
    # Internal logic tracing for string manipulation
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer album with local caching.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        album_id = source_data[0].get('id')
        is_artist = source_data[0].get('source',None)
        
        if not album_id:
            logger.error("Source type 'album' failed: missing 'id' in configuration.")
            return []

        # Logic Tracing: Metadata retrieval
        logger.debug(f"Targeting Album ID: {album_id} | Retention: {retention_hrs}h")

        try:
            album = client.get_album(album_id)
            clean_name = get_sanitized_name(album.title)
            cache_file = str(get_cache_dir() / f"album_{album_id}_{clean_name}.json")
            
            logger.debug(f"Resolved Album: '{album.title}' | Cache Key: {clean_name}")

            if not is_artist:
                logger.info(f"Fetching tracks for album: '{album.title}' (ID {album_id})...")

        except Exception as e:
            logger.error(f"Error fetching album metadata for {album_id}: {e}")
            logger.debug("Stack trace:", exc_info=True)
            return []
        
        # Get collection name for database caching
        collection_name = get_collection_name(logger, "album", id=album_id)
        
        def fetch_album():
            """Closure triggered only if cache is invalid or missing."""
            logger.debug(f"Initiating live API fetch for album: {album.id}")
            return fetch_shallow_tracks(album.get_tracks(), logger)


        # Execution via Cache Manager (with database collection support)
        tracks = handle_cached_data(cache_file, retention_hrs, logger, fetch_album, "album", collection_name=collection_name)

        # Consolidated INFO: Single summary line
        logger.debug(f"Loaded {len(tracks)} tracks from album '{album.title}'.")

        # Data Samples for Debugging
        if tracks:
            sample_ids = [t.get('id') for t in tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        return tracks

    except Exception as e:
        logger.error(f"Critical failure in album source: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []