# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import time
from datetime import timedelta
import logging
from utils.infrastructure.paths import get_cache_dir 
from utils.deezer_auth import get_tracks
from utils.collections import handle_cached_data
from utils.config import get_global_value
import strategies.sources.album as album_strategy 

def requires_metadata(source_data=None):
    """
    Artist source only requires entity ID to fetch tracks through albums
    """
    return False

def get_sanitized_name(title):
    # Internal logic tracing for string manipulation
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer artist by iterating through their albums.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        artist_id = source_data[0].get('id')
        logger.debug(f"Artist source start: artist_id={artist_id}, retention={retention_hrs}h")
        
        if not artist_id:
            logger.error("Source type 'artist' failed: missing 'id' in configuration.")
            return []

        # Logic Tracing: Artist metadata
        try:
            artist = client.get_artist(artist_id)
            albums = artist.get_albums()
            total_albums = len(albums)
            logger.debug(f"Artist: '{artist.name}' | Total albums found: {total_albums}")
        except Exception as e:
            logger.error(f"Failed to retrieve artist metadata for {artist_id}: {e}")
            logger.debug("Stack trace:", exc_info=True)
            return []

        artist_tracks = []
        
        # Throttled Progress: We log a single INFO line before starting the loop
        logger.info(f"Fetching tracks for Artist: '{artist.name}' (ID {artist_id}). Found {total_albums} albums...")
        start_log_time = time.time()
        last_log_time = start_log_time
        log_interval = get_global_value('log_interval',120)
        for i, album_obj in enumerate(albums, start=1):
            logger.debug(f"[{i}/{total_albums}] Dispatching to album strategy: '{album_obj.title}' (ID: {album_obj.id})")
            
            # Inform user during long waits
            current_time = time.time()
            if current_time - last_log_time >= log_interval:
                # 1. Calculate progress
                elapsed_time = current_time - start_log_time
                items_remaining = total_albums - i
                
                # 2. Calculate average time and ETA
                time_per_item = elapsed_time / i
                eta_seconds = items_remaining * time_per_item
                
                # 3. Format seconds
                eta_str = str(timedelta(seconds=int(eta_seconds)))
                percent = f"{i/total_albums:.1%}"

                # 4. Create suffix
                suffix = f"{percent} complete (ETA: {eta_str})..."

                logger.info(f"Processing '{artist.name}': {suffix}")
                last_log_time = current_time 

            album_payload = {
                'id': album_obj.id,
                'retention': retention_hrs,
                'source': 'artist'
            }
            
            # Delegate to existing logic
            tracks = album_strategy.run(client, config, logger, album_payload)
            artist_tracks.extend(tracks)

        logger.debug(f"Successfully aggregated {len(artist_tracks)} tracks from artist '{artist.name}'.")

        # Duplicate tracks and create copy with `artist__<artist name>`
        logger.debug(f"Created duplicate record of tracks for arist collection")
        tracks = []
        sanitized_name = f"artist__{artist_id}"

        tracks = [
            {**track, 'collection': sanitized_name} 
            for track in artist_tracks
        ]
        artist_tracks.extend(tracks)

        # Consolidated INFO: Final result report

        # Data Samples
        if artist_tracks:
            sample_ids = [t.get('id') for t in artist_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        logger.debug(
            f"Artist source end: artist_id={artist_id}, albums={total_albums}, returned={len(artist_tracks)}"
        )

        return artist_tracks

    except Exception as e:
        logger.error(f"Artist aggregation failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []