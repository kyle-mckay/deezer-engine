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
from utils.db.connection import get_db_path
from utils.config import get_global_value
from utils.deezer_auth import get_tracks, get_albums
from utils.infrastructure.signals import shutdown_event

def _get_connection():
    """Internal helper to provide a connection with row factory enabled."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn

def _blocklist_where_clause(include_blocklisted):
    from utils.db.blocklist import _blocklist_where_clause as _real_blocklist_where_clause
    return _real_blocklist_where_clause(include_blocklisted)

def release_expired_blocklisted_entities(logger=None):
    """Wrapper for blocklist expiry logic (see utils/db/blocklist.py)."""
    from utils.db.blocklist import release_expired_blocklisted_entities as _real_release_expired
    return _real_release_expired(logger)


def _mark_entity_metadata_fetch_failed(entity_type, entity_table, entity_id, error_code, logger=None):
    from utils.db.blocklist import _mark_entity_metadata_fetch_failed as _real_mark_entity_metadata_fetch_failed
    return _real_mark_entity_metadata_fetch_failed(entity_type, entity_table, entity_id, error_code, logger)

def mark_track_metadata_fetch_failed(track_id, error_code, logger=None):
    from utils.db.blocklist import mark_track_metadata_fetch_failed as _real_mark_track_metadata_fetch_failed
    return _real_mark_track_metadata_fetch_failed(track_id, error_code, logger)

def mark_album_metadata_fetch_failed(album_id, error_code, logger=None):
    from utils.db.blocklist import mark_album_metadata_fetch_failed as _real_mark_album_metadata_fetch_failed
    return _real_mark_album_metadata_fetch_failed(album_id, error_code, logger)

def get_album_ids_for_unavailable_tracks(logger=None):
    from utils.db.blocklist import get_album_ids_for_unavailable_tracks as _real_get_album_ids_for_unavailable_tracks
    return _real_get_album_ids_for_unavailable_tracks(logger)

def blocklist_albums_for_unavailable_tracks(logger=None):
    from utils.db.blocklist import blocklist_albums_for_unavailable_tracks as _real_blocklist_albums_for_unavailable_tracks
    return _real_blocklist_albums_for_unavailable_tracks(logger)

def fetch_collection(source_name, logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.collections.cache_queries.fetch_collection."""
    from utils.collections.cache_queries import fetch_collection as _fetch_collection

    return _fetch_collection(source_name, logger, include_blocklisted)

def validate_sync_integrity(original_tracks, synced_tracks, logger):
    """Compatibility wrapper for utils.collections.sync.validate_sync_integrity."""
    from utils.collections.sync import validate_sync_integrity as _validate_sync_integrity

    return _validate_sync_integrity(original_tracks, synced_tracks, logger)

def sync_to_collections(tracklist, logger, collection_name=None):
    """Compatibility wrapper for utils.collections.sync.sync_to_collections."""
    from utils.collections.sync import sync_to_collections as _sync_to_collections

    return _sync_to_collections(tracklist, logger, collection_name)

def get_unprocessed_track_ids(logger=None, include_blocklisted=False):
    """
    Retrieves all track IDs from the database that have not yet been 
    enriched with metadata.
    """
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

def get_unprocessed_album_ids(logger=None, include_blocklisted=False):
    """
    Retrieves all album IDs from the database that have not yet been 
    enriched with metadata OR have not completed genre mapping.
    """
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

def reset_album_genres_by_track_ids(track_ids, logger=None):
    """
    Resets genre_mapped flag to 0 for albums associated with tracks missing genre mappings.
    """
    if not track_ids:
        if logger:
            logger.debug("No track IDs provided. Skipping album genre reset.")
        return 0

    if logger:
        logger.debug(f"Resetting album genre mappings for tracks_missing_genres_count={len(track_ids)}.")
    
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

