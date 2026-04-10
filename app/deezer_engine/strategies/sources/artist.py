# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import time
from datetime import timedelta
from utils.collections import get_collection_name, sync_to_collections
from utils.config import get_global_value
from utils.infrastructure.signals import shutdown_event
import strategies.sources.album as album_strategy 
from utils.metadata.orchestration import add_key_to_dicts

# Headers returned from Artists
# Artist delegates to `album.py`, so returned rows follow the Album payload shape.

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
        id_value = source_data[0].get('id')

        if id_value is None:
            logger.error("Source type 'artist' failed: missing 'id' in configuration.")
            return []

        artist_ids = id_value if isinstance(id_value, list) else [id_value]
        normalized_artist_ids = []
        for raw_artist_id in artist_ids:
            if raw_artist_id is None:
                logger.warning("Artist source received null ID in list input. Skipping entry.")
                continue

            artist_id = str(raw_artist_id).strip()
            if not artist_id:
                logger.warning("Artist source received empty ID in list input. Skipping entry.")
                continue

            normalized_artist_ids.append(artist_id)

        if not normalized_artist_ids:
            logger.warning("Artist source has no valid IDs after filtering invalid list entries.")
            return []

        logger.debug(f"Artist source start: artist_ids={normalized_artist_ids}, retention={retention_hrs}h")

        artist_tracks = []
        for artist_id in normalized_artist_ids:
            collection_artist = get_collection_name(logger, "artist", id=artist_id)
            if shutdown_event.is_set():
                logger.debug("Shutdown acknowledged before next artist lookup. Skipping remaining artists.")
                break

            # Logic Tracing: Artist metadata
            try:
                artist = client.get_artist(artist_id)
                albums = artist.get_albums()
                total_albums = len(albums)
                logger.debug(f"Artist: '{artist.name}' | Total albums found: {total_albums}")
            except Exception as e:
                logger.error(f"Failed to retrieve artist metadata for {artist_id}: {e}")
                logger.debug("Stack trace:", exc_info=True)
                continue

            # Throttled Progress: We log a single INFO line before starting the loop
            logger.info(f"Fetching tracks for Artist: '{artist.name}' (ID {artist_id}). Found {total_albums} albums...")
            start_log_time = time.time()
            last_log_time = start_log_time
            log_interval = get_global_value('log_interval',120)
            for i, album_obj in enumerate(albums, start=1):
                if shutdown_event.is_set():
                    logger.debug(
                        "Shutdown acknowledged during artist album dispatch. "
                        "Skipping remaining albums for this artist."
                    )
                    break

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
                # Manually sync album to collections 
                sync_to_collections(tracks, logger, get_collection_name(logger, "album", id=album_obj.id))
                artist_tracks.extend(add_key_to_dicts(logger,tracks,'collection', collection_artist))

                if shutdown_event.is_set():
                    logger.debug(
                        "Shutdown acknowledged after album strategy run. "
                        "Stopping artist aggregation early."
                    )
                    break

            logger.debug(f"Successfully aggregated {len(artist_tracks)} tracks from artist '{artist.name}'.")

        if not artist_tracks:
            logger.warning("Artist source returned no tracks after processing all valid IDs.")
            return []

        # Data Samples
        if artist_tracks:
            sample_ids = [t.get('id') for t in artist_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        logger.debug(
            f"Artist source end: artist_ids={normalized_artist_ids}, returned={len(artist_tracks)}"
        )

        return artist_tracks

    except Exception as e:
        logger.error(f"Artist aggregation failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []