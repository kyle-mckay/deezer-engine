# Copyright (C) 2026 kylemmkay
# Source: https://codeberg.org/kylemmkay/deezer-engine
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
import sqlite3
import logging
import json
from datetime import datetime, timedelta
from utils.database import get_db_path
from utils.config_loader import get_global_value
from utils.deezer_auth import get_tracks, get_albums
from utils.signals import shutdown_event

# Centralized static path
DB_PATH = get_db_path() 

def _get_connection():
    """Internal helper to provide a connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_blocklist_expiry_iso(current_streak_errors, total_errors, last_failure_iso, default_days=7):
    """
    Calculates the next blocklist expiry timestamp.
    """
    # Placeholder for future dynamic logic
    _ = (current_streak_errors, total_errors, last_failure_iso)

    configured_days = get_global_value("blocklist_expiry_days", default=default_days)
    try:
        expiry_days = int(configured_days)
        if expiry_days < 0:
            expiry_days = default_days
    except (TypeError, ValueError):
        expiry_days = default_days

    return (datetime.now() + timedelta(days=expiry_days)).isoformat()

def _blocklist_where_clause(include_blocklisted):
    """Returns SQL predicate for including or excluding blocklisted entities."""
    return "1=1" if include_blocklisted else "COALESCE(blocklisted, 0) = 0"

def release_expired_blocklisted_entities(logger=None):
    """
    Startup reconciliation: unblocks tracks/albums whose blocklist expiry has passed.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.release_expired_blocklisted_entities")

    now_iso = datetime.now().isoformat()
    select_query = """
    SELECT entity_type, entity_id
    FROM blocklist
    WHERE blocklist_expires_at IS NOT NULL
      AND blocklist_expires_at != ''
      AND blocklist_expires_at <= ?
    """

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(select_query, (now_iso,))
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
                    f"UPDATE tracks SET blocklisted = 0 WHERE id IN ({placeholders})",
                    track_ids
                )
                tracks_unblocked = cursor.rowcount

            if album_ids:
                placeholders = ','.join('?' * len(album_ids))
                cursor.execute(
                    f"UPDATE albums SET blocklisted = 0 WHERE id IN ({placeholders})",
                    album_ids
                )
                albums_unblocked = cursor.rowcount

            conn.commit()

            if logger:
                logger.debug(
                    f"Reopened expired blocklist entries: tracks={tracks_unblocked}, albums={albums_unblocked}"
                )
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to release expired blocklisted entities: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.release_expired_blocklisted_entities")

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
    select_by_entity_query = "SELECT id, total_errors, streak_errors, last_failed_at FROM blocklist WHERE entity_type = ? AND entity_id = ? LIMIT 1"
    update_blocklist_query = """
    UPDATE blocklist
    SET total_errors = ?,
        streak_errors = ?,
        last_error_code = ?,
        last_failed_at = ?,
        blocklist_expires_at = ?
    WHERE id = ?
    """
    insert_blocklist_query = """
    INSERT INTO blocklist (entity_type, entity_id, total_errors, streak_errors, last_error_code, last_failed_at, blocklist_expires_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    attach_query = f"UPDATE {entity_table} SET blacklist_id = ?, blocklisted = 1 WHERE id = ?"

    normalized_error = str(error_code) if error_code is not None else None

    with _get_connection() as conn:
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
            return

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
            blocklist_expiry = calculate_blocklist_expiry_iso(
                current_streak_errors,
                current_total_errors,
                previous_last_failure
            )
            cursor.execute(
                update_blocklist_query,
                (next_total_errors, next_streak_errors, normalized_error, failed_at, blocklist_expiry, blocklist_id)
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
            blocklist_expiry = calculate_blocklist_expiry_iso(0, 0, None)
            cursor.execute(
                insert_blocklist_query,
                (entity_type, entity_id, next_total_errors, next_streak_errors, normalized_error, failed_at, blocklist_expiry)
            )
            blocklist_id = cursor.lastrowid

        cursor.execute(attach_query, (blocklist_id, entity_id))
        conn.commit()

def mark_track_metadata_fetch_failed(track_id, error_code, logger=None):
    """
    Increments track all-time and concurrent error counts in blocklist.
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.mark_track_metadata_fetch_failed ({track_id})")

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
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.mark_track_metadata_fetch_failed")

def mark_album_metadata_fetch_failed(album_id, error_code, logger=None):
    """
    Increments album all-time and concurrent error counts in blocklist.
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.mark_album_metadata_fetch_failed ({album_id})")

    try:
        _mark_entity_metadata_fetch_failed(
            entity_type="album",
            entity_table="albums",
            entity_id=album_id,
            error_code=error_code,
            logger=logger,
        )
        if logger:
            logger.debug(f"Album failure recorded in blocklist: id={album_id}, code={error_code}")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to mark album metadata fetch failure for {album_id}: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.mark_album_metadata_fetch_failed")

def fetch_collection(source_name, logger=None, include_blocklisted=False):
    """
    Retrieves all tracks and their full metadata associated with a specific source.
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.fetch_collection ({source_name})")

    # SQL JOIN: Get track metadata where the track exists in the specified collection
    track_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT t.* FROM tracks t
    JOIN collections c ON t.id = c.track_id
        WHERE c.source_name = ?
            AND {track_filter};
    """
    
    collection_data = []
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query, (source_name,))
            rows = cursor.fetchall()
            
            for row in rows:
                # Convert the sqlite3.Row to a standard dictionary
                track = dict(row)
                
                # Parse 'JSON strings' back into Python objects
                if track.get('available_countries'):
                    track['available_countries'] = json.loads(track['available_countries'])
                if track.get('contributors'):
                    track['contributors'] = json.loads(track['contributors'])
                
                collection_data.append(track)
            
            if logger:
                logger.debug(f"DB: Retrieved {len(collection_data)} tracks for '{source_name}'.")
                
            return collection_data
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to fetch '{source_name}': {e}")
        return []
    finally:
        if logger:
            logger.debug(f"<<< END: utils.db_manager.fetch_collection")

def validate_sync_integrity(original_tracks, synced_tracks, logger):
    """
    Compares original fetched tracks with synced tracks from the database.
    Ensures data integrity after sync_to_collections.
    """
    logger.debug(">>> START: utils.db_manager.validate_sync_integrity")
    
    if not original_tracks or not synced_tracks:
        logger.warning("Sync validation skipped: One or both track lists are empty.")
        return
    
    # Get track IDs from both sources
    original_ids = {str(t.get('id')) for t in original_tracks}
    synced_ids = {str(t.get('id')) for t in synced_tracks}
    
    logger.debug(f"Original track count: {len(original_ids)}, Synced track count: {len(synced_ids)}")
    
    # Check if all original tracks were synced
    missing_ids = original_ids - synced_ids
    if missing_ids:
        error_msg = f"Data integrity error: {len(missing_ids)} tracks missing from synced collection. Missing IDs: {missing_ids}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Check if extra tracks were added (shouldn't happen)
    extra_ids = synced_ids - original_ids
    if extra_ids:
        error_msg = f"Data integrity error: {len(extra_ids)} unexpected tracks in synced collection. Extra IDs: {extra_ids}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    if original_ids == synced_ids:
        logger.debug(f"Sync validation passed: All {len(original_ids)} track IDs match between original and synced data.")
        logger.debug("<<< END: utils.db_manager.validate_sync_integrity")
    else:
        error_msg = "Sync validation failed: Track ID mismatch detected."
        logger.error(error_msg)
        raise ValueError(error_msg)

def sync_to_collections(tracklist, logger, collection_name=None):
    """
    Parses a tracklist where each track contains its own source info.
    Inserts IDs into 'tracks' and maps them in 'collections'.
    """
    logger.debug(">>> START: utils.db_manager.sync_to_collections")
    if not tracklist:
        if collection_name:
            try:
                with _get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM collections WHERE source_name = ?",
                        (collection_name,)
                    )
                    conn.commit()
                    logger.debug(f"DB: Cleared {cursor.rowcount} cached tracks from '{collection_name}'.")
            except Exception as e:
                logger.error(f"DB Sync failed: {e}")
            finally:
                logger.debug("<<< END: utils.db_manager.sync_to_collections")
            return

        logger.debug("Sync skipped: No tracks provided in payload.")
        return
    
    # Use a set to handle unique pairs of (id, source) from the input
    # If collection_name is provided, use it as default; otherwise use track's collection or 'unknown'
    if collection_name:
        unique_pairs = {(str(t['id']), collection_name) for t in tracklist}
        logger.debug(f"Using provided collection_name: '{collection_name}' for all tracks.")
    else:
        unique_pairs = {(str(t['id']), t.get('collection', 'unknown')) for t in tracklist}
    
    unique_track_ids = {tid for tid, source in unique_pairs}
    
    logger.debug(f"DB: Syncing {len(unique_track_ids)} unique track IDs.")

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            date_time = datetime.now().isoformat()

            # extracts (id, collection, date_cached) from the payload
            if collection_name:
                # Use provided collection_name for all tracks
                unique_pairs = {
                    (
                        str(t['id']), 
                        collection_name,
                        date_time
                    ) for t in tracklist
                }
            else:
                # Use collection from each track object
                unique_pairs = {
                    (
                        str(t['id']), 
                        t.get('collection', 'unknown'), 
                        date_time
                    ) for t in tracklist
                }
            
            # Unique track IDs for the master tracks table
            unique_track_ids = {tid for tid, source, timestamp in unique_pairs}
            
            # Update 'tracks' table. Metadata is fetched in a later step.
            track_entries = [(tid,) for tid in unique_track_ids]
            cursor.executemany(
                "INSERT OR IGNORE INTO tracks (id) VALUES (?)", 
                track_entries
            )
            
            # Replace each touched collection atomically without affecting other collections.
            incoming_ids_by_collection = {}
            for track_id, source_name, _timestamp in unique_pairs:
                incoming_ids_by_collection.setdefault(source_name, set()).add(track_id)

            for source_name, incoming_ids in incoming_ids_by_collection.items():
                if incoming_ids:
                    placeholders = ','.join('?' * len(incoming_ids))
                    delete_query = f"DELETE FROM collections WHERE source_name = ? AND track_id NOT IN ({placeholders})"
                    delete_params = [source_name, *sorted(incoming_ids)]
                    cursor.execute(delete_query, delete_params)
                else:
                    cursor.execute(
                        "DELETE FROM collections WHERE source_name = ?",
                        (source_name,)
                    )

                if logger and cursor.rowcount > 0:
                    logger.debug(f"DB: Removed {cursor.rowcount} stale tracks from ['{source_name}']")

            # Update 'collections' table

            collection_entries = [(tid, source, timestamp) for tid, source, timestamp in unique_pairs]
            cursor.executemany(
                "INSERT OR REPLACE INTO collections (track_id, source_name, date_cached) VALUES (?, ?, ?)", 
                collection_entries
            )

            conn.commit()
            logger.debug("DB: Transaction committed successfully.")

    except Exception as e:
        logger.error(f"DB Sync failed: {e}")
    finally:
        logger.debug("<<< END: utils.db_manager.sync_to_collections")

def get_unprocessed_track_ids(logger=None, include_blocklisted=False):
    """
    Retrieves all track IDs from the database that have not yet been 
    enriched with metadata.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_unprocessed_track_ids")

    track_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id
    FROM tracks
    WHERE (date_cached IS NULL OR date_cached = '')
      AND {track_filter};
    """
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            # Map the rows to the requested payload format
            tracks_payload = [{'id': row['id']} for row in rows]
            
            if logger and len(tracks_payload) > 0:
                logger.debug(f"Database: {len(tracks_payload)} tracks found requiring enrichment.")
            
            return tracks_payload
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to check for unprocessed tracks: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_unprocessed_track_ids")

def get_unprocessed_album_ids(logger=None, include_blocklisted=False):
    """
    Retrieves all album IDs from the database that have not yet been 
    enriched with metadata OR have not completed genre mapping.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_unprocessed_album_ids")

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
        with _get_connection() as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            # Return list of album IDs
            album_ids = [row[0] for row in rows]
            
            if logger and len(album_ids) > 0:
                logger.debug(f"Database: {len(album_ids)} albums found requiring enrichment or genre mapping.")
            
            return album_ids
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to check for unprocessed albums: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_unprocessed_album_ids")

def reset_album_genres_by_track_ids(track_ids, logger=None):
    """
    Resets genre_mapped flag to 0 for albums associated with tracks missing genre mappings.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.reset_album_genres_by_track_ids")
    
    if not track_ids:
        if logger:
            logger.debug("No track IDs provided. Skipping album genre reset.")
        return 0
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # Find unique album IDs for the tracks with missing genres
            placeholders = ','.join('?' * len(track_ids))
            query = f"""
            SELECT DISTINCT album_id FROM tracks 
            WHERE id IN ({placeholders}) AND album_id IS NOT NULL
            """
            cursor.execute(query, track_ids)
            album_ids = [row[0] for row in cursor.fetchall()]
            
            if not album_ids:
                if logger:
                    logger.debug("No albums found for tracks missing genres.")
                return 0
            
            # Reset genre_mapped to 0 for these albums
            reset_placeholders = ','.join('?' * len(album_ids))
            reset_query = f"""
            UPDATE albums SET genre_mapped = 0 WHERE id IN ({reset_placeholders})
            """
            cursor.execute(reset_query, album_ids)
            rows_affected = cursor.rowcount
            
            conn.commit()
            
            if logger:
                logger.debug(f"Reset genre_mapped=0 for {rows_affected} albums associated with {len(track_ids)} tracks missing genres.")
            
            return rows_affected
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to reset album genres by track IDs: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.reset_album_genres_by_track_ids")

def update_unprocessed(client,logger):
    """
    Identify and process tracks/albums that need metadata and genre mapping.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.update_unprocessed")
    
    # Process unprocessed tracks
    unprocessed = get_unprocessed_track_ids(logger)
    if len(unprocessed) > 0:
        logger.info(f"Fetching metadata for {len(unprocessed)} new tracks...")
        unprocessed = get_tracks(client,logger,"database","tracks","null",unprocessed)
        logger.debug(f"Metadata fetched, updating database with {len(unprocessed)} records.")
        update_track_metadata(unprocessed,logger)
        unprocessed = get_unprocessed_track_ids(logger)
        if len(unprocessed) > 0:
            logger.warning(f"Metadata enrichment finished but tracks are missing metadata. Expecting 0, got {len(unprocessed)}")
    
    # Track metadata committed — safe exit point before album enrichment begins.
    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after track enrichment. Deferring album enrichment to next run.")
        return

    # Process unprocessed albums
    sync_missing_albums_to_table(logger)
    sync_missing_artists_to_table(logger)
    unprocessed_album = get_unprocessed_album_ids(logger)
    enriched_albums = []
    
    if len(unprocessed_album) > 0:
        logger.info(f"Fetching metadata for {len(unprocessed_album)} new albums...")
        unprocessed_album = get_albums(client, logger, identifier="database", album_ids=unprocessed_album)
        logger.debug(f"Metadata fetched, updating database with {len(unprocessed_album)} records.")
        update_album_metadata(unprocessed_album, logger)
        enriched_albums = unprocessed_album
        
        unprocessed_album = get_unprocessed_album_ids(logger)
        if len(unprocessed_album) > 0:
            logger.warning(f"Metadata enrichment finished but albums are missing metadata. Expecting 0, got {len(unprocessed_album)}")
    
    # Album metadata committed — safe exit point before genre mapping cascades.
    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after album enrichment. Deferring genre mapping to next run.")
        return

    # Populate album genres for newly enriched albums
    if enriched_albums:
        logger.debug(f"Populating genres for {len(enriched_albums)} enriched albums...")
        try:
            populate_album_genres(enriched_albums, logger)
        except Exception as e:
            logger.error(f"Failed to populate album genres: {e}")

    # Album->genre mapping committed — safe exit point before global track-genre pass.
    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after album-genre mapping. Deferring track-genre mapping to next run.")
        return
    
    # Populate track genres from album relationships
    logger.debug("Populating track genres from album relationships...")
    try:
        populate_track_genres(logger)
    except Exception as e:
        logger.error(f"Failed to populate track genres: {e}")

    # Track-genre mapping committed — safe exit point before diagnostics/requeue checks.
    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after track-genre mapping. Deferring diagnostics to next run.")
        return
    
    # Check for albums still missing genre mappings  
    albums_missing_genres = get_albums_missing_genres(logger)
    if albums_missing_genres:
        if logger:
            logger.debug(f"Albums missing genre mappings (IDs: {albums_missing_genres})")
        logger.warning(f"Found {len(albums_missing_genres)} albums without genre mapping. These will be reprocessed on the next cycle.")
    
    # Check for tracks still missing genre mappings
    tracks_missing_genres = get_tracks_missing_genres(logger)
    if tracks_missing_genres:
        if logger:
            logger.debug(f"Tracks missing genre mappings (IDs: {tracks_missing_genres})")
        logger.warning(f"Found {len(tracks_missing_genres)} tracks missing genre mappings. Associated albums will be reset and reprocessed on the next cycle.")
        # Reset the albums associated with these tracks so they get re-processed
        reset_album_genres_by_track_ids(tracks_missing_genres, logger)
    
    if logger:
        logger.debug("<<< END: utils.db_manager.update_unprocessed")

def update_tracks_partial_batch(track_list, logger=None):
    """
    Updates multiple tracks using the keys present in the first dictionary.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.update_tracks_partial_batch")

    if not track_list:
        return

    sample_track = track_list[0]
    update_keys = [k for k in sample_track.keys() if k != 'id']
    set_clause = ", ".join([f"{k} = ?" for k in update_keys])
    query = f"UPDATE tracks SET {set_clause} WHERE id = ?;"

    data_tuples = []
    for t in track_list:
        row_values = [t.get(k) for k in update_keys]
        row_values.append(t.get('id'))
        data_tuples.append(tuple(row_values))

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data_tuples)
            conn.commit()
            if logger:
                logger.info(f"Refreshed stats (rank/unseen) for {len(track_list)} tracks.")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Partial batch update failed: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.update_tracks_partial_batch")

def update_track_metadata(track_list, logger=None):
    """
    Updates the tracks table with full metadata fetched from the Deezer API.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.update_track_metadata")
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
            t.get('readable'), t.get('title'), t.get('title_short'), t.get('title_version'),
            t.get('unseen'), t.get('isrc'), t.get('link'), t.get('share'), t.get('duration'),
            t.get('track_position'), t.get('disk_number'), t.get('rank'), t.get('release_date'),
            t.get('explicit_lyrics'), t.get('explicit_content_lyrics'), t.get('explicit_content_cover'),
            t.get('preview'), t.get('bpm'), t.get('gain'), t.get('available_countries'),
            t.get('contributors'), t.get('md5_image'), t.get('track_token'), t.get('artist_id'),
            t.get('album_id'), t.get('date_cached'), t.get('id')
        )
        for t in track_list
    ]
    
    if logger and data_tuples:
        sample_track = track_list[0]
        logger.debug(f"Sample track data structure: id={sample_track.get('id')} (type: {type(sample_track.get('id')).__name__}), title={sample_track.get('title')}, date_cached={sample_track.get('date_cached')}")
        logger.debug(f"Sample data tuple (last 3 fields): album_id={data_tuples[0][-3]}, date_cached={data_tuples[0][-2]}, id={data_tuples[0][-1]}")

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # Ensure FK parent rows exist before writing track references.
            artist_ids = sorted({t.get('artist_id') for t in track_list if t.get('artist_id') is not None})
            if artist_ids:
                cursor.executemany(
                    "INSERT OR IGNORE INTO artists (id) VALUES (?)",
                    [(artist_id,) for artist_id in artist_ids]
                )
                if logger:
                    logger.debug(f"Upserted {len(artist_ids)} artist stubs from track metadata payload.")

            album_ids = sorted({t.get('album_id') for t in track_list if t.get('album_id') is not None})
            if album_ids:
                cursor.executemany(
                    "INSERT OR IGNORE INTO albums (id) VALUES (?)",
                    [(album_id,) for album_id in album_ids]
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
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Metadata update failed: {e}")
            logger.exception("Stack trace for track metadata update error:")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.update_track_metadata")

def update_album_metadata(album_list, logger=None):
    """
    Updates the albums table with full metadata fetched from the Deezer API.
    Captures complete album information including covers, genres, and metadata.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.update_album_metadata")
        logger.debug(f"Received {len(album_list) if album_list else 0} albums for metadata update")

    if not album_list:
        if logger:
            logger.debug("Album list is empty, returning early.")
        return

    query = """
    UPDATE albums SET
        title = ?, upc = ?, link = ?, share = ?, cover = ?, cover_small = ?, 
        cover_medium = ?, cover_big = ?, cover_xl = ?, md5_image = ?, 
        label = ?, nb_tracks = ?, duration = ?, fans = ?, release_date = ?, 
        record_type = ?, available = ?, tracklist = ?, explicit_lyrics = ?, 
        explicit_content_lyrics = ?, explicit_content_cover = ?, genres = ?, contributors = ?, 
        artist_id = ?, artist_name = ?, date_cached = ?
    WHERE id = ?;
    """

    data_tuples = [
        (
            a.get('title'), a.get('upc'), a.get('link'), a.get('share'),
            a.get('cover'), a.get('cover_small'), a.get('cover_medium'), a.get('cover_big'),
            a.get('cover_xl'), a.get('md5_image'), a.get('label'),
            a.get('nb_tracks'), a.get('duration'), a.get('fans'), a.get('release_date'),
            a.get('record_type'), a.get('available'), a.get('tracklist'),
            a.get('explicit_lyrics'), a.get('explicit_content_lyrics'), a.get('explicit_content_cover'),
            a.get('genres'), a.get('contributors'), a.get('artist_id'), a.get('artist_name'), a.get('date_cached'),
            a.get('id')
        )
        for a in album_list
    ]
    
    if logger and data_tuples:
        sample_album = album_list[0]
        logger.debug(f"Sample album data structure: id={sample_album.get('id')} (type: {type(sample_album.get('id')).__name__}), title={sample_album.get('title')}, date_cached={sample_album.get('date_cached')}")
        logger.debug(f"Sample data tuple (last 3 fields): artist_name={data_tuples[0][-3]}, date_cached={data_tuples[0][-2]}, id={data_tuples[0][-1]}")

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # Ensure FK parent artist rows exist before writing album references.
            artist_ids = sorted({a.get('artist_id') for a in album_list if a.get('artist_id') is not None})
            if artist_ids:
                cursor.executemany(
                    "INSERT OR IGNORE INTO artists (id) VALUES (?)",
                    [(artist_id,) for artist_id in artist_ids]
                )
                if logger:
                    logger.debug(f"Upserted {len(artist_ids)} artist stubs from album metadata payload.")

            if logger:
                logger.debug(f"Executing UPDATE query for {len(data_tuples)} albums...")
            cursor.executemany(query, data_tuples)
            rows_affected = cursor.rowcount
            if logger:
                logger.debug(f"UPDATE query affected {rows_affected} rows.")
            conn.commit()
            if logger:
                logger.debug(f"Metadata enrichment complete for {len(album_list)} albums.")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Album metadata update failed: {e}")
            logger.exception("Stack trace for album metadata update error:")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.update_album_metadata")

def populate_album_genres(album_list, logger=None):
    """
    Populates the genres table with unique genres from the Deezer API response,
    and creates many-to-many relationships in the album_genres junction table.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.populate_album_genres")
        logger.debug(f"Processing {len(album_list) if album_list else 0} albums for genre population")

    if not album_list:
        if logger:
            logger.debug("Album list is empty, returning early.")
        return

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            processed_album_ids = []

            # Collect all unique genres across all albums
            all_genres = {}
            album_genre_relationships = []
            
            for album in album_list:
                album_id = album.get('id')
                genres_json = album.get('genres', '[]')
                
                if not album_id:
                    continue

                processed_album_ids.append(album_id)
                
                # Parse genres
                try:
                    if isinstance(genres_json, str):
                        genres = json.loads(genres_json)
                    else:
                        genres = genres_json if isinstance(genres_json, list) else []
                except json.JSONDecodeError:
                    if logger:
                        logger.debug(f"Failed to parse genres JSON for album {album_id}: {genres_json}")
                    genres = []
                
                if not genres:
                    continue
                
                # Extract unique genres
                for genre_obj in genres:
                    if not isinstance(genre_obj, dict):
                        continue

                    genre_name = genre_obj.get('name')
                    deezer_genre_id = genre_obj.get('id')

                    if not genre_name or deezer_genre_id is None:
                        continue

                    try:
                        deezer_genre_id = int(deezer_genre_id)
                    except (TypeError, ValueError):
                        if logger:
                            logger.debug(f"Skipping invalid genre id for album {album_id}: {deezer_genre_id}")
                        continue

                    # Track genre by name, using Deezer genre ID as canonical identifier
                    if genre_name not in all_genres:
                        all_genres[genre_name] = deezer_genre_id

                    # Record the album-genre relationship using Deezer genre ID directly
                    album_genre_relationships.append((album_id, deezer_genre_id))
            
            if all_genres:
                # Reconcile existing genres
                for genre_name, deezer_genre_id in all_genres.items():
                    cursor.execute("SELECT id FROM genres WHERE name = ?", (genre_name,))
                    existing_row = cursor.fetchone()

                    if existing_row and existing_row[0] != deezer_genre_id:
                        old_genre_id = existing_row[0]

                        cursor.execute(
                            "SELECT name FROM genres WHERE id = ?",
                            (deezer_genre_id,)
                        )
                        conflicting_target = cursor.fetchone()
                        if conflicting_target and conflicting_target[0] != genre_name:
                            if logger:
                                logger.warning(
                                    f"Genre ID conflict detected for Deezer genre {deezer_genre_id}: "
                                    f"existing name '{conflicting_target[0]}', incoming '{genre_name}'. Skipping remap."
                                )
                            continue

                        temp_name = f"{genre_name}__legacy_{old_genre_id}"
                        cursor.execute(
                            "UPDATE genres SET name = ? WHERE id = ?",
                            (temp_name, old_genre_id)
                        )
                        cursor.execute(
                            "INSERT OR IGNORE INTO genres (id, name) VALUES (?, ?)",
                            (deezer_genre_id, genre_name)
                        )

                        cursor.execute(
                            "UPDATE OR IGNORE album_genres SET genre_id = ? WHERE genre_id = ?",
                            (deezer_genre_id, old_genre_id)
                        )
                        cursor.execute(
                            "DELETE FROM album_genres WHERE genre_id = ?",
                            (old_genre_id,)
                        )

                        cursor.execute(
                            "UPDATE OR IGNORE track_genres SET genre_id = ? WHERE genre_id = ?",
                            (deezer_genre_id, old_genre_id)
                        )
                        cursor.execute(
                            "DELETE FROM track_genres WHERE genre_id = ?",
                            (old_genre_id,)
                        )

                        cursor.execute("DELETE FROM genres WHERE id = ?", (old_genre_id,))

                # Insert genres into the genres table using Deezer IDs.
                genre_insert_tuples = [(genre_id, name) for name, genre_id in all_genres.items()]
                if logger:
                    logger.debug(f"Inserting {len(genre_insert_tuples)} unique genres into database")

                cursor.executemany(
                    "INSERT OR IGNORE INTO genres (id, name) VALUES (?, ?)",
                    genre_insert_tuples
                )

                # Create album_genres relationships
                album_genres_tuples = []
                for album_id, genre_id in album_genre_relationships:
                    album_genres_tuples.append((album_id, genre_id))

                if logger:
                    logger.debug(f"Creating {len(album_genres_tuples)} album-genre relationships")

                # Insert relationships into album_genres table (using REPLACE to handle updates)
                cursor.executemany(
                    "INSERT OR REPLACE INTO album_genres (album_id, genre_id) VALUES (?, ?)",
                    album_genres_tuples
                )
            else:
                if logger:
                    logger.debug("No genres found in album data.")
                album_genres_tuples = []

            # Mark processed albums as having completed genre mapping pass
            if processed_album_ids:
                cursor.executemany(
                    "UPDATE albums SET genre_mapped = 1 WHERE id = ?",
                    [(album_id,) for album_id in set(processed_album_ids)]
                )
                if logger:
                    logger.debug(f"Marked {len(set(processed_album_ids))} albums as genre_mapped=1")
            
            conn.commit()
            if logger:
                logger.debug(f"Genre population complete: {len(all_genres)} genres, {len(album_genres_tuples)} relationships")
            
            # Populate track genres for each album that was enriched
            enriched_album_ids = set(album_id for album_id, _ in album_genre_relationships)
            if logger:
                logger.debug(f"Retroactively populating track genres for {len(enriched_album_ids)} enriched albums")
            
            for album_id in enriched_album_ids:
                if shutdown_event.is_set():
                    if logger:
                        logger.debug("Shutdown acknowledged during per-album track-genre backfill. Remaining albums deferred to next run.")
                    break
                try:
                    populate_track_genres_for_album(album_id, logger)
                except Exception as album_err:
                    if logger:
                        logger.warning(f"Failed to populate track genres for album {album_id}: {album_err}")
                    # Continue with other albums
                    continue
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Genre population failed: {e}")
            logger.exception("Stack trace for genre population error:")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.populate_album_genres")

def populate_track_genres(logger=None):
    """
    Populates the track_genres table by inheriting genres from albums.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.populate_track_genres")

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # Identify albums whose tracks haven't been mapped yet
            cursor.execute("""
            SELECT COUNT(*) FROM tracks
            WHERE COALESCE(genre_mapped, 0) = 0
              AND album_id IS NOT NULL
              AND album_id IN (
                  SELECT id FROM albums 
                  WHERE COALESCE(genre_mapped, 0) = 1
              )
            """)
            unmapped_tracks_count = cursor.fetchone()[0]
            
            if unmapped_tracks_count == 0:
                if logger:
                    logger.debug("No unmapped tracks found. Skipping track-genre population.")
                return
            
            if logger:
                logger.debug(f"Found {unmapped_tracks_count} unmapped tracks to process.")
            
            # Only for tracks that haven't been genre_mapped yet
            insert_query = """
            INSERT OR REPLACE INTO track_genres (track_id, genre_id)
            SELECT DISTINCT t.id, ag.genre_id
            FROM tracks t
            JOIN albums a ON t.album_id = a.id
            JOIN album_genres ag ON a.id = ag.album_id
            WHERE t.album_id IS NOT NULL
              AND COALESCE(t.genre_mapped, 0) = 0
              AND COALESCE(a.genre_mapped, 0) = 1
            """
            
            if logger:
                logger.debug("Executing track-genre population from album-genre relationships")
            
            cursor.execute(insert_query)
            rows_affected = cursor.rowcount

            # Mark tracks as genre mapping processed when their album mapping pass is complete
            # This includes albums that may legitimately have no genres.
            cursor.execute(
                """
                UPDATE tracks
                SET genre_mapped = 1
                WHERE COALESCE(genre_mapped, 0) = 0
                  AND album_id IS NOT NULL
                  AND album_id IN (
                      SELECT id
                      FROM albums
                      WHERE COALESCE(genre_mapped, 0) = 1
                  )
                """
            )
            tracks_marked = cursor.rowcount
            
            conn.commit()
            
            if logger:
                logger.debug(f"Track-genre population complete: {rows_affected} track-genre relationships created, {tracks_marked} tracks marked genre_mapped=1")
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Track genre population failed: {e}")
            logger.exception("Stack trace for track genre population error:")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.populate_track_genres")

def populate_track_genres_for_album(album_id, logger=None):
    """
    Populates track_genres for a specific album.   
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.populate_track_genres_for_album ({album_id})")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if album has any genres
            cursor.execute("SELECT COUNT(*) FROM album_genres WHERE album_id = ?", (album_id,))
            genre_count = cursor.fetchone()[0]
            
            if genre_count == 0:
                cursor.execute(
                    "UPDATE tracks SET genre_mapped = 1 WHERE album_id = ?",
                    (album_id,)
                )
                conn.commit()
                if logger:
                    logger.debug(f"Album {album_id} has no genres to populate. Marked tracks as genre_mapped=1.")
                return 0
            
            # Populate track-genres for this album's tracks
            insert_query = """
            INSERT OR REPLACE INTO track_genres (track_id, genre_id)
            SELECT DISTINCT t.id, ag.genre_id
            FROM tracks t
            JOIN album_genres ag ON ag.album_id = ?
            WHERE t.album_id = ?
            """
            
            cursor.execute(insert_query, (album_id, album_id))
            rows_affected = cursor.rowcount

            cursor.execute(
                "UPDATE tracks SET genre_mapped = 1 WHERE album_id = ?",
                (album_id,)
            )
            tracks_marked = cursor.rowcount
            
            conn.commit()
            
            if logger:
                logger.debug(f"Populated {rows_affected} track-genre relationships for album {album_id}, marked {tracks_marked} tracks as genre_mapped=1")
            
            return rows_affected
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to populate track genres for album {album_id}: {e}")
        raise
    finally:
        if logger:
            logger.debug(f"<<< END: utils.db_manager.populate_track_genres_for_album")

def get_albums_missing_genres(logger=None, include_blocklisted=False):
    """
    Retrieves all album IDs that have not completed genre mapping.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_albums_missing_genres")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # Find albums that have not completed genre mapping
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
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to retrieve albums missing genres: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_albums_missing_genres")

def get_tracks_missing_genres(logger=None, include_blocklisted=False):
    """
    Retrieves all track IDs that have not completed genre mapping.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_tracks_missing_genres")
    
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # Find tracks that have not completed genre mapping
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
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to retrieve tracks missing genres: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_tracks_missing_genres")

def update_albums_partial_batch(album_list, logger=None):
    """
    Updates multiple albums with refreshable fields only (fans, available, date_cached).
    Used for periodic stats refreshing without full metadata fetch.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.update_albums_partial_batch")

    if not album_list:
        return

    query = """
    UPDATE albums SET
        fans = ?, available = ?, date_cached = ?
    WHERE id = ?
    """

    data_tuples = [
        (
            a.get('fans'), a.get('available'), a.get('date_cached'), a.get('id')
        )
        for a in album_list
    ]

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data_tuples)
            conn.commit()
            if logger:
                logger.info(f"Refreshed stats (fans/available) for {len(album_list)} albums.")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Partial album batch update failed: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.update_albums_partial_batch")

def get_unique_album_ids_from_tracks(logger=None):
    """
    Retrieves all unique album IDs from the tracks table where album_id is not NULL.
    Returns a set of album IDs.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_unique_album_ids_from_tracks")
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT album_id 
                FROM tracks 
                WHERE album_id IS NOT NULL
                ORDER BY album_id
            """)
            
            album_ids = {row[0] for row in cursor.fetchall()}
            
            if logger:
                logger.debug(f"DB: Found {len(album_ids)} unique album IDs in tracks table.")
            
            return album_ids
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to get unique album IDs - {e}")
        return set()
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_unique_album_ids_from_tracks")

def get_missing_album_ids(logger=None):
    """
    Identifies album IDs that exist in the tracks table but are missing from the albums table.
    Returns a set of missing album IDs.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_missing_album_ids")
    
    try:
        with _get_connection() as conn:
            # Get all unique album IDs from tracks
            cursor = conn.execute("""
                SELECT DISTINCT album_id 
                FROM tracks 
                WHERE album_id IS NOT NULL
            """)
            track_album_ids = {row[0] for row in cursor.fetchall()}
            
            # Get all album IDs that already exist in albums table
            cursor = conn.execute("""
                SELECT DISTINCT id 
                FROM albums
            """)
            existing_album_ids = {row[0] for row in cursor.fetchall()}
            
            # Find the difference
            missing_album_ids = track_album_ids - existing_album_ids
            
            if logger:
                logger.debug(f"DB: {len(track_album_ids)} album IDs in tracks, {len(existing_album_ids)} in albums table.")
                logger.debug(f"DB: {len(missing_album_ids)} missing album IDs to be synced.")
            
            return missing_album_ids
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to get missing album IDs - {e}")
        return set()
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_missing_album_ids")

def get_missing_artist_ids(logger=None):
    """
    Identifies artist IDs referenced by tracks/albums that are missing from the artists table.
    Returns a set of missing artist IDs.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_missing_artist_ids")

    try:
        with _get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT artist_id
                FROM tracks
                WHERE artist_id IS NOT NULL
                UNION
                SELECT DISTINCT artist_id
                FROM albums
                WHERE artist_id IS NOT NULL
            """)
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

    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to get missing artist IDs - {e}")
        return set()
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_missing_artist_ids")

def sync_missing_albums_to_table(logger=None):
    """
    Identifies missing album IDs from tracks table and inserts stub records into albums table.
    Stub records contain only the album ID; other fields will be populated during metadata enrichment.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.sync_missing_albums_to_table")
    
    try:
        missing_ids = get_missing_album_ids(logger)
        
        if not missing_ids:
            if logger:
                logger.debug("DB: All track albums already exist in albums table.")
            return
        
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert stub records for missing albums (only ID, other fields NULL)
            insert_query = "INSERT INTO albums (id) VALUES (?)"
            cursor.executemany(insert_query, [(album_id,) for album_id in missing_ids])
            conn.commit()
            
            if logger:
                logger.debug(f"Album Sync: Inserted {len(missing_ids)} stub album records for later enrichment.")
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Album sync to table failed - {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.sync_missing_albums_to_table")

def sync_missing_artists_to_table(logger=None):
    """
    Identifies missing artist IDs from tracks/albums and inserts stub records into artists table.
    Stub records contain only the artist ID; other fields will be populated during enrichment.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.sync_missing_artists_to_table")

    try:
        missing_ids = get_missing_artist_ids(logger)

        if not missing_ids:
            if logger:
                logger.debug("DB: All referenced artists already exist in artists table.")
            return

        with _get_connection() as conn:
            cursor = conn.cursor()

            insert_query = "INSERT INTO artists (id) VALUES (?)"
            cursor.executemany(insert_query, [(artist_id,) for artist_id in missing_ids])
            conn.commit()

            if logger:
                logger.debug(f"Artist Sync: Inserted {len(missing_ids)} stub artist records for later enrichment.")

    except Exception as e:
        if logger:
            logger.error(f"DB Error: Artist sync to table failed - {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.sync_missing_artists_to_table")

