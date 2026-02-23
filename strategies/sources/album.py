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
import re
import logging
from utils.paths import get_cache_dir 
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data, get_collection_name
from utils.config_loader import get_global_value

def get_sanitized_name(title):
    # Internal logic tracing for string manipulation
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer album with local caching.
    """
    logger.debug(">>> START: strategies.sources.album.run")
    
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
            context_name = f"album__{album.title}__{album.id}"
            # get_tracks handles the heavy lifting of API interaction
            return get_tracks(album.get_tracks(), logger, album, context_name, cache_file)

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
        
    finally:
        logger.debug("<<< END: strategies.sources.album.run")