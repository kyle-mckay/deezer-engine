# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from utils.config import get_global_value
from utils.infrastructure.signals import shutdown_event

from .connection import get_connection

def _blocklist_where_clause(include_blocklisted):
    """Returns SQL predicate for including or excluding blocklisted entities."""
    return "1=1" if include_blocklisted else "COALESCE(blocklisted, 0) = 0"

def release_expired_blocklisted_entities(logger=None):
    """
    Startup reconciliation: unblocks tracks/albums once blocklist_expiry_days has elapsed
    since the blocklist event timestamp.
    """
    configured_days = get_global_value("blocklist_expiry_days", default=7)
    try:
        expiry_days = int(configured_days)
        if expiry_days < 0:
            expiry_days = 0
    except (TypeError, ValueError):
        expiry_days = 7

    cutoff_iso = (datetime.now() - timedelta(days=expiry_days)).isoformat()
    select_query = """
    SELECT entity_type, entity_id
    FROM blocklist
    WHERE COALESCE(NULLIF(blocklist_applied_at, ''), NULLIF(last_failed_at, '')) IS NOT NULL
      AND COALESCE(NULLIF(blocklist_applied_at, ''), NULLIF(last_failed_at, '')) <= ?
    """

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(select_query, (cutoff_iso,))
            expired = cursor.fetchall()

            if not expired:
                if logger:
                    logger.debug("No expired blocklist entries found.")
                return

            track_ids = [row[1] for row in expired if row[0] == 'track']
            album_ids = [row[1] for row in expired if row[0] == 'album']

            tracks_unblocked = 0
            albums_unblocked = 0

            if track_ids:
                placeholders = ','.join('?' * len(track_ids))
                cursor.execute(
                    f"""
                    UPDATE tracks
                    SET blocklisted = 0,
                        blacklist_id = NULL
                    WHERE id IN ({placeholders})
                      AND NOT EXISTS (
                          SELECT 1
                          FROM blocklist ab
                          WHERE ab.entity_type = 'album'
                            AND ab.entity_id = tracks.album_id
                            AND COALESCE(NULLIF(ab.blocklist_applied_at, ''), NULLIF(ab.last_failed_at, '')) IS NOT NULL
                      )
                    """,
                    track_ids
                )
                tracks_unblocked = cursor.rowcount
                cursor.execute(
                    f"UPDATE blocklist SET blocklist_applied_at = NULL WHERE entity_type = 'track' AND entity_id IN ({placeholders})",
                    track_ids
                )

            if album_ids:
                placeholders = ','.join('?' * len(album_ids))
                cursor.execute(
                    f"UPDATE albums SET blocklisted = 0, blacklist_id = NULL WHERE id IN ({placeholders})",
                    album_ids
                )
                albums_unblocked = cursor.rowcount
                cursor.execute(
                    f"UPDATE blocklist SET blocklist_applied_at = NULL WHERE entity_type = 'album' AND entity_id IN ({placeholders})",
                    album_ids
                )

                # Album release cascades to tracks, but tracks with their own active
                # track blocklist remain blocked and are reattached to their own blocklist row.
                cursor.execute(
                    f"""
                    UPDATE tracks
                    SET blocklisted = 1,
                        blacklist_id = (
                            SELECT tb.id
                            FROM blocklist tb
                            WHERE tb.entity_type = 'track'
                              AND tb.entity_id = tracks.id
                            LIMIT 1
                        )
                    WHERE album_id IN ({placeholders})
                      AND EXISTS (
                          SELECT 1
                          FROM blocklist tb
                          WHERE tb.entity_type = 'track'
                            AND tb.entity_id = tracks.id
                            AND COALESCE(NULLIF(tb.blocklist_applied_at, ''), NULLIF(tb.last_failed_at, '')) IS NOT NULL
                      )
                    """,
                    album_ids
                )

                cursor.execute(
                    f"""
                    UPDATE tracks
                    SET blocklisted = 0,
                        blacklist_id = NULL
                    WHERE album_id IN ({placeholders})
                      AND NOT EXISTS (
                          SELECT 1
                          FROM blocklist tb
                          WHERE tb.entity_type = 'track'
                            AND tb.entity_id = tracks.id
                            AND COALESCE(NULLIF(tb.blocklist_applied_at, ''), NULLIF(tb.last_failed_at, '')) IS NOT NULL
                      )
                    """,
                    album_ids
                )

            conn.commit()

            if logger:
                logger.debug(
                    f"Reopened blocklist entries using blocklist_expiry_days={expiry_days}: tracks={tracks_unblocked}, albums={albums_unblocked}"
                )
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to release expired blocklisted entities: {e}")
        raise

