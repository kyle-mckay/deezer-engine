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

import sqlite3
import json

def fetch_collection(source_name, logger=None):
    """
    Retrieves all tracks and their full metadata associated with a specific source.
    
    Args:
        source_name (str): The identifier (e.g., 'playlist__12345').
        logger: Logger instance.
        
    Returns:
        list[dict]: List of full track metadata dictionaries.
    """
    if logger:
        logger.debug(f"Database: Fetching full collection for source '{source_name}'")

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
                logger.debug(f"Database: Successfully fetched {len(collection_data)} tracks for '{source_name}'")
                
            return collection_data
            
    except Exception as e:
        if logger:
            logger.error(f"Database: Failed to fetch collection '{source_name}': {e}")
        return []

def sync_to_collections(tracklist, logger):
    """
    Parses a tracklist where each track contains its own source info.
    Inserts IDs into 'tracks' and maps them in 'collections'.
    """
    if not tracklist:
        logger.warning("No tracks provided for sync.")
        return
    
    # Use a set to handle unique pairs of (id, source) from the input
    unique_pairs = {(str(t['id']), t.get('collection', 'unknown')) for t in tracklist}
    unique_track_ids = {tid for tid, source in unique_pairs}

    logger.debug(f"Processing {len(unique_track_ids)} into collections cache.")

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
            logger.debug("Database sync successful.")

    except Exception as e:
        logger.error(f"Database sync failed: {e}")

def get_unprocessed_track_ids(logger=None):
    """
    Retrieves all track IDs from the database that have not yet been 
    enriched with metadata (where date_cached is NULL or empty).
    
    Returns:
        list[dict]: A list of track payloads, e.g., [{'id': 12345}, {'id': 67890}]
    """
    query = "SELECT id FROM tracks WHERE date_cached IS NULL OR date_cached = '';"
    
    try:
        with _get_connection() as conn:
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            
            # Map the rows to the requested payload format
            tracks_payload = [{'id': row['id']} for row in rows]
            
            if logger:
                logger.info(f"Database: Found {len(tracks_payload)} tracks requiring metadata enrichment.")
            
            return tracks_payload
            
    except Exception as e:
        if logger:
            logger.error(f"Failed to fetch unprocessed track IDs: {e}")
        return []

def update_track_metadata(track_list, logger=None):
    """
    Updates the tracks table with full metadata fetched from the Deezer API.
    Expects a list of dictionaries containing all metadata fields.
    """
    if not track_list:
        if logger:
            logger.warning("No metadata provided for update.")
        return

    # SQL query to update all fields based on the ID
    query = """
    UPDATE tracks SET
        readable = ?,
        title = ?,
        title_short = ?,
        title_version = ?,
        unseen = ?,
        isrc = ?,
        link = ?,
        share = ?,
        duration = ?,
        track_position = ?,
        disk_number = ?,
        rank = ?,
        release_date = ?,
        explicit_lyrics = ?,
        explicit_content_lyrics = ?,
        explicit_content_cover = ?,
        preview = ?,
        bpm = ?,
        gain = ?,
        available_countries = ?,
        contributors = ?,
        md5_image = ?,
        track_token = ?,
        artist_id = ?,
        album_id = ?,
        date_cached = ?
    WHERE id = ?;
    """

    # Mapping the dictionary keys to the tuple order in the query
    data_tuples = [
        (
            t.get('readable'),
            t.get('title'),
            t.get('title_short'),
            t.get('title_version'),
            t.get('unseen'),
            t.get('isrc'),
            t.get('link'),
            t.get('share'),
            t.get('duration'),
            t.get('track_position'),
            t.get('disk_number'),
            t.get('rank'),
            t.get('release_date'),
            t.get('explicit_lyrics'),
            t.get('explicit_content_lyrics'),
            t.get('explicit_content_cover'),
            t.get('preview'),
            t.get('bpm'),
            t.get('gain'),
            t.get('available_countries'), # Already JSON stringified in get_tracks
            t.get('contributors'),        # Already JSON stringified in get_tracks
            t.get('md5_image'),
            t.get('track_token'),
            t.get('artist_id'),
            t.get('album_id'),
            t.get('date_cached'),
            t.get('id')                   # For the WHERE clause
        )
        for t in track_list
    ]

    try:
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, data_tuples)
            conn.commit()
            if logger:
                logger.info(f"Database: Successfully updated metadata for {len(track_list)} tracks.")
    except Exception as e:
        if logger:
            logger.error(f"Database metadata update failed: {e}")
        raise


def is_collection_cached(source_name, config, logger=None):
    """
    Checks if a collection exists and was cached within the retention window.
    
    Returns:
        bool: True if valid cache exists, False if expired or missing.
    """

    retention_hrs = config.get('retention', get_global_value('retention', default = 0))
    # Query collections table against timestamps
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
                    logger.debug(f"Cache miss: No entry found for '{source_name}'")
                return False
            
            cache_time = datetime.fromisoformat(row['date_cached'])
            expiration_time = datetime.now() - timedelta(hours=retention_hrs)
            
            is_valid = cache_time > expiration_time
            
            if logger:
                status = "Valid" if is_valid else "Expired"
                logger.debug(f"Cache check for '{source_name}': {status} (Cached: {row['date_cached']})")
                
            return is_valid
            
    except Exception as e:
        if logger:
            logger.error(f"Error checking cache retention: {e}")
        return False