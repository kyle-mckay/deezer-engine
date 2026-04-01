# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metadata sync helpers for missing album/artist references."""

from utils.db.connection import get_connection


def get_unique_album_ids_from_tracks(logger=None):
    """Return all unique non-null album IDs referenced by tracks."""
    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT album_id
                FROM tracks
                WHERE album_id IS NOT NULL
                ORDER BY album_id
                """
            )
            album_ids = {row[0] for row in cursor.fetchall()}

            if logger:
                logger.debug(f"DB: Found {len(album_ids)} unique album IDs in tracks table.")

            return album_ids

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to get unique album IDs - {exc}")
        return set()


def get_missing_album_ids(logger=None):
    """Return album IDs referenced in tracks but missing from albums table."""
    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT album_id
                FROM tracks
                WHERE album_id IS NOT NULL
                """
            )
            track_album_ids = {row[0] for row in cursor.fetchall()}

            cursor = conn.execute("SELECT DISTINCT id FROM albums")
            existing_album_ids = {row[0] for row in cursor.fetchall()}

            missing_album_ids = track_album_ids - existing_album_ids

            if logger:
                logger.debug(
                    f"DB: {len(track_album_ids)} album IDs in tracks, {len(existing_album_ids)} in albums table."
                )
                logger.debug(f"DB: {len(missing_album_ids)} missing album IDs to be synced.")

            return missing_album_ids

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to get missing album IDs - {exc}")
        return set()


def get_missing_artist_ids(logger=None):
    """Return artist IDs referenced by tracks/albums but missing from artists table."""
    try:
        with get_connection(logger) as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT artist_id
                FROM tracks
                WHERE artist_id IS NOT NULL
                UNION
                SELECT DISTINCT artist_id
                FROM albums
                WHERE artist_id IS NOT NULL
                """
            )
            referenced_artist_ids = {row[0] for row in cursor.fetchall()}

            cursor = conn.execute("SELECT id FROM artists")
            existing_artist_ids = {row[0] for row in cursor.fetchall()}

            missing_artist_ids = referenced_artist_ids - existing_artist_ids

            if logger:
                logger.debug(
                    f"DB: {len(referenced_artist_ids)} referenced artist IDs, "
                    f"{len(existing_artist_ids)} artists in table, "
                    f"{len(missing_artist_ids)} missing artist IDs to be synced."
                )

            return missing_artist_ids

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Failed to get missing artist IDs - {exc}")
        return set()


def sync_missing_albums_to_table(logger=None):
    """Insert stub album rows for album IDs referenced by tracks."""
    try:
        missing_ids = get_missing_album_ids(logger)

        if not missing_ids:
            if logger:
                logger.debug("DB: All track albums already exist in albums table.")
            return

        with get_connection(logger) as conn:
            cursor = conn.cursor()
            cursor.executemany("INSERT INTO albums (id) VALUES (?)", [(album_id,) for album_id in missing_ids])
            conn.commit()

            if logger:
                logger.debug(
                    f"Album Sync: Inserted {len(missing_ids)} stub album records for later enrichment."
                )

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Album sync to table failed - {exc}")
        raise


def sync_missing_artists_to_table(logger=None):
    """Insert stub artist rows for artist IDs referenced by tracks/albums."""
    try:
        missing_ids = get_missing_artist_ids(logger)

        if not missing_ids:
            if logger:
                logger.debug("DB: All referenced artists already exist in artists table.")
            return

        with get_connection(logger) as conn:
            cursor = conn.cursor()
            cursor.executemany("INSERT INTO artists (id) VALUES (?)", [(artist_id,) for artist_id in missing_ids])
            conn.commit()

            if logger:
                logger.debug(
                    f"Artist Sync: Inserted {len(missing_ids)} stub artist records for later enrichment."
                )

    except Exception as exc:
        if logger:
            logger.error(f"DB Error: Artist sync to table failed - {exc}")
        raise