def _mark_entity_metadata_fetch_failed(entity_type, entity_table, entity_id, error_code, logger=None):
    """Shared helper to upsert blocklist failure metadata and attach blacklist_id to an entity row."""
    if entity_id is None:
        if logger:
            logger.debug(f"{entity_type.capitalize()} failure update skipped: id is None.")
        return

    if entity_table not in {"tracks", "albums"}:
        raise ValueError(f"Unsupported entity table: {entity_table}")

    failed_at = datetime.now().isoformat()
    exists_query = f"SELECT blacklist_id, date_cached FROM {entity_table} WHERE id = ? LIMIT 1"
    insert_entity_stub_query = f"INSERT OR IGNORE INTO {entity_table} (id) VALUES (?)"
    select_by_id_query = """
    SELECT id, entity_type, entity_id, total_errors, streak_errors, last_failed_at
    FROM blocklist
    WHERE id = ?
    LIMIT 1
    """
    select_by_entity_query = """
    SELECT id, entity_type, entity_id, total_errors, streak_errors, last_failed_at
    FROM blocklist
    WHERE entity_type = ? AND entity_id = ?
    LIMIT 1
    """
    update_blocklist_query = """
    UPDATE blocklist
    SET total_errors = ?,
        streak_errors = ?,
        last_error_code = ?,
        last_failed_at = ?,
        blocklist_applied_at = ?
    WHERE id = ?
    """
    insert_blocklist_query = """
    INSERT INTO blocklist (
        entity_type,
        entity_id,
        total_errors,
        streak_errors,
        last_error_code,
        last_failed_at,
        blocklist_applied_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    attach_query = f"UPDATE {entity_table} SET blacklist_id = ?, blocklisted = 1 WHERE id = ?"

    normalized_error = str(error_code) if error_code is not None else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(exists_query, (entity_id,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute(insert_entity_stub_query, (entity_id,))
            cursor.execute(exists_query, (entity_id,))
            row = cursor.fetchone()
            if logger:
                logger.debug(f"Created {entity_type} stub for missing id={entity_id} to attach blocklist reference.")

        if row is None:
            if logger:
                logger.debug(f"{entity_type.capitalize()} failure update skipped: unable to resolve {entity_type} {entity_id} row.")
            return None

        current_blacklist_id = row[0]
        entity_date_cached = row[1]
        blocklist_row = None
        if current_blacklist_id is not None:
            cursor.execute(select_by_id_query, (current_blacklist_id,))
            blocklist_row = cursor.fetchone()

            # Defensive check: only trust attached blacklist_id if it belongs to this entity.
            if blocklist_row is not None:
                attached_entity_type = blocklist_row[1]
                attached_entity_id = blocklist_row[2]
                if attached_entity_type != entity_type or attached_entity_id != entity_id:
                    if logger:
                        logger.debug(
                            f"Ignoring mismatched blacklist_id={current_blacklist_id} for {entity_type} {entity_id}; "
                            f"attached to {attached_entity_type} {attached_entity_id}."
                        )
                    blocklist_row = None

        if blocklist_row is None:
            cursor.execute(select_by_entity_query, (entity_type, entity_id))
            blocklist_row = cursor.fetchone()

        if blocklist_row is not None:
            blocklist_id = blocklist_row[0]
            current_total_errors = int(blocklist_row[3] or 0)
            current_streak_errors = int(blocklist_row[4] or 0)
            previous_last_failure = blocklist_row[5]
            next_total_errors = current_total_errors + 1

            # Reset streak only when metadata was successfully cached after the last failure.
            recovered_since_last_failure = False
            if entity_date_cached and previous_last_failure:
                try:
                    recovered_since_last_failure = datetime.fromisoformat(entity_date_cached) > datetime.fromisoformat(previous_last_failure)
                except ValueError:
                    # Fallback for non-ISO values: lexical compare still works for canonical ISO strings.
                    recovered_since_last_failure = str(entity_date_cached) > str(previous_last_failure)

            next_streak_errors = 1 if recovered_since_last_failure else (current_streak_errors + 1)
            cursor.execute(
                update_blocklist_query,
                (
                    next_total_errors,
                    next_streak_errors,
                    normalized_error,
                    failed_at,
                    failed_at,
                    blocklist_id,
                )
            )
            if logger and recovered_since_last_failure:
                logger.debug(
                    f"Resetting {entity_type} {entity_id} streak_errors to 1: "
                    f"date_cached ({entity_date_cached}) is newer than last_failed_at ({previous_last_failure})."
                )
            if logger and (current_blacklist_id is None or current_blacklist_id != blocklist_id):
                logger.debug(f"Reusing historical blocklist ID {blocklist_id} for {entity_type} {entity_id}.")
        else:
            next_total_errors = 1
            next_streak_errors = 1
            cursor.execute(
                insert_blocklist_query,
                (
                    entity_type,
                    entity_id,
                    next_total_errors,
                    next_streak_errors,
                    normalized_error,
                    failed_at,
                    failed_at,
                )
            )
            blocklist_id = cursor.lastrowid

        cursor.execute(attach_query, (blocklist_id, entity_id))
        conn.commit()
        return blocklist_id

def mark_track_metadata_fetch_failed(track_id, error_code, logger=None):
    """
    Increments track all-time and concurrent error counts in blocklist.
    """
    try:
        _mark_entity_metadata_fetch_failed(
            entity_type="track",
            entity_table="tracks",
            entity_id=track_id,
            error_code=error_code,
            logger=logger,
        )
        if logger:
            logger.debug(f"Track failure recorded in blocklist: id={track_id}, code={error_code}")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to mark track metadata fetch failure for {track_id}: {e}")
        raise

def mark_album_metadata_fetch_failed(album_id, error_code, logger=None):
    """
    Increments album all-time and concurrent error counts in blocklist.
    """
    try:
        blocklist_id = _mark_entity_metadata_fetch_failed(
            entity_type="album",
            entity_table="albums",
            entity_id=album_id,
            error_code=error_code,
            logger=logger,
        )

        if blocklist_id is not None:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE tracks
                    SET blocklisted = 1,
                        blacklist_id = ?
                    WHERE album_id = ?
                    """,
                    (blocklist_id, album_id),
                )
                cascaded_track_count = cursor.rowcount
                conn.commit()

            if logger:
                if cascaded_track_count > 0:
                    logger.debug(
                        f"Album blocklist cascaded to {cascaded_track_count} tracks: album_id={album_id}, blocklist_id={blocklist_id}."
                    )
                else:
                    logger.debug(
                        f"Album blocklist cascade matched no tracks: album_id={album_id}, blocklist_id={blocklist_id}."
                    )

        if logger:
            logger.debug(f"Album failure recorded in blocklist: id={album_id}, code={error_code}")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to mark album metadata fetch failure for {album_id}: {e}")
        raise

