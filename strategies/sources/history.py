import json
import random
import time
from datetime import datetime
from utils.deezer_auth import get_authenticated_session
from utils.config_loader import get_global_value
from utils.cache_manager import get_collection_name
from utils.paths import get_data_dir

def get_deezer_history(limit, logger):
    """
    Fetches history using the exact parameters found in your network logs.
    """
    # Setup auth
    arl = get_global_value('arl_token', None)
    if not arl:
        logger.error(f"Unable to fetch history, no arl token available")
        return []
    
    warm_url = "https://www.deezer.com/en/profile/me/history"
    session, api_token = get_authenticated_session(arl, logger, warm_url)
    
    if not session or not api_token:
        raise Exception("Authentication failed.")

    # 2. Use method and parameters seen in HAR file when visiting `https://www.deezer.com/profile/me/history`
    # Method from logs: user.getSongsHistory 
    cid = random.randint(100000000, 999999999)
    method = "user.getSongsHistory"
    
    gw_url = (
        f"https://www.deezer.com/ajax/gw-light.php?"
        f"method={method}&input=3&api_version=1.0"
        f"&api_token={api_token}&cid={cid}"
    )

    # Body from logs: {"nb": 40, "start": 0} 
    payload = {
        "nb": limit, # Number of tracks to fetch 
        "start": 0
    }
    

    # Format response
    response = session.post(gw_url, data=json.dumps(payload))
    resp_json = response.json()

    # Return nested tracks
    return resp_json.get('results', {}).get('data', [])

def run(client, config, logger, source_data):
    """
    Fetches tracks from your listen history: https://www.deezer.com/en/profile/me/history
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        
        # Pull config keys
        source_type = source_data[0].get('type').lower()
        source_retention = source_data[0].get('retention', get_global_value('retention', 0))
        source_lookback = source_data[0].get('lookback', get_global_value('history_lookback', 14))
        source_limit = min(source_data[0].get('limit', get_global_value('history_limit', 100)), 100)
        
        collection = get_collection_name(logger, source_type, None, None)

        history_tracks = get_deezer_history(source_limit, logger)
        if not history_tracks:
            logger.info("Fetched 0 items from history.")
            return []

        # Calculate the cutoff timestamp
        current_ts = int(time.time())
        cutoff_ts = current_ts - (int(source_lookback) * 86400)

        filtered_tracks = []
        date_time = datetime.now().isoformat()

        for item in history_tracks:
            # Get the timestamp from the track metadata
            track_ts = int(item.get('TS', 0))

            # Only append if the track was played after the cutoff
            if track_ts >= cutoff_ts:
                filtered_tracks.append({
                    'id': str(item.get('SNG_ID')),
                    'collection': collection,
                    'date_cached': date_time
                })
        
        if not filtered_tracks:
            logger.info(f"Fetched 0 items from history after filtering by lookback ({source_lookback})")
            return []
        
        # Provide feedback on how many were filtered out by age
        filtered_count = len(history_tracks) - len(filtered_tracks)
        logger.info(f"Fetched {len(filtered_tracks)} tracks from history within the last {source_lookback} days.")
        logger.debug(f"Limit count: {len(history_tracks)}, Filtered count: {len(filtered_tracks)}, Difference: {filtered_count} removed.")
        
        return filtered_tracks

    except Exception as e:
        logger.error(f"History execution failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []