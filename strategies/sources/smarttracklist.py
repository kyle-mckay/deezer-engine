import os
import json
import re
import random
import logging
from utils.deezer_auth import get_authenticated_session
from utils.paths import get_cache_dir
from utils.cache_manager import handle_cached_data

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer smarttracklists with local caching.
    source_data:
      - id: str (The numeric playlist ID)
      - retention: int (hours to keep cache, 0 for live)
    """
    list_name = source_data.get('name')
    retention_hrs = source_data.get('retention', 0)
    arl = config.get('config', {}).get('arl_token')
    
    cache_file = str(get_cache_dir() / f"smart_{list_name}.json")

    def fetch_smart_list():
        # called by handle_cached_data if cache is invalid/missing
        warm_url = f"https://www.deezer.com/us/smarttracklist/{list_name}"
        session, api_token = get_authenticated_session(arl, logger, warm_url)
        
        if not session or not api_token:
            logger.error(f"Authentication utility failed to provide a session for {list_name}")
            return []
        # Identify the Internal ID via Scrape
        page_response = session.get(warm_url)
        page_text = page_response.text
        
        real_id_match = re.search(r'"SMART_TRACKLIST":\{.*?"id":"([^"]+)"', page_text)
        target_id = real_id_match.group(1) if real_id_match else list_name.replace('-', '_')

        # Universal Fetch Strategies
        fetch_strategies = [
            ("deezer.pageSmartTracklist", {"smartTracklist_id": target_id, "tab": 0}),
            ("song.getListData", {"sng_ids": [], "type": "smarttracklist", "id": target_id})
        ]

        logger.info(f"Fetching songs for '{list_name}'...")
        track_ids = []
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

        # FAILSAFE: Direct HTML Scrape
        if not track_ids:
            logger.debug(f"Gateway methods returned empty for {list_name}, attempting direct HTML regex scrape...")
            # This searches for "SNG_ID":"12345" inside the raw page HTML
            track_ids = re.findall(r'"SNG_ID":"?(\d+)"?', page_text)

        if not track_ids:
            logger.error(f"Could not find any tracks for '{list_name}'")
            return []

        # Deduplicate and Fetch full metadata
        track_ids = list(dict.fromkeys(track_ids))
        tracks = []
        for track_id in track_ids:
            try:
                track = client.get_track(track_id)
                tracks.append({
                    'id': str(track.id),
                    'title': getattr(track, 'title', 'Unknown'),
                    'unseen': getattr(track, 'unseen', False),
                    'duration': getattr(track, 'duration', 0),
                    'rank': getattr(track, 'rank', 0),
                    'explicit_lyrics': getattr(track, 'explicit_lyrics', False),
                    'artist': track.artist.name if hasattr(track, 'artist') else 'Unknown',
                    'album': track.album.title if hasattr(track, 'album') else 'Unknown',
                })
            except Exception as e:
                logger.debug(f"Could not fetch metadata for track {track_id}: {e}")
            
        
        return tracks

    # handle_cached_data will manage the file check, the fetch, and the write-to-disk
    return handle_cached_data(cache_file,retention_hrs,logger,fetch_smart_list,"smarttracklist"
    )