def get_album_ids_for_unavailable_tracks(logger=None):
    """
    Returns album IDs for tracks with available_countries='[]' that are not already
    track-blocklisted and do not already have an album blocklist row.
    """
    if logger:
        logger.debug("Disabling this module until resolution of git issue 108")
    return []
    
    query = """
    SELECT DISTINCT t.album_id
    FROM tracks t
    WHERE t.album_id IS NOT NULL
      AND t.available_countries = '[]'
      AND COALESCE(t.blocklisted, 0) = 0
      AND NOT EXISTS (
          SELECT 1
          FROM blocklist b
          WHERE b.entity_type = 'album'
            AND b.entity_id = t.album_id
      )
    ORDER BY t.album_id
    """

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            album_ids = [row[0] for row in cursor.fetchall()]

            if logger and album_ids:
                logger.debug(
                    f"Found {len(album_ids)} albums requiring safeguard blocklist from unavailable tracks."
                )

            return album_ids
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed retrieving albums for unavailable track safeguard: {e}")
        raise

def blocklist_albums_for_unavailable_tracks(logger=None):
    """
    DB-driven safeguard: find unavailable tracks and blocklist their albums by reusing
    the existing album failure path.
    """
    marker_error_code = "available_countries_empty"

    try:
        album_ids = get_album_ids_for_unavailable_tracks(logger)
        if not album_ids:
            if logger:
                logger.debug("No albums require safeguard blocklisting for empty available_countries.")
            return

        created_count = 0
        for album_id in album_ids:
            mark_album_metadata_fetch_failed(album_id, marker_error_code, logger)
            created_count += 1

        if logger:
            logger.debug(
                "Safeguard blocklist applied for unavailable tracks: "
                f"albums_blocklisted={created_count}."
            )
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed safeguard blocklist for unavailable tracks: {e}")
        raise