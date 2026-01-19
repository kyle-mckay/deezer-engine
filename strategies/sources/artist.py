import re
import logging
from utils.paths import get_cache_dir 
from utils.deezer_auth import get_tracks
from utils.cache_manager import handle_cached_data
from utils.config_loader import get_global_value
import strategies.sources.album as album_strategy 

def get_sanitized_name(title):
    return re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer artist by iterating through their albums.
    """
    logger.debug("------ sources.artist START ------")
    artist_id = source_data.get('id')
    retention_hrs = source_data.get('retention', get_global_value('retention', default = 0))
    
    if not artist_id:
        logger.error("Source type 'artist' requires an 'id'.")
        return []

    # Get artist name and data
    try:
        artist = client.get_artist(artist_id)
        albums = artist.get_albums()
        logger.info(f"Found {len(albums)} albums for artist: '{artist.name}'")
    except Exception as e:
        logger.error(f"Error fetching artist metadata for {artist_id}: {e}")
        return []

    artist_tracks = []

    for i, album_obj in enumerate(albums, start=1):
        logger.debug(f"Processing album {i}/{len(albums)}: '{album_obj.title}'")
        
        album_payload = {
            'id': album_obj.id,
            'retention': source_data.get('retention', get_global_value('retention', default = 0))
        }
        
        # Call the album strategy and extend our track list
        tracks = album_strategy.run(client, config, logger, album_payload)
        artist_tracks.extend(tracks)
    
    logger.debug("------ sources.artist END ------")
    return artist_tracks