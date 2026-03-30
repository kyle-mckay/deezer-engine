# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Track metadata helpers."""

import json
from utils.metadata.albums import flatten_albums
from utils.db_manager import insert_shallow_track_stubs



TRACK_HEADERS_AVAILABLE_IN_ALL_FETCH_TYPES = frozenset({
    'id',
    'readable',
    'title',
    'link',
    'duration',
    'rank',
    'explicit_lyrics',
    'explicit_content_lyrics',
    'explicit_content_cover',
    'md5_image',
    'artist_id',
    'artist_name',
    'album_id',
    'album_name',
})


def track_header_available(header_name):
    """Return True when a track header exists in every supported fetch type."""
    if not isinstance(header_name, str):
        return False

    return header_name.strip() in TRACK_HEADERS_AVAILABLE_IN_ALL_FETCH_TYPES

def _normalize_field(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def _coerce_track(track):
    if hasattr(track, "as_dict"):
        return track.as_dict()
    if isinstance(track, dict):
        return dict(track)
    return dict(track)


def _dedupe_tracks(tracklist):
    deduped_tracks = []
    seen_track_ids = set()

    for track in tracklist:
        track_payload = _coerce_track(track)
        track_id = track_payload.get("id")
        if track_id is None:
            deduped_tracks.append(track_payload)
            continue
        if track_id in seen_track_ids:
            continue
        seen_track_ids.add(track_id)
        deduped_tracks.append(track_payload)

    return deduped_tracks


def flatten_tracks(tracklist, logger):
    """Flatten paginated track payloads into shallow track dictionaries."""
    if tracklist is None:
        logger.debug("Flattening 0 tracks.")
        return []

    tracks = tracklist if isinstance(tracklist, list) else [tracklist]
    tracks = _dedupe_tracks(tracks)
    logger.debug(f"Flattening {len(tracks)} tracks.")

    flattened_tracks = []
    albums = []
    for track in tracks:
        try:
            flattened = dict(track) if isinstance(track, dict) else _coerce_track(track)
            flattened.pop("playlist", None)

            album = flattened.pop("album", None)
            if isinstance(album, dict):
                albums.append(album)
                flattened["album_id"] = flattened.get("album_id", album.get("id"))
                flattened["album_name"] = flattened.get("album_name", album.get("title"))

            artist = flattened.pop("artist", None)
            if isinstance(artist, dict):
                flattened["artist_id"] = flattened.get("artist_id", artist.get("id"))
                flattened["artist_name"] = flattened.get("artist_name", artist.get("name"))

            alternative = flattened.get("alternative")
            if isinstance(alternative, (list, dict)):
                flattened["alternative"] = json.dumps(alternative)

            contributors = flattened.get("contributors")
            if isinstance(contributors, (list, dict)):
                flattened["contributors"] = json.dumps(contributors)

            available_countries = flattened.get("available_countries")
            if isinstance(available_countries, (list, dict)):
                flattened["available_countries"] = json.dumps(available_countries)

            flattened_tracks.append(
                {key: _normalize_field(value) for key, value in flattened.items() if key != "date_cached"}
            )
        except Exception as exc:
            logger.error(f"Error flattening track with data {track}: {exc}")
            raise

    logger.debug(f"Flattened tracks. Start count: {len(tracks)}, end count: {len(flattened_tracks)}.")

    flatten_albums(albums, logger)
    insert_shallow_track_stubs(flattened_tracks, logger)
    return flattened_tracks

