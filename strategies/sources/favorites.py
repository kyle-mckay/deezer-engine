import os
import json
import time

def run(client, config, logger, source_data):
        """
        Retrieve the user's favorite track IDs.
        source_data keys:
            - retention: int (optional cache retention hours)
        """
    user_id = config.get('config', {}).get('user_id')
    retention_hrs = source_data.get('retention', 0)
    
    # Set cache file path using the configured user id
    cache_file = f"./cache/favorites_{user_id}.json"

    # Use cached IDs when the cache is still within the retention window
    if retention_hrs > 0 and os.path.exists(cache_file):
        file_age_hrs = (time.time() - os.path.getmtime(cache_file)) / 3600
        if file_age_hrs < retention_hrs:
            logger.info(f"Using cached favorites (Age: {file_age_hrs:.1f}h)")
            with open(cache_file, 'r') as f:
                return json.load(f)

    # Fetch live data from the Deezer API
    logger.info(f"Fetching live favorites from Deezer API for User {user_id}...")
    try:
        # `get_user_tracks` yields a PaginatedList that auto-paginates when iterated
        user_tracks = client.get_user_tracks(user_id)

        # Keep only track IDs
        track_ids = [track.id for track in user_tracks]

        # Save IDs to cache for future runs
        with open(cache_file, 'w') as f:
            json.dump(track_ids, f)

        logger.info(f"Successfully fetched {len(track_ids)} tracks.")
        return track_ids

    except Exception as e:
        logger.error(f"Failed to fetch favorites: {e}")
        # If fetching fails, fall back to any existing cache (even if expired)
        if os.path.exists(cache_file):
            logger.warning("Falling back to expired cache due to API error.")
            with open(cache_file, 'r') as f:
                return json.load(f)
        raise e