# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import re
from utils.collections import get_collection_name
from utils.config import get_global_value
from utils.api.fetching import fetch_shallow_tracks
from utils.metadata.orchestration import add_key_to_dicts

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
    Fetches tracks from one or more Deezer playlists.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        id_value = source_data[0].get('id')

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

        collected_tracks = []

        for playlist_id in normalized_playlist_ids:
            # Logic Tracing: Metadata retrieval
            logger.debug(f"Fetching metadata for Playlist ID: {playlist_id}")

            try:
                playlist = client.get_playlist(playlist_id)
                clean_name = get_sanitized_name(playlist.title)
                logger.debug(f"Sanitized playlist name: '{clean_name}'")
            except Exception as e:
                logger.error(f"Failed to retrieve playlist metadata: {e}")
                logger.debug("Stack trace:", exc_info=True)
                continue

            logger.info(f"Fetching tracks for playlist: '{playlist.title}' (ID {playlist_id})...")
            collection_name = get_collection_name(logger, "playlist", id=playlist_id)
            logger.debug(f"Initiating live fetch for '{playlist.title}'")
            tracks = fetch_shallow_tracks(playlist.get_tracks(), logger) or []
            if tracks:
                collected_tracks.extend(add_key_to_dicts(logger, tracks, 'collection', collection_name))

        if collected_tracks:
            sample_ids = [t.get('id') for t in collected_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")
            return collected_tracks

        logger.warning("Playlist source returned no tracks after processing all valid IDs.")
        return []

    except Exception as e:
        logger.error(f"Source execution failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []