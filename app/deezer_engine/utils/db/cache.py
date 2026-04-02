# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Cache finalization helpers - mark DB rows as cached when fully populated."""

from datetime import datetime
from utils.db.connection import get_connection


def _mark_rows_cached_when_fields_populated(table_name, required_fields, logger=None, cached_at=None, conn=None):
    """Set date_cached for rows that have all required API fields populated."""
    if not required_fields:
        return 0

    marker = cached_at if cached_at is not None else datetime.now().isoformat()
    where_all_fields_present = " AND ".join(
        [f"COALESCE(CAST({field} AS TEXT), '') <> ''" for field in required_fields]
    )

    query = f"""
    UPDATE {table_name}
    SET date_cached = ?
    WHERE COALESCE(date_cached, '') = ''
      AND {where_all_fields_present};
    """

    if logger:
        logger.debug(
            f"Cache finalization for '{table_name}': using {'shared' if conn is not None else 'standalone'} connection."
        )

    try:
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute(query, (marker,))
            return cursor.rowcount

        with get_connection(logger) as managed_conn:
            cursor = managed_conn.cursor()
            cursor.execute(query, (marker,))
            rows_affected = cursor.rowcount
            managed_conn.commit()
            return rows_affected
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed cache finalization for table '{table_name}': {e}")
        raise


def mark_fully_populated_tracks_as_cached(logger=None, cached_at=None, conn=None):
    """Mark tracks as cached when all track API fields are populated."""
    required_track_fields = [
        'readable',
        'title',
        'title_short',
        'title_version',
        'unseen',
        'isrc',
        'link',
        'share',
        'duration',
        'track_position',
        'disk_number',
        'rank',
        'release_date',
        'explicit_lyrics',
        'explicit_content_lyrics',
        'explicit_content_cover',
        'preview',
        'bpm',
        'gain',
        'available_countries',
        'contributors',
        'md5_image',
        'track_token',
        'artist_id',
        'album_id',
    ]
    rows = _mark_rows_cached_when_fields_populated(
        'tracks',
        required_track_fields,
        logger=logger,
        cached_at=cached_at,
        conn=conn,
    )
    if logger and rows > 0:
        logger.debug(f"Cache finalization: marked {rows} fully populated tracks as cached.")
    return rows


def mark_fully_populated_albums_as_cached(logger=None, cached_at=None, conn=None):
    """Mark albums as cached when all album API fields are populated."""
    required_album_fields = [
        'title',
        'upc',
        'link',
        'share',
        'cover',
        'cover_small',
        'cover_medium',
        'cover_big',
        'cover_xl',
        'md5_image',
        'label',
        'nb_tracks',
        'duration',
        'fans',
        'release_date',
        'record_type',
        'available',
        'tracklist',
        'explicit_lyrics',
        'explicit_content_lyrics',
        'explicit_content_cover',
        'genres',
        'contributors',
        'artist_id',
        'artist_name',
    ]
    rows = _mark_rows_cached_when_fields_populated(
        'albums',
        required_album_fields,
        logger=logger,
        cached_at=cached_at,
        conn=conn,
    )
    if logger and rows > 0:
        logger.debug(f"Cache finalization: marked {rows} fully populated albums as cached.")
    return rows


def mark_fully_populated_artists_as_cached(logger=None, cached_at=None, conn=None):
    """Mark artists as cached when all artist API fields are populated."""
    required_artist_fields = [
        'name',
        'link',
        'share',
        'picture',
        'picture_small',
        'picture_medium',
        'picture_big',
        'picture_xl',
        'nb_album',
        'nb_fan',
        'radio',
        'tracklist',
    ]
    rows = _mark_rows_cached_when_fields_populated(
        'artists',
        required_artist_fields,
        logger=logger,
        cached_at=cached_at,
        conn=conn,
    )
    if logger and rows > 0:
        logger.debug(f"Cache finalization: marked {rows} fully populated artists as cached.")
    return rows


def mass_mark_fully_populated_as_cached(logger=None):
    """Mark artists, albums, and tracks as cached in a single DB transaction."""
    if logger:
        logger.debug("mass_mark_fully_populated_as_cached: starting batch cache finalization (artists, albums, tracks).")
    try:
        with get_connection(logger) as conn:
            mark_fully_populated_artists_as_cached(logger=logger, conn=conn)
            mark_fully_populated_albums_as_cached(logger=logger, conn=conn)
            mark_fully_populated_tracks_as_cached(logger=logger, conn=conn)
            conn.commit()
    except Exception as e:
        if logger:
            logger.error(f"DB Error: mass_mark_fully_populated_as_cached failed: {e}")
        raise