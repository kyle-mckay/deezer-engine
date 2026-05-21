# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from utils.collections import get_collection_name
from utils.config import get_global_value
from utils.api.fetching import fetch_shallow_tracks
from utils.api.playlist import fetch_playlist_info, fetch_playlist_track_ids
from utils.metadata.orchestration import add_key_to_dicts
from strategies.sources.track import run as fetch_enriched_tracks

# Headers returned from Playlists:
# Public path (deezer-python): id, readable, title, title_short, title_version, link, isrc,
#   duration, rank, explicit_lyrics, explicit_content_lyrics, explicit_content_cover,
#   preview, md5_image, time_add, artist, album, type, playlist.
# Private fallback (gw-light → track.py): full track payload shape via fetch_enriched_tracks.


def requires_metadata(source_data=None):
    return False


def run(client, config, logger, source_data):
    """
    Fetches tracks from one or more Deezer playlists.
    Attempts the deezer-python public API first; falls back to the authenticated
    gw-light web API for private playlists or any other access failure.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        id_value = source_data[0].get('id')
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))

        if id_value is None:
            logger.error("Source type 'playlist' failed: missing 'id' in configuration.")
            return []

        playlist_ids = id_value if isinstance(id_value, list) else [id_value]
        normalized_playlist_ids = []
        for raw_id in playlist_ids:
            if raw_id is None:
                logger.warning("Playlist source received null ID in list input. Skipping entry.")
                continue
            playlist_id = str(raw_id).strip()
            if not playlist_id:
                logger.warning("Playlist source received empty ID in list input. Skipping entry.")
                continue
            normalized_playlist_ids.append(playlist_id)

        if not normalized_playlist_ids:
            logger.warning("Playlist source has no valid IDs after filtering invalid list entries.")
            return []

        collected_tracks = []

        for playlist_id in normalized_playlist_ids:
            collection_name = get_collection_name(logger, "playlist", id=playlist_id)
            tracks = _fetch_playlist_tracks(client, config, logger, playlist_id, collection_name, retention_hrs)
            if tracks:
                collected_tracks.extend(tracks)

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


def _fetch_playlist_tracks(client, config, logger, playlist_id, collection_name, retention_hrs):
    """
    Try deezer-python (public API) first. Fall back to the gw-light web API
    for private playlists or any other access failure.
    """
    try:
        playlist = client.get_playlist(playlist_id)
        logger.info(f"Fetching tracks for playlist: '{playlist.title}' (ID {playlist_id})...")
        logger.debug(f"Using deezer-python for public playlist {playlist_id}")
        tracks = fetch_shallow_tracks(playlist.get_tracks(), logger) or []
        if tracks:
            return add_key_to_dicts(logger, tracks, 'collection', collection_name)
        return []
    except Exception as e:
        logger.debug(
            f"deezer-python failed for playlist {playlist_id} ({e}); "
            "falling back to authenticated web API."
        )

    # Web API fallback — works for private playlists
    info = fetch_playlist_info(client, playlist_id, logger)
    if info is None:
        logger.error(f"Failed to retrieve playlist metadata for ID {playlist_id}. Skipping.")
        return []

    visibility = "private" if info['is_private'] else "public"
    logger.info(
        f"Fetching tracks for {visibility} playlist: '{info['title']}' (ID {playlist_id})..."
    )

    track_ids = fetch_playlist_track_ids(client, playlist_id, logger)
    if not track_ids:
        logger.warning(f"No tracks found in playlist '{info['title']}' (ID {playlist_id}).")
        return []

    return fetch_enriched_tracks(client, config, logger, [{
        'id': track_ids,
        'override_collection': collection_name,
        'retention': retention_hrs,
    }]) or []
