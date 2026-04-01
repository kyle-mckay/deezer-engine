# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Artist metadata helpers."""

import json


def insert_shallow_artist_stubs(artist_list, logger=None):
    """Insert shallow artist payloads for shallow metadata-collection."""
    if logger:
        logger.debug(f"Received {len(artist_list) if artist_list else 0} artists for shallow insert")

    if not artist_list:
        return

    from utils.db.connection import get_connection
    from utils.db.cache import mark_fully_populated_artists_as_cached

    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(artists)")
            artist_table_columns = [row[1] for row in cursor.fetchall()]

            artists_by_id = {}
            for artist in artist_list:
                artist_payload = _coerce_artist(artist)
                artist_id = artist_payload.get('id')
                if artist_id is None:
                    continue
                existing_artist = artists_by_id.get(artist_id, {})
                merged_artist = {**existing_artist, **artist_payload}
                artists_by_id[artist_id] = merged_artist

            artist_usable_columns = [
                column for column in artist_table_columns
                if column != 'date_cached'
                if any(column in payload for payload in artists_by_id.values())
            ]
            if 'id' in artist_usable_columns:
                artist_usable_columns = ['id'] + [c for c in artist_usable_columns if c != 'id']

            if artist_usable_columns:
                artist_placeholders = ", ".join(["?"] * len(artist_usable_columns))
                artist_updates = ",\n                        ".join(
                    [
                        f"{column} = COALESCE(artists.{column}, excluded.{column})"
                        for column in artist_usable_columns
                        if column != 'id'
                    ]
                )
                artist_query = f"""
                INSERT INTO artists ({", ".join(artist_usable_columns)})
                VALUES ({artist_placeholders})
                ON CONFLICT(id) DO UPDATE SET
                    {artist_updates}
                WHERE COALESCE(artists.date_cached, '') = '';
                """
                artist_rows = [
                    tuple(_normalize_field(payload.get(column)) for column in artist_usable_columns)
                    for payload in artists_by_id.values()
                ]
                cursor.executemany(artist_query, artist_rows)

            conn.commit()
            if logger:
                logger.debug(f"Shallow artist insert complete: artists={len(artists_by_id)}")
            mark_fully_populated_artists_as_cached(logger)
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Shallow artist insert failed: {e}")
        raise


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