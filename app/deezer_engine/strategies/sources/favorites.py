# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from utils.collections import get_collection_name
from utils.api.fetching import fetch_shallow_tracks
from utils.metadata.orchestration import add_key_to_dicts

# Header returned from Favorites:
# Returns: id, readable, title, link, duration, rank, explicit_lyrics,
# explicit_content_lyrics, explicit_content_cover, md5_image, time_add,
# artist, album, type.
# Not returned: title_short, title_version, isrc, share, track_position,
# disk_number, release_date, preview, bpm, gain, available_countries,
# contributors, track_token, playlist.

def requires_metadata(source_data=None):
    """
    No requirements to pull beyond user ID and arl for authentication
    """
    return False

def run(client, config, logger, source_data):
    """
    Fetches the user's favorite tracks.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        user_id = config.get('config', {}).get('user_id')
        if not user_id:
            logger.warning("No User ID found in config; favorites fetch may fail or return empty.")

        masked_id = f"{user_id[0]}...{user_id[-1]}" if user_id and len(str(user_id)) > 2 else "***"
        logger.debug(f"Source parameters: UserID={masked_id}")
        logger.info(f"Fetching tracks from favorites...")
        collection_name = get_collection_name(logger, "favorites")

        logger.debug(f"Initiating live favorites fetch for User {masked_id}.")
        tracks = fetch_shallow_tracks(client.get_user_tracks(user_id), logger) or []
        if tracks:
            tracks = add_key_to_dicts(logger, tracks, 'collection', collection_name)
        
        # Data Samples for Debugging
        if tracks:
            sample_titles = [t.get('title', 'Unknown') for t in tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_titles}")

        return tracks

    except Exception as e:
        logger.error(f"Failed to fetch favorites: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []