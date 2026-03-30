# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Artist metadata helpers."""

import json

from utils.db_manager import insert_shallow_artist_stubs


def _normalize_field(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return value


def _coerce_artist(artist):
    if hasattr(artist, "as_dict"):
        return artist.as_dict()
    if isinstance(artist, dict):
        return dict(artist)
    return dict(artist)


def _dedupe_artists(artistlist):
    deduped_artists = []
    seen_artist_ids = set()

    for artist in artistlist:
        artist_payload = _coerce_artist(artist)
        artist_id = artist_payload.get("id")
        if artist_id is None:
            deduped_artists.append(artist_payload)
            continue
        if artist_id in seen_artist_ids:
            continue
        seen_artist_ids.add(artist_id)
        deduped_artists.append(artist_payload)

    return deduped_artists


def flatten_artists(artistlist, logger):
    """Flatten artist payloads into dictionaries suitable for shallow database writes."""
    if artistlist is None:
        logger.debug("Flattening 0 artists.")
        return []

    artists = artistlist if isinstance(artistlist, list) else [artistlist]
    artists = _dedupe_artists(artists)
    logger.debug(f"Flattening {len(artists)} artists.")

    flattened_artists = []
    for artist in artists:
        try:
            flattened = dict(artist) if isinstance(artist, dict) else _coerce_artist(artist)
            flattened_artists.append(
                {key: _normalize_field(value) for key, value in flattened.items()}
            )
        except Exception as exc:
            logger.error(f"Error flattening artist with data {artist}: {exc}")
            raise

    logger.debug(
        f"Flattened artists. Start count: {len(artists)}, end count: {len(flattened_artists)}."
    )

    insert_shallow_artist_stubs(flattened_artists, logger)
    return flattened_artists