def get_expired_track_ids(logger=None, include_blocklisted=False):
    """
    Returns a list of track IDs where date_cached is older than n days. Should ignore unprocessed (new) ids.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_expired_track_ids")

    track_stats_refresh=get_global_value("track_stats_refresh",default = 90)
    track_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id 
    FROM tracks 
    WHERE date_cached < datetime('now', '-{track_stats_refresh} days')
      AND {track_filter};
    """
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query)
            expired_ids = [row[0] for row in cursor.fetchall()]
            
            if logger and len(expired_ids) > 0:
                logger.debug(f"DB: Detected {len(expired_ids)} tracks older than {track_stats_refresh} days.")
                
            return expired_ids
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Expiry check failed: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_expired_track_ids")

def refresh_stats(client, logger):
    refresh_stats = get_expired_track_ids(logger)
    if len(refresh_stats) > 0:
        logger.info(f"Refreshing stats for {len(refresh_stats)} existing tracks...")
        refresh_stats = get_tracks(client, logger, "database", "stats", "null", refresh_stats)
        logger.debug(f"Stats fetched, updating database.")
        update_tracks_partial_batch(refresh_stats)
    
    expired_albums = get_expired_album_ids(logger)
    if len(expired_albums) > 0:
        logger.info(f"Refreshing stats for {len(expired_albums)} existing albums...")
        album_stats = get_albums(client, logger, identifier="stats", album_ids=expired_albums)
        logger.debug(f"Album stats fetched, updating database.")
        if album_stats:
            update_albums_partial_batch(album_stats, logger)

