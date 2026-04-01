# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import re
import logging
from utils.infrastructure.paths import get_cache_dir 
from utils.collections import handle_cached_data, get_collection_name
from utils.config import get_global_value
from utils.api.fetching import fetch_shallow_tracks

# Headers returned from Playlists:
# Returns: id, readable, title, title_short, title_version, link, isrc,
# duration, rank, explicit_lyrics, explicit_content_lyrics,
# explicit_content_cover, preview, md5_image, time_add, artist, album,
# type, playlist.
# Not returned: share, track_position, disk_number, release_date, bpm,
# gain, available_countries, contributors, track_token.

def requires_metadata(source_data=None):
    """
    Only requires playlist ID to fetch tracks
    """
    return False

def get_sanitized_name(title):
    # Internal logic tracing for string manipulation
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer playlist with local caching.
    """
    try:
        # Configuration extraction logic
        retention_hrs = 0
        if isinstance(source_data, dict):
            source_data = [source_data]
        id_value = source_data[0].get('id')
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))

        if id_value is None:
            logger.error("Source type 'playlist' failed: missing 'id' in configuration.")
            return []

        playlist_ids = id_value if isinstance(id_value, list) else [id_value]
        normalized_playlist_ids = []
        for raw_playlist_id in playlist_ids:
            if raw_playlist_id is None:
                logger.warning("Playlist source received null ID in list input. Skipping entry.")
                continue

            playlist_id = str(raw_playlist_id).strip()
            if not playlist_id:
                logger.warning("Playlist source received empty ID in list input. Skipping entry.")
                continue

            normalized_playlist_ids.append(playlist_id)

        if not normalized_playlist_ids:
            logger.warning("Playlist source has no valid IDs after filtering invalid list entries.")
            return []

        source_collection = get_collection_name(
            logger,
            "playlist",
            id=normalized_playlist_ids if len(normalized_playlist_ids) > 1 else normalized_playlist_ids[0],
        )

        collected_tracks = []

        for playlist_id in normalized_playlist_ids:
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
                continue

            logger.info(f"Fetching tracks for playlist: '{playlist.title}' (ID {playlist_id})...")

            # Keep per-playlist cache collections intact while allowing one merged source output.
            collection_name = get_collection_name(logger, "playlist", id=playlist_id)

            def fetch_playlist():
                # This logic is triggered only if cache is invalid
                logger.debug(f"Cache miss or expired. Initiating live fetch for '{playlist.title}'")
                return fetch_shallow_tracks(playlist.get_tracks(), logger)

            # Process data (with database collection support)
            tracks = handle_cached_data(cache_file, retention_hrs, logger, fetch_playlist, "playlist", collection_name=collection_name)
            if tracks:
                collected_tracks.extend([{**track, 'collection': source_collection} for track in tracks])

        if collected_tracks:
            sample_ids = [t.get('id') for t in collected_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        return collected_tracks

    except Exception as e:
        logger.error(f"Source execution failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []