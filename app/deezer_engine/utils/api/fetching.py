# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""API fetch orchestration helpers."""

from utils.config import get_global_value
from utils.metadata.tracks import flatten_tracks


def _get_artist(client, entity_id, logger):
    logger.debug(f"Fetching artist with ID {entity_id}")
    return client.get_artist(entity_id)


def get_artist_albums(client, entity_id, logger):
    logger.debug(f"Fetching albums for artist with ID {entity_id}")
    return client.get_artist(entity_id).get_albums()


def _get_album(client, entity_id, logger):
    logger.debug(f"Fetching album with ID {entity_id}")
    return client.get_album(entity_id)


def _get_album_tracks(client, entity_id, logger):
    logger.debug(f"Fetching tracks for album with ID {entity_id}")
    return client.get_album(entity_id).get_tracks()


def _get_artist_albums(client, entity_id, logger):
    logger.debug(f"Fetching artist with ID {entity_id}")
    return client.get_artist(entity_id).get_albums()


def _get_playlist_tracks(client, entity_id, logger):
    logger.debug(f"Fetching playlist with ID {entity_id}")
    playlist = client.get_playlist(entity_id)
    logger.debug(f"Playlist '{playlist.title}' is accessible publicly. Returning tracks.")
    return playlist.get_tracks()


def _get_favorites(client, logger):
    logger.debug("Fetching user's favorite tracks.")
    uid = get_global_value("user_id")
    if not uid:
        logger.error("User ID is not set in global config. Cannot fetch favorites.")
        raise ValueError("User ID is required to fetch favorites.")

    return client.get_user(uid).get_tracks()


def fetch_shallow_tracks(paginated_tracks, logger):
    """Consume a paginated track source and return flattened shallow metadata rows."""
    raw_tracks = list(paginated_tracks) if paginated_tracks is not None else []
    logger.debug(f"Fetched {len(raw_tracks)} raw paginated tracks for shallow processing.")
    return flatten_tracks(raw_tracks, logger)