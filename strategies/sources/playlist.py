import os
import json
import time

def run(client, config, logger, source_data):
        """
        Retrieve track IDs from a Deezer playlist.
        source_data keys:
            - id: str (numeric playlist ID)
            - retention: int (optional cache retention hours)
        """
    playlist_id = source_data.get('id')
    retention_hrs = source_data.get('retention', 24) # Default retention: 24 hours for playlists
    
    if not playlist_id:
        logger.error("Source type 'playlist' requires an 'id'.")
        return []

    cache_file = f"./cache/playlist_{playlist_id}.json"

    # Use cached IDs when still within the retention window
    if retention_hrs > 0 and os.path.exists(cache_file):
        file_age = (time.time() - os.path.getmtime(cache_file)) / 3600
        if file_age < retention_hrs:
            logger.debug(f"Using cached playlist {playlist_id}")
            with open(cache_file, 'r') as f:
                return json.load(f)

    # Fetch live data from the Deezer API
    try:
        # `get_playlist` yields a PaginatedList that auto-paginates when iterated
        playlist = client.get_playlist(playlist_id)

        # Keep only track IDs
        track_ids = [track.id for track in playlist.get_tracks()]
        
        # Save IDs to cache for future runs
        with open(cache_file, 'w') as f:
            json.dump(track_ids, f)
        
        logger.info(f"Successfully fetched {len(track_ids)} tracks.")
        return track_ids
    except Exception as e:
        logger.error(f"Error fetching playlist {playlist_id}: {e}")
        return []