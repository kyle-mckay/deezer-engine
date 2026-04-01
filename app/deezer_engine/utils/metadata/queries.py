# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metadata query helpers for unprocessed/expired/missing entities."""

from utils.config import get_global_value
from utils.db.blocklist import _blocklist_where_clause
from utils.db.connection import get_connection


def get_unprocessed_track_ids(logger=None, include_blocklisted=False):
    """Return track IDs that still require metadata enrichment."""
    if logger:
        logger.debug(f"Querying unprocessed track IDs (include_blocklisted={include_blocklisted}).")

    track_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id
    FROM tracks
    WHERE (date_cached IS NULL OR date_cached = '')
      AND {track_filter};
    """

    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            tracks_payload = [{"id": row["id"]} for row in rows]

            if logger and tracks_payload:
                logger.debug(f"Database: {len(tracks_payload)} tracks found requiring enrichment.")

            return tracks_payload

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to check for unprocessed tracks: {exc}")
        return []


def get_unprocessed_album_ids(logger=None, include_blocklisted=False):
    """Return album IDs requiring metadata enrichment or genre mapping."""
    if logger:
        logger.debug(f"Querying unprocessed album IDs (include_blocklisted={include_blocklisted}).")

    album_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id
    FROM albums
    WHERE (
            (date_cached IS NULL OR date_cached = '')
            OR COALESCE(genre_mapped, 0) = 0
    )
      AND {album_filter}
    """

    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            album_ids = [row[0] for row in rows]

            if logger and album_ids:
                logger.debug(f"Database: {len(album_ids)} albums found requiring enrichment or genre mapping.")

            return album_ids

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to check for unprocessed albums: {exc}")
        return []


def get_albums_missing_genres(logger=None, include_blocklisted=False):
    """Return album IDs where genre mapping has not completed."""
    if logger:
        logger.debug(f"Querying albums missing genre mappings (include_blocklisted={include_blocklisted}).")

    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()
            album_filter = _blocklist_where_clause(include_blocklisted)
            query = f"""
            SELECT id
            FROM albums
            WHERE COALESCE(genre_mapped, 0) = 0
              AND {album_filter}
            ORDER BY id
            """

            cursor.execute(query)
            albums = [row[0] for row in cursor.fetchall()]

            if logger:
                logger.debug(f"Found {len(albums)} albums without genre mappings.")

            return albums

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to retrieve albums missing genres: {exc}")
        return []


def get_tracks_missing_genres(logger=None, include_blocklisted=False):
    """Return track IDs where genre mapping has not completed."""
    if logger:
        logger.debug(f"Querying tracks missing genre mappings (include_blocklisted={include_blocklisted}).")

    try:
        with get_connection(logger) as conn:
            cursor = conn.cursor()
            track_filter = _blocklist_where_clause(include_blocklisted)
            query = f"""
            SELECT id
            FROM tracks
            WHERE COALESCE(genre_mapped, 0) = 0
              AND {track_filter}
            ORDER BY id
            """

            cursor.execute(query)
            tracks = [row[0] for row in cursor.fetchall()]

            if logger:
                logger.debug(f"Found {len(tracks)} tracks without genre mappings.")

            return tracks

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to retrieve tracks missing genres: {exc}")
        return []


def get_expired_track_ids(logger=None, include_blocklisted=False):
    """Return track IDs with stale date_cached according to track_stats_refresh."""
    track_stats_refresh = get_global_value("track_stats_refresh", default=90)
    if logger:
        logger.debug(
            f"Querying expired track stats with refresh_days={track_stats_refresh} "
            f"(include_blocklisted={include_blocklisted})."
        )

    track_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id
    FROM tracks
    WHERE date_cached < datetime('now', '-{track_stats_refresh} days')
      AND {track_filter};
    """

    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(query)
            expired_ids = [row[0] for row in cursor.fetchall()]

            if logger and expired_ids:
                logger.debug(f"DB: Detected {len(expired_ids)} tracks older than {track_stats_refresh} days.")

            return expired_ids

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Expiry check failed: {exc}")
        return []


def get_expired_album_ids(logger=None, include_blocklisted=False):
    """Return album IDs with stale date_cached according to album_stats_refresh."""
    album_stats_refresh = get_global_value("album_stats_refresh", default=90)
    if logger:
        logger.debug(
            f"Querying expired album stats with refresh_days={album_stats_refresh} "
            f"(include_blocklisted={include_blocklisted})."
        )

    album_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id
    FROM albums
    WHERE date_cached < datetime('now', '-{album_stats_refresh} days')
      AND {album_filter};
    """

    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(query)
            expired_ids = [row[0] for row in cursor.fetchall()]

            if logger and expired_ids:
                logger.debug(
                    f"DB: Detected {len(expired_ids)} albums older than {album_stats_refresh} days or missing cache date."
                )

            return expired_ids

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Album expiry check failed: {exc}")
        return []