def get_expired_album_ids(logger=None, include_blocklisted=False):
    """
    Returns a list of album IDs where date_cached is older than n days. Should ignore unprocessed (new) ids.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_expired_album_ids")

    album_stats_refresh = get_global_value("album_stats_refresh", default=90)
    album_filter = _blocklist_where_clause(include_blocklisted)
    query = f"""
    SELECT id 
    FROM albums 
    WHERE date_cached < datetime('now', '-{album_stats_refresh} days')
      AND {album_filter};
    """
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query)
            expired_ids = [row[0] for row in cursor.fetchall()]
            
            if logger and len(expired_ids) > 0:
                logger.debug(f"DB: Detected {len(expired_ids)} albums older than {album_stats_refresh} days or missing cache date.")
                
            return expired_ids
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Album expiry check failed: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_expired_album_ids")

def is_collection_cached(source_name, config, logger=None):
    """
    Checks if a collection exists and was cached within the retention window.
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.is_collection_cached ({source_name})")

    retention_hrs = config.get('retention', get_global_value('retention', default = 0))
    if logger:
        logger.debug(f"Retention hours for '{source_name}': {retention_hrs}")
    query = """
    SELECT date_cached FROM collections 
    WHERE source_name = ? 
    ORDER BY date_cached DESC LIMIT 1;
    """
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query, (source_name,))
            row = cursor.fetchone()
            
            if not row or not row['date_cached']:
                if logger:
                    logger.debug(f"Cache miss: '{source_name}' not found.")
                return False
            
            cache_time = datetime.fromisoformat(row['date_cached'])
            expiration_time = datetime.now() - timedelta(hours=retention_hrs)
            
            is_valid = cache_time > expiration_time
            
            if logger:
                if is_valid:
                    logger.debug(f"Cache verify: {'Valid' if is_valid else 'Expired'} (Age: {cache_time} > Exp: {expiration_time})")
                else:
                    logger.debug(f"Cache verify: {'Valid' if is_valid else 'Expired'} (Age: {cache_time} < Exp: {expiration_time})")
                
            return is_valid
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Cache validation failed: {e}")
        return False
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.is_collection_cached")