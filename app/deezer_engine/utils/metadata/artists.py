# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Artist metadata helpers."""

import json

from utils.db.cache import mark_fully_populated_artists_as_cached
from utils.db.connection import get_connection


def insert_shallow_artist_stubs(artist_list, logger=None, skip_fully_populated=False):
    """Insert shallow artist payloads for shallow metadata-collection."""
    if logger:
        logger.debug(
            f"Received {len(artist_list) if artist_list else 0} artists for shallow insert "
            f"(skip_fully_populated={skip_fully_populated})."
        )

    if not artist_list:
        return

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

            if not skip_fully_populated:
                if logger:
                    logger.debug("Marking fully populated artists as cached.")
                mark_fully_populated_artists_as_cached(logger=logger, conn=conn)
            elif logger:
                logger.debug("Skipping artist cache finalization (deferred).")

            conn.commit()
            if logger:
                logger.debug(f"Shallow artist insert complete: artists={len(artists_by_id)}")
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


def _dedupe_entities(entities, coerce_fn, logger=None, entity_label="entities"):
    """Merge duplicate entities by id, combining fields from all occurrences."""
    if logger:
        logger.debug(f"_dedupe_entities: received {len(entities)} {entity_label}.")

    by_id = {}
    no_id = []

    for entity in entities:
        payload = coerce_fn(entity)
        entity_id = payload.get("id")
        if entity_id is None:
            no_id.append(payload)
            continue
        existing = by_id.get(entity_id, {})
        by_id[entity_id] = {**existing, **{k: v for k, v in payload.items() if v is not None}}

    deduped = list(by_id.values()) + no_id

    if logger:
        logger.debug(
            f"_dedupe_entities: {len(entities)} in, {len(deduped)} out "
            f"({len(entities) - len(deduped)} merged)."
        )
    return deduped


def flatten_artists(artistlist, logger, skip_fully_populated=False):
    """Flatten artist payloads into dictionaries suitable for shallow database writes."""
    if artistlist is None:
        logger.debug("Flattening 0 artists.")
        return []

    artists = artistlist if isinstance(artistlist, list) else [artistlist]
    artists = _dedupe_entities(artists, _coerce_artist, logger=logger, entity_label="artists")
    logger.debug(f"Flattening {len(artists)} artists (skip_fully_populated={skip_fully_populated}).")

    flattened_artists = []
    for artist in artists:
        try:
            flattened = dict(artist) if isinstance(artist, dict) else _coerce_artist(artist)
            flattened.pop("playlist", None)
            flattened.pop("album", None)
            flattened_artists.append(
                {key: _normalize_field(value) for key, value in flattened.items()}
            )
        except Exception as exc:
            logger.error(f"Error flattening artist with data {artist}: {exc}")
            raise

    logger.debug(
        f"Flattened artists. Start count: {len(artists)}, end count: {len(flattened_artists)}."
    )

    insert_shallow_artist_stubs(
        flattened_artists,
        logger,
        skip_fully_populated=skip_fully_populated,
    )
    return flattened_artists
