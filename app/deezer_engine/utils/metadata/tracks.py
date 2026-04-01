# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Track metadata helpers."""

import json
from utils.db.connection import get_connection
from utils.metadata.albums import flatten_albums
from utils.metadata.safeguards import blocklist_albums_for_unavailable_tracks


def insert_shallow_track_stubs(track_list, logger=None):
    """Insert shallow paginated track payloads for shallow metadata collection."""
    if logger:
        logger.debug(f"Received {len(track_list) if track_list else 0} tracks for shallow insert")

    if not track_list:
        return

    artist_rows = []
    seen_artist_ids = set()
    album_rows = []
    seen_album_ids = set()

    for track in track_list:
        artist_id = track.get("artist_id")
        if artist_id is not None and artist_id not in seen_artist_ids:
            artist_rows.append((artist_id, track.get("artist_name")))
            seen_artist_ids.add(artist_id)

        album_id = track.get("album_id")
        if album_id is not None and album_id not in seen_album_ids:
            album_rows.append((album_id, track.get("album_name"), artist_id, track.get("artist_name")))
            seen_album_ids.add(album_id)

    track_columns = [
        "id",
        "readable",
        "title",
        "title_short",
        "title_version",
        "unseen",
        "isrc",
        "link",
        "share",
        "duration",
        "track_position",
        "disk_number",
        "rank",
        "release_date",
        "explicit_lyrics",
        "explicit_content_lyrics",
        "explicit_content_cover",
        "preview",
        "available_countries",
        "alternative",
        "contributors",
        "md5_image",
        "artist_id",
        "artist_name",
        "album_id",
        "album_name",
    ]
    track_rows = [tuple(track.get(column) for column in track_columns) for track in track_list]

    update_assignments = ",\n        ".join(
        [f"{column} = COALESCE(excluded.{column}, tracks.{column})" for column in track_columns if column != "id"]
    )
    track_placeholders = ", ".join(["?"] * len(track_columns))
    track_insert_query = f"""
    INSERT INTO tracks ({", ".join(track_columns)})
    VALUES ({track_placeholders})
    ON CONFLICT(id) DO UPDATE SET
        {update_assignments}
    WHERE COALESCE(tracks.date_cached, '') = '';
    """

    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()

            if artist_rows:
                cursor.executemany(
                    """
                    INSERT INTO artists (id, name)
                    VALUES (?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = COALESCE(artists.name, excluded.name);
                    """,
                    artist_rows,
                )

            if album_rows:
                cursor.executemany(
                    """
                    INSERT INTO albums (id, title, artist_id, artist_name)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = COALESCE(albums.title, excluded.title),
                        artist_id = COALESCE(albums.artist_id, excluded.artist_id),
                        artist_name = COALESCE(albums.artist_name, excluded.artist_name);
                    """,
                    album_rows,
                )

            cursor.executemany(track_insert_query, track_rows)
            conn.commit()

            if logger:
                logger.debug(
                    f"Shallow track insert complete: tracks={len(track_rows)}, albums={len(album_rows)}, artists={len(artist_rows)}"
                )

        from utils.db.cache import mark_fully_populated_tracks_as_cached

        mark_fully_populated_tracks_as_cached(logger=logger)
    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Shallow track insert failed: {exc}")
        raise



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


def update_tracks_partial_batch(track_list, logger=None):
    """
    Update multiple tracks using keys present in the payload.
    """
    if not track_list:
        return

    sample_track = track_list[0]
    update_keys = [k for k in sample_track.keys() if k != "id"]

    if logger:
        logger.debug(
            f"Refreshing partial track stats for track_count={len(track_list)} with update_fields={update_keys}."
        )

    set_clause = ", ".join([f"{k} = ?" for k in update_keys])
    query = f"UPDATE tracks SET {set_clause} WHERE id = ?;"

    data_tuples = []
    for track in track_list:
        row_values = [track.get(k) for k in update_keys]
        row_values.append(track.get("id"))
        data_tuples.append(tuple(row_values))

    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data_tuples)
            conn.commit()
            if logger:
                logger.info(f"Refreshed stats (rank/unseen) for {len(track_list)} tracks.")

        try:
            blocklist_albums_for_unavailable_tracks(logger)
        except Exception as safeguard_error:
            if logger:
                logger.warning(
                    f"Safeguard blocklist pass failed after partial track update: {safeguard_error}"
                )
    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Partial batch update failed: {exc}")
        raise


