import re
import logging
from utils.paths import get_cache_dir 
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data
from utils.config_loader import get_global_value
import strategies.sources.album as album_strategy 

def get_sanitized_name(title):
    # Internal logic tracing for string manipulation
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer artist by iterating through their albums.
    """
    logger.debug(">>> START: strategies.sources.artist.run")
    
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        artist_id = source_data[0].get('id')
        
        if not artist_id:
            logger.error("Source type 'artist' failed: missing 'id' in configuration.")
            return []

        # Logic Tracing: Artist metadata
        try:
            artist = client.get_artist(artist_id)
            albums = artist.get_albums()
            total_albums = len(albums)
            logger.debug(f"Artist: '{artist.name}' | Total albums found: {total_albums}")
        except Exception as e:
            logger.error(f"Failed to retrieve artist metadata for {artist_id}: {e}")
            logger.debug("Stack trace:", exc_info=True)
            return []

        artist_tracks = []
        
        # Throttled Progress: We log a single INFO line before starting the loop
        logger.info(f"Processing {total_albums} albums for artist '{artist.name}'...")

        for i, album_obj in enumerate(albums, start=1):
            # Granular DEBUG: High-resolution trace for developer
            logger.debug(f"[{i}/{total_albums}] Dispatching to album strategy: '{album_obj.title}' (ID: {album_obj.id})")
            
            album_payload = {
                'id': album_obj.id,
                'retention': retention_hrs
            }
            
            # Delegate to existing logic
            tracks = album_strategy.run(client, config, logger, album_payload)
            artist_tracks.extend(tracks)

        logger.info(f"Successfully aggregated {len(artist_tracks)} tracks from artist '{artist.name}'.")

        # Duplicate tracks and create copy with `artist__<artist name>`
        logger.debug(f"Created duplicate record of tracks for arist collection")
        tracks = []
        sanitized_name = f"artist__{artist_id}"

        tracks = [
            {**track, 'collection': sanitized_name} 
            for track in artist_tracks
        ]
        artist_tracks.extend(tracks)

        # Consolidated INFO: Final result report

        # Data Samples
        if artist_tracks:
            sample_ids = [t.get('id') for t in artist_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        return artist_tracks

    except Exception as e:
        logger.error(f"Artist aggregation failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []
        
    finally:
        logger.debug("<<< END: strategies.sources.artist.run")