def update_unprocessed(client,logger):
    """
    Identify and process tracks/albums that need metadata and genre mapping.
    """
    # Process unprocessed tracks
    unprocessed = get_unprocessed_track_ids(logger)
    if len(unprocessed) > 0:
        logger.info(f"Fetching metadata for {len(unprocessed)} new tracks...")
        unprocessed = get_tracks(client,logger,"database","tracks","null",unprocessed)
        logger.debug(f"Metadata fetched, updating database with {len(unprocessed)} records.")
        update_track_metadata(unprocessed,logger)
    # Track metadata committed — safe exit point before album enrichment begins.
    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after track enrichment. Deferring album enrichment to next run.")
        return
    else:
        unprocessed = get_unprocessed_track_ids(logger)
        if len(unprocessed) > 0:
            logger.warning(f"Metadata enrichment finished but tracks are missing metadata. Expecting 0, got {len(unprocessed)}")
    

    # Process unprocessed albums
    sync_missing_albums_to_table(logger)
    sync_missing_artists_to_table(logger)
    unprocessed_album = get_unprocessed_album_ids(logger)
    
    if len(unprocessed_album) > 0:
        logger.info(f"Fetching metadata for {len(unprocessed_album)} new albums...")
        unprocessed_album = get_albums(client, logger, identifier="database", album_ids=unprocessed_album)
        logger.debug(f"Metadata fetched, updating database with {len(unprocessed_album)} records.")
        update_album_metadata(unprocessed_album, logger)
    # Album metadata committed — safe exit point before genre mapping cascades.
    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after album enrichment. Deferring genre mapping to next run.")
        return
    else:
        unprocessed_album = get_unprocessed_album_ids(logger)
        if len(unprocessed_album) > 0:
            logger.warning(f"Metadata enrichment finished but albums are missing metadata. Expecting 0, got {len(unprocessed_album)}")

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

def update_tracks_partial_batch(track_list, logger=None):
    """
    Updates multiple tracks using the keys present in the first dictionary.
    """
    if not track_list:
        return

    sample_track = track_list[0]
    update_keys = [k for k in sample_track.keys() if k != 'id']

    if logger:
        logger.debug(
            f"Refreshing partial track stats for track_count={len(track_list)} with update_fields={update_keys}."
        )

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

        # Shared post-write safeguard: both partial/full paths rely on DB state only.
        try:
            blocklist_albums_for_unavailable_tracks(logger)
        except Exception as safeguard_error:
            if logger:
                logger.warning(
                    f"Safeguard blocklist pass failed after partial track update: {safeguard_error}"
                )
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Partial batch update failed: {e}")
        raise

def update_track_metadata(track_list, logger=None):
    """
    Updates the tracks table with full metadata fetched from the Deezer API.
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

        # Shared post-write safeguard: both partial/full paths rely on DB state only.
        try:
            blocklist_albums_for_unavailable_tracks(logger)
        except Exception as safeguard_error:
            if logger:
                logger.warning(
                    f"Safeguard blocklist pass failed after full track metadata update: {safeguard_error}"
                )
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Metadata update failed: {e}")
            logger.exception("Stack trace for track metadata update error:")
        raise

def update_album_metadata(album_list, logger=None):
    """
    Updates the albums table with full metadata fetched from the Deezer API.
    Captures complete album information including covers, genres, and metadata.
    """
    if logger:
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

def populate_album_genres(album_list, logger=None):
    """
    Populates the genres table with unique genres from the Deezer API response,
    and creates many-to-many relationships in the album_genres junction table.
    """
    if logger:
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
            
            total_enriched_albums = len(enriched_album_ids)
            for album_position, album_id in enumerate(enriched_album_ids, start=1):
                if shutdown_event.is_set():
                    if logger:
                        logger.debug("Shutdown acknowledged during per-album track-genre backfill. Remaining albums deferred to next run.")
                    break
                try:
                    populate_track_genres_for_album(
                        album_id,
                        logger,
                        album_position=album_position,
                        album_total=total_enriched_albums,
                    )
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

def populate_track_genres(logger=None):
    """
    Populates the track_genres table by inheriting genres from albums.
    """
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

def populate_track_genres_for_album(album_id, logger=None, album_position=None, album_total=None):
    """
    Populates track_genres for a specific album.   
    """
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            progress_suffix = ""
            if album_position is not None and album_total is not None:
                progress_suffix = f" ({album_position}/{album_total})"
            
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
                    logger.debug(
                        f"Album {album_id}{progress_suffix} has no genres to populate. "
                        f"Marked tracks as genre_mapped=1."
                    )
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
                logger.debug(
                    f"Populated {rows_affected} track-genre relationships for album {album_id}{progress_suffix}, "
                    f"marked {tracks_marked} tracks as genre_mapped=1"
                )
            
            return rows_affected
    
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to populate track genres for album {album_id}: {e}")
        raise

def get_albums_missing_genres(logger=None, include_blocklisted=False):
    """
    Retrieves all album IDs that have not completed genre mapping.
    """
    if logger:
        logger.debug(f"Querying albums missing genre mappings (include_blocklisted={include_blocklisted}).")

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

def get_tracks_missing_genres(logger=None, include_blocklisted=False):
    """
    Retrieves all track IDs that have not completed genre mapping.
    """
    if logger:
        logger.debug(f"Querying tracks missing genre mappings (include_blocklisted={include_blocklisted}).")

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

def update_albums_partial_batch(album_list, logger=None):
    """
    Updates multiple albums with refreshable fields only (fans, available, date_cached).
    Used for periodic stats refreshing without full metadata fetch.
    """
    if not album_list:
        return

    if logger:
        logger.debug(f"Refreshing partial album stats for album_count={len(album_list)}.")

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

def get_unique_album_ids_from_tracks(logger=None):
    """
    Retrieves all unique album IDs from the tracks table where album_id is not NULL.
    Returns a set of album IDs.
    """
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

def get_missing_album_ids(logger=None):
    """
    Identifies album IDs that exist in the tracks table but are missing from the albums table.
    Returns a set of missing album IDs.
    """
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

def get_missing_artist_ids(logger=None):
    """
    Identifies artist IDs referenced by tracks/albums that are missing from the artists table.
    Returns a set of missing artist IDs.
    """
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

def sync_missing_albums_to_table(logger=None):
    """
    Identifies missing album IDs from tracks table and inserts stub records into albums table.
    Stub records contain only the album ID; other fields will be populated during metadata enrichment.
    """
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

def sync_missing_artists_to_table(logger=None):
    """
    Identifies missing artist IDs from tracks/albums and inserts stub records into artists table.
    Stub records contain only the artist ID; other fields will be populated during enrichment.
    """
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

def get_expired_track_ids(logger=None, include_blocklisted=False):
    """
    Returns a list of track IDs where date_cached is older than n days. Should ignore unprocessed (new) ids.
    """
    track_stats_refresh=get_global_value("track_stats_refresh",default = 90)
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

def is_collection_cached(source_name, config, logger=None):
    """Compatibility wrapper for utils.collections.cache_queries.is_collection_cached."""
    from utils.collections.cache_queries import is_collection_cached as _is_collection_cached

    return _is_collection_cached(source_name, config, logger)

def fetch_entities_by(table_name, column_name, operator, values, return_ids_only=False, logger=None):
    """
    General-purpose fetch for entities from a table by column and operator.
    - table_name: str, e.g. 'tracks'
    - column_name: str, e.g. 'id'
    - operator: str, '=', 'IN', etc.
    - values: single value or list of values
    - return_ids_only: if True, return only the id column; else, return all columns
    Returns a list of dicts (all columns) or a list of ids (if return_ids_only).
    """
    norm_operator = _normalize_operator(operator)
    if logger:
        logger.debug(f"Query database for table_name={table_name}, column_name={column_name}, operator={norm_operator}, values={values}, return_ids_only={return_ids_only}")
    if not table_name or not column_name or not norm_operator or values is None:
        return []
    if norm_operator == 'IN':
        if not isinstance(values, (list, tuple, set)) or not values:
            return []
        placeholders = ','.join('?' * len(values))
        where_clause = f"{column_name} IN ({placeholders})"
        params = list(values)
    else:
        where_clause = f"{column_name} {norm_operator} ?"
        params = [values]
    select_cols = 'id' if return_ids_only else '*'
    query = f"SELECT {select_cols} FROM {table_name} WHERE {where_clause}"
    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if return_ids_only:
                result = [row['id'] for row in rows]
                if logger:
                    logger.debug(f"Returning IDs: {result[:5]}{'...' if len(result) > 5 else ''}")
            else:
                result = [dict(row) for row in rows]
                if logger and logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Returning dict. Sample: {result[0] if result else None}")
            if logger and result:
                logger.debug(f"Fetched {len(result)} rows from {table_name} where {column_name} {operator} {values}.")
            return result
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to fetch from {table_name} by {column_name} {operator}: {e}")
        return []

def _normalize_operator(operator):
    """
    Maps common aliases to standard SQL operators.
    """
    if not operator:
        return '='
    op = operator.strip().upper()
    # Map common aliases
    aliases = {
        'EQ': '=',
        'EQUALS': '=',
        'IS': '=',
        'NE': '!=',
        'NOT': '!=',
        'NEQ': '!=',
        'GT': '>',
        'LT': '<',
        'GTE': '>=',
        'GE': '>=',
        'LTE': '<=',
        'LE': '<=',
        'IN': 'IN',
        'NOT IN': 'NOT IN',
        'LIKE': 'LIKE',
        'ILIKE': 'LIKE',  # SQLite doesn't support ILIKE
    }
    return aliases.get(op, op)