def update_track_metadata(track_list, logger=None):
    """
    Update tracks with full metadata payload fetched from Deezer.
    """
    if logger:
        logger.debug(f"Received {len(track_list) if track_list else 0} tracks for metadata update")

    if not track_list:
        if logger:
            logger.debug("Track list is empty, returning early.")
        return

    query = """
    UPDATE tracks SET
        readable = ?, title = ?, title_short = ?, title_version = ?, unseen = ?,
        isrc = ?, link = ?, share = ?, duration = ?, track_position = ?,
        disk_number = ?, rank = ?, release_date = ?, explicit_lyrics = ?,
        explicit_content_lyrics = ?, explicit_content_cover = ?, preview = ?,
        bpm = ?, gain = ?, available_countries = ?, contributors = ?,
        md5_image = ?, track_token = ?, artist_id = ?, album_id = ?, date_cached = ?
    WHERE id = ?;
    """

    data_tuples = [
        (
            track.get("readable"),
            track.get("title"),
            track.get("title_short"),
            track.get("title_version"),
            track.get("unseen"),
            track.get("isrc"),
            track.get("link"),
            track.get("share"),
            track.get("duration"),
            track.get("track_position"),
            track.get("disk_number"),
            track.get("rank"),
            track.get("release_date"),
            track.get("explicit_lyrics"),
            track.get("explicit_content_lyrics"),
            track.get("explicit_content_cover"),
            track.get("preview"),
            track.get("bpm"),
            track.get("gain"),
            track.get("available_countries"),
            track.get("contributors"),
            track.get("md5_image"),
            track.get("track_token"),
            track.get("artist_id"),
            track.get("album_id"),
            track.get("date_cached"),
            track.get("id"),
        )
        for track in track_list
    ]

    if logger and data_tuples:
        sample_track = track_list[0]
        logger.debug(
            f"Sample track data structure: id={sample_track.get('id')} "
            f"(type: {type(sample_track.get('id')).__name__}), title={sample_track.get('title')}, "
            f"date_cached={sample_track.get('date_cached')}"
        )
        logger.debug(
            f"Sample data tuple (last 3 fields): album_id={data_tuples[0][-3]}, "
            f"date_cached={data_tuples[0][-2]}, id={data_tuples[0][-1]}"
        )

    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()

            artist_ids = sorted({track.get("artist_id") for track in track_list if track.get("artist_id") is not None})
            if artist_ids:
                cursor.executemany(
                    "INSERT OR IGNORE INTO artists (id) VALUES (?)",
                    [(artist_id,) for artist_id in artist_ids],
                )
                if logger:
                    logger.debug(f"Upserted {len(artist_ids)} artist stubs from track metadata payload.")

            album_ids = sorted({track.get("album_id") for track in track_list if track.get("album_id") is not None})
            if album_ids:
                cursor.executemany(
                    "INSERT OR IGNORE INTO albums (id) VALUES (?)",
                    [(album_id,) for album_id in album_ids],
                )
                if logger:
                    logger.debug(f"Upserted {len(album_ids)} album stubs from track metadata payload.")

            if logger:
                logger.debug(f"Executing UPDATE query for {len(data_tuples)} tracks...")
            cursor.executemany(query, data_tuples)
            rows_affected = cursor.rowcount
            if logger:
                logger.debug(f"UPDATE query affected {rows_affected} rows.")
            conn.commit()
            if logger:
                logger.debug(f"Metadata enrichment complete for {len(track_list)} tracks.")

        try:
            blocklist_albums_for_unavailable_tracks(logger)
        except Exception as safeguard_error:
            if logger:
                logger.warning(
                    f"Safeguard blocklist pass failed after full track metadata update: {safeguard_error}"
                )
    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Metadata update failed: {exc}")
            logger.exception("Stack trace for track metadata update error:")
        raise

