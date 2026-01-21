import sqlite3
import logging
import json
from datetime import datetime, timedelta
from utils.database import get_db_path
from utils.config_loader import get_global_value

# Centralized static path
DB_PATH = get_db_path() 

def _get_connection():
    """Internal helper to provide a connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_collection(source_name, logger=None):
    """
    Retrieves all tracks and their full metadata associated with a specific source.
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.fetch_collection ({source_name})")

    # SQL JOIN: Get track metadata where the track exists in the specified collection
    query = """
    SELECT t.* FROM tracks t
    JOIN collections c ON t.id = c.track_id
    WHERE c.source_name = ?;
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

def sync_to_collections(tracklist, logger):
    """
    Parses a tracklist where each track contains its own source info.
    Inserts IDs into 'tracks' and maps them in 'collections'.
    """
    logger.debug(">>> START: utils.db_manager.sync_to_collections")
    if not tracklist:
        logger.debug("Sync skipped: No tracks provided in payload.")
        return
    
    # Use a set to handle unique pairs of (id, source) from the input
    unique_pairs = {(str(t['id']), t.get('collection', 'unknown')) for t in tracklist}
    unique_track_ids = {tid for tid, source in unique_pairs}

    logger.debug(f"DB: Syncing {len(unique_track_ids)} unique track IDs.")

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()

            # extracts (id, collection, date_cached) from the payload
            unique_pairs = {
                (
                    str(t['id']), 
                    t.get('collection', 'unknown'), 
                    t.get('date_cached')
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
            
            # Update 'collections' table
            collection_entries = [(tid, source, timestamp) for tid, source, timestamp in unique_pairs]
            cursor.executemany(
                "INSERT OR IGNORE INTO collections (track_id, source_name, date_cached) VALUES (?, ?, ?)", 
                collection_entries
            )

            conn.commit()
            logger.debug("DB: Transaction committed successfully.")

    except Exception as e:
        logger.error(f"DB Sync failed: {e}")
    finally:
        logger.debug("<<< END: utils.db_manager.sync_to_collections")

def get_unprocessed_track_ids(logger=None):
    """
    Retrieves all track IDs from the database that have not yet been 
    enriched with metadata.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_unprocessed_track_ids")

    query = "SELECT id FROM tracks WHERE date_cached IS NULL OR date_cached = '';"
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            # Map the rows to the requested payload format
            tracks_payload = [{'id': row['id']} for row in rows]
            
            if logger and len(tracks_payload) > 0:
                logger.info(f"Database: {len(tracks_payload)} tracks found requiring enrichment.")
            
            return tracks_payload
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Failed to check for unprocessed tracks: {e}")
        return []
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.get_unprocessed_track_ids")

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

    if not track_list:
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

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data_tuples)
            conn.commit()
            if logger:
                logger.info(f"Metadata enrichment complete for {len(track_list)} tracks.")
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Metadata update failed: {e}")
        raise
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.update_track_metadata")

def get_expired_track_ids(logger=None):
    """
    Returns a list of track IDs where date_cached is older than n days.
    """
    if logger:
        logger.debug(">>> START: utils.db_manager.get_expired_track_ids")

    track_stats_refresh=get_global_value("track_stats_refresh",default = 7)
    query = f"""
    SELECT id 
    FROM tracks 
    WHERE date_cached < datetime('now', '-{track_stats_refresh} days');
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

def is_collection_cached(source_name, config, logger=None):
    """
    Checks if a collection exists and was cached within the retention window.
    """
    if logger:
        logger.debug(f">>> START: utils.db_manager.is_collection_cached ({source_name})")

    retention_hrs = config.get('retention', get_global_value('retention', default = 0))
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
                logger.debug(f"Cache verify: {'Valid' if is_valid else 'Expired'} (Age: {cache_time})")
                
            return is_valid
            
    except Exception as e:
        if logger:
            logger.error(f"DB Error: Cache validation failed: {e}")
        return False
    finally:
        if logger:
            logger.debug("<<< END: utils.db_manager.is_collection_cached")