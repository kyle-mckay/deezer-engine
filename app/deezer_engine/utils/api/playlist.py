# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""
Shared playlist operations via the Deezer gw-light and pipe.deezer.com GraphQL APIs.

All functions in this module require a client produced by get_authenticated_client —
they use client.session and client.api_token. Write operations additionally attempt
client.pipe_jwt if the gw-light path is unavailable.

Public API
----------
fetch_playlist_info(client, playlist_id, logger)
    Retrieve playlist metadata (title, description, privacy, track count).
    Works for both public and private playlists.

fetch_playlist_track_ids(client, playlist_id, logger)
    Return a list of track ID strings from a playlist.
    Works for both public and private playlists.

set_playlist_privacy(client, playlist_id, is_private, logger)
rename_playlist(client, playlist_id, title, logger)
set_playlist_description(client, playlist_id, description, logger)
    Standalone mutation hooks that fetch current playlist state first, then send an
    UpdatePlaylist GraphQL mutation to pipe.deezer.com.
    Requires a valid pipe JWT (client.pipe_jwt). The JWT is only obtainable when
    'refresh_token' is set in config.yml (browser cookie exported alongside the ARL).
    Without it, these operations raise RuntimeError.
"""

import json
import logging
import random

from utils.api.auth import get_or_refresh_pipe_jwt

# GraphQL mutation used by all playlist metadata write operations.
# Captured verbatim from browser network traffic against pipe.deezer.com/api.
_UPDATE_PLAYLIST_MUTATION = (
    "mutation UpdatePlaylist($input: PlaylistUpdateMutationInput!) {\n"
    "  updatePlaylist(input: $input) {\n"
    "    playlist {\n"
    "      ...PlaylistInfo\n"
    "      __typename\n"
    "    }\n"
    "    __typename\n"
    "  }\n"
    "}\n"
    "\n"
    "fragment PlaylistInfo on Playlist {\n"
    "  ...PlaylistBase\n"
    "  description\n"
    "  isPrivate\n"
    "  isCollaborative\n"
    "  defaultPicture {\n"
    "    id\n"
    "    ...PictureSmall\n"
    "    ...PictureMedium\n"
    "    __typename\n"
    "  }\n"
    "  __typename\n"
    "}\n"
    "\n"
    "fragment PlaylistBase on Playlist {\n"
    "  id\n"
    "  picture {\n"
    "    ...PictureSmall\n"
    "    ...PictureMedium\n"
    "    ...PictureLarge\n"
    "    __typename\n"
    "  }\n"
    "  title\n"
    "  __typename\n"
    "}\n"
    "\n"
    "fragment PictureSmall on Picture {\n"
    "  id\n"
    "  small: urls(pictureRequest: {height: 100, width: 100})\n"
    "  explicitStatus\n"
    "  __typename\n"
    "}\n"
    "\n"
    "fragment PictureMedium on Picture {\n"
    "  id\n"
    "  medium: urls(pictureRequest: {width: 264, height: 264})\n"
    "  explicitStatus\n"
    "  __typename\n"
    "}\n"
    "\n"
    "fragment PictureLarge on Picture {\n"
    "  id\n"
    "  large: urls(pictureRequest: {width: 500, height: 500})\n"
    "  explicitStatus\n"
    "  __typename\n"
    "}"
)


def gw_post(client, method, payload, logger):
    """
    Make a single authenticated gw-light POST and return the parsed results dict.
    Raises RuntimeError if the session is missing or the gateway returns an error.
    """
    if not client.session or not client.api_token:
        raise RuntimeError(
            "Client has no active web session. "
            "Ensure get_authenticated_client completed successfully."
        )

    cid = random.randint(100000000, 999999999)
    url = (
        f"https://www.deezer.com/ajax/gw-light.php?method={method}"
        f"&input=3&api_version=1.0&api_token={client.api_token}&cid={cid}"
    )
    resp = client.session.post(url, data=json.dumps(payload))
    resp.raise_for_status()
    data = resp.json()
    if data.get('error'):
        raise RuntimeError(f"gw-light error for {method}: {data['error']}")
    return data.get('results', {})


def fetch_playlist_info(client, playlist_id, logger):
    """
    Fetch playlist metadata via deezer.pagePlaylist.
    Works for both public and private playlists (requires authenticated session).

    Returns a dict:
        id            str
        title         str
        description   str
        is_private    bool   (STATUS 0=public, 1=private)
        is_collaborative bool
        track_count   int

    Returns None on failure.
    """
    logger.debug(f"Fetching playlist info for ID: {playlist_id}")
    try:
        results = gw_post(client, "deezer.pagePlaylist", {
            "playlist_id": str(playlist_id),
            "lang": "en",
            "tab": 0,
            "nb": 0,
            "start": 0,
            "tags": True,
            "header": True,
        }, logger)

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"deezer.pagePlaylist result keys: {list(results.keys())}")

        data = results.get('DATA', {})
        if not data:
            logger.error(f"deezer.pagePlaylist returned no DATA for playlist {playlist_id}")
            return None

        # STATUS: 0 = public, 1 = private (confirmed from network recordings)
        status = data.get('STATUS', 0)
        # COLLAB_KEY is a pre-generated invite key present on all user playlists — it does NOT
        # indicate active collaboration. deezer.pagePlaylist has no reliable is_collaborative field;
        # the browser always sends isCollaborative: false for regular user playlists.
        is_collaborative = False
        logger.debug(f"Playlist {playlist_id}: STATUS={status}, is_private={bool(status)}")

        return {
            'id': str(playlist_id),
            'title': data.get('TITLE', ''),
            'description': data.get('DESCRIPTION', ''),
            'is_private': bool(status),
            'is_collaborative': is_collaborative,
            'track_count': data.get('NB_SONG', 0),
        }
    except Exception as e:
        logger.error(f"Failed to fetch playlist info for {playlist_id}: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return None


def fetch_playlist_track_ids(client, playlist_id, logger):
    """
    Fetch all track IDs from a playlist via deezer.pagePlaylist.
    Works for both public and private playlists.
    Returns a list of track ID strings.
    """
    logger.debug(f"Fetching track IDs for playlist {playlist_id}")
    try:
        results = gw_post(client, "deezer.pagePlaylist", {
            "playlist_id": str(playlist_id),
            "lang": "en",
            "tab": 0,
            "nb": 10000,
            "start": 0,
            "tags": True,
            "header": True,
        }, logger)

        songs = results.get('SONGS', {})
        tracks = songs.get('data', []) if isinstance(songs, dict) else []
        total = songs.get('total', 0) if isinstance(songs, dict) else 0

        track_ids = [str(t['SNG_ID']) for t in tracks if t.get('SNG_ID')]

        if total and total > len(track_ids):
            logger.warning(
                f"Playlist {playlist_id} has {total} tracks but only {len(track_ids)} were returned. "
                "Pagination not yet implemented; results are truncated."
            )

        logger.debug(f"Fetched {len(track_ids)} track IDs from playlist {playlist_id}")
        return track_ids
    except Exception as e:
        logger.error(f"Failed to fetch track IDs for playlist {playlist_id}: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []


def _update_playlist_metadata(client, playlist_id, title, description, is_private, logger, is_collaborative=None):
    """
    Send an UpdatePlaylist mutation to pipe.deezer.com.

    title, description, and is_private are required. is_collaborative is optional —
    when None it is omitted from the payload, leaving the server to preserve its current value.

    Raises RuntimeError if no valid JWT is available.
    Returns the updated playlist dict from the API response.
    """
    jwt = get_or_refresh_pipe_jwt(client, logger)

    input_data = {
        "playlistId": str(playlist_id),
        "title": title,
        "description": description,
        "isPrivate": bool(is_private),
    }
    if is_collaborative is not None:
        input_data["isCollaborative"] = bool(is_collaborative)

    payload = {
        "operationName": "UpdatePlaylist",
        "variables": {"input": input_data},
        "query": _UPDATE_PLAYLIST_MUTATION,
    }

    headers = {
        "Content-Type": "application/json",
        "Referer": "https://www.deezer.com/",
        "Origin": "https://www.deezer.com",
    }
    if jwt:
        headers["authorization"] = f"Bearer {jwt}"
    else:
        logger.debug(
            "UpdatePlaylist: no pipe JWT — attempting with session cookies only."
        )

    resp = client.session.post("https://pipe.deezer.com/api", json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    if data.get('errors'):
        raise RuntimeError(f"UpdatePlaylist GraphQL error for {playlist_id}: {data['errors']}")

    updated = data.get('data', {}).get('updatePlaylist', {}).get('playlist', {})
    logger.debug(
        f"UpdatePlaylist success: id={playlist_id}, title='{updated.get('title')}', "
        f"isPrivate={updated.get('isPrivate')}, isCollaborative={updated.get('isCollaborative')}"
    )
    return updated


def update_playlist(client, playlist_id, logger, *, title=None, description=None, is_private=None, is_collaborative=None):
    """
    Update one or more metadata fields of an owned playlist in a single API call.
    Fetches the current state first; only the provided keyword arguments are overridden.
    Unspecified fields (None) keep their current value.

    is_collaborative: when None (default), the field is omitted from the mutation payload
    so the server preserves its current value. Pass True/False to change it explicitly.

    Requires client.pipe_jwt — see 'refresh_token' in config.yml.
    Raises RuntimeError if the current state cannot be fetched or the JWT is unavailable.
    """
    info = fetch_playlist_info(client, playlist_id, logger)
    if info is None:
        raise RuntimeError(
            f"Cannot update playlist: failed to fetch current state for {playlist_id}"
        )
    return _update_playlist_metadata(
        client, playlist_id,
        title=title if title is not None else info['title'],
        description=description if description is not None else info['description'],
        is_private=is_private if is_private is not None else info['is_private'],
        is_collaborative=is_collaborative,  # None = omit from payload, server preserves value
        logger=logger,
    )


def set_playlist_privacy(client, playlist_id, is_private, logger):
    """
    Set the privacy of an owned playlist.
    Fetches the current title/description/collaborative state first to preserve them.
    """
    info = fetch_playlist_info(client, playlist_id, logger)
    if info is None:
        raise RuntimeError(
            f"Cannot set privacy: failed to fetch current state for playlist {playlist_id}"
        )
    logger.debug(
        f"set_playlist_privacy: id={playlist_id}, "
        f"is_private={is_private} (was {info['is_private']})"
    )
    return _update_playlist_metadata(
        client, playlist_id,
        title=info['title'],
        description=info['description'],
        is_private=is_private,
        is_collaborative=None,  # omit from payload; server preserves current value
        logger=logger,
    )


def rename_playlist(client, playlist_id, title, logger):
    """
    Rename an owned playlist.
    Fetches the current description/privacy/collaborative state first to preserve them.
    """
    info = fetch_playlist_info(client, playlist_id, logger)
    if info is None:
        raise RuntimeError(
            f"Cannot rename: failed to fetch current state for playlist {playlist_id}"
        )
    logger.debug(
        f"rename_playlist: id={playlist_id}, "
        f"title='{title}' (was '{info['title']}')"
    )
    return _update_playlist_metadata(
        client, playlist_id,
        title=title,
        description=info['description'],
        is_private=info['is_private'],
        is_collaborative=None,  # omit from payload; server preserves current value
        logger=logger,
    )


def set_playlist_description(client, playlist_id, description, logger):
    """
    Update the description of an owned playlist.
    Fetches the current title/privacy/collaborative state first to preserve them.
    """
    info = fetch_playlist_info(client, playlist_id, logger)
    if info is None:
        raise RuntimeError(
            f"Cannot set description: failed to fetch current state for playlist {playlist_id}"
        )
    logger.debug(f"set_playlist_description: id={playlist_id}")
    return _update_playlist_metadata(
        client, playlist_id,
        title=info['title'],
        description=description,
        is_private=info['is_private'],
        is_collaborative=None,  # omit from payload; server preserves current value
        logger=logger,
    )
