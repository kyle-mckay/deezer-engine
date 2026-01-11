import os
import json
import time
import re
import random
import logging
from utils.deezer_auth import get_authenticated_session

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer playlist with local caching.
    source_data:
      - id: str (The numeric playlist ID)
      - retention: int (hours to keep cache, 0 for live)
    """
    list_name = source_data.get('name')
    retention_hrs = source_data.get('retention', 0)
    arl = config.get('config', {}).get('arl_token')
    
    cache_file = f"./cache/smart_{list_name}.json"
    
    # 1. Cache Check Logic
    if retention_hrs > 0 and os.path.exists(cache_file):
        file_age = (time.time() - os.path.getmtime(cache_file)) / 3600
        if file_age < retention_hrs:
            logger.debug(f"Using cached smart list: {list_name} ({file_age:.1f}h old)")
            with open(cache_file, 'r') as f:  # <--- Added the missing 'with open'
                return json.load(f)

    # 2. Use Utility for Auth
    # We use the smarttracklist URL as the "warm up" to ensure the session is valid for this list
    warm_url = f"https://www.deezer.com/us/smarttracklist/{list_name}"
    session, api_token = get_authenticated_session(arl, logger, warm_url)
    
    if not session or not api_token:
        logger.error(f"Authentication utility failed to provide a session for {list_name}")
        return []

    try:
        track_ids = []
        # Identify the Internal ID via Scrape
        page_response = session.get(warm_url)
        page_text = page_response.text
        
        real_id_match = re.search(r'"SMART_TRACKLIST":\{.*?"id":"([^"]+)"', page_text)
        target_id = real_id_match.group(1) if real_id_match else list_name.replace('-', '_')

        # 3. Universal Fetch Strategies
        # Try the two methods discovered in your HAR files
        fetch_strategies = [
            ("deezer.pageSmartTracklist", {"smartTracklist_id": target_id, "tab": 0}),
            ("song.getListData", {"sng_ids": [], "type": "smarttracklist", "id": target_id})
        ]

        logger.info(f"Fetching songs for '{list_name}'...")
        for method, payload in fetch_strategies:
            cid = random.randint(100000000, 999999999)
            gw_url = f"https://www.deezer.com/ajax/gw-light.php?method={method}&input=3&api_version=1.0&api_token={api_token}&cid={cid}"
            try:
                r = session.post(gw_url, data=json.dumps(payload)).json()
                items = r.get('results', {}).get('data', [])
                if items:
                    track_ids = [str(i.get('SNG_ID') or i.get('id')) for i in items]
                    if track_ids:
                        logger.debug(f"Successfully retrieved tracks using {method}")
                        break
            except Exception:
                continue

        if track_ids:
            # Deduplicate while preserving order
            track_ids = list(dict.fromkeys(track_ids))
            
            os.makedirs("./cache", exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(track_ids, f)
            
            logger.info(f"Resolved {len(track_ids)} songs for '{list_name}'.")
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Track IDs for {list_name}: {track_ids}")
                
            return track_ids
        
        logger.error(f"Could not find any tracks for '{list_name}' in Gateway or HTML.")
        return []

    except Exception as e:
        logger.error(f"Source worker encountered an error for '{list_name}': {e}")
        return []