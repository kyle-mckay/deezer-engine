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
import os
import json
import re
import random
import logging
from datetime import datetime
from utils.deezer_auth import get_authenticated_session
from utils.infrastructure.paths import get_cache_dir
from utils.collections import handle_cached_data, get_collection_name
from utils.config_loader import get_global_value

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer smarttracklists with local caching.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        list_name = source_data[0].get('name')
        arl = config.get('config', {}).get('arl_token')
        
        # Security: Mask ARL in debug logs
        masked_arl = f"{arl[:6]}...{arl[-6:]}" if arl else "None"
        logger.debug(f"Params: name='{list_name}', retention={retention_hrs}h, arl={masked_arl}")
        logger.debug(f"SmartTracklist source start: name='{list_name}', retention={retention_hrs}h")

        cache_file = str(get_cache_dir() / f"smart_{list_name}.json")

        logger.info(f"Fetching tracks for smarttracklist: '{list_name}'...")

        # Get collection name for database caching
        collection_name = get_collection_name(logger, "smarttracklist", name=list_name)

        def fetch_smart_list():
            """Internal logic for live retrieval when cache is invalid."""
            logger.debug(f"Cache miss for smarttracklist '{list_name}'. Starting live retrieval...")
            
            warm_url = f"https://www.deezer.com/us/smarttracklist/{list_name}"
            logger.debug(f"SmartTracklist live fetch start: warm_url='{warm_url}'")
            session, api_token = get_authenticated_session(arl, logger, warm_url)
            
            if not session or not api_token:
                logger.error(f"Auth failed for {list_name}: Session or API token missing.")
                return []

            # Logic Tracing: Scraping for internal IDs
            page_response = session.get(warm_url)
            page_text = page_response.text
            
            real_id_match = re.search(r'"SMART_TRACKLIST":\{.*?"id":"([^"]+)"', page_text)
            target_id = real_id_match.group(1) if real_id_match else list_name.replace('-', '_')
            logger.debug(f"Resolved Internal ID for {list_name}: {target_id}")

            fetch_strategies = [
                ("deezer.pageSmartTracklist", {"smartTracklist_id": target_id, "tab": 0}),
                ("song.getListData", {"sng_ids": [], "type": "smarttracklist", "id": target_id})
            ]

            track_ids = []
            selected_method = "none"
            for method, payload in fetch_strategies:
                cid = random.randint(100000000, 999999999)
                gw_url = f"https://www.deezer.com/ajax/gw-light.php?method={method}&input=3&api_version=1.0&api_token={api_token}&cid={cid}"
                try:
                    logger.debug(f"Attempting Gateway method: {method}")
                    r = session.post(gw_url, data=json.dumps(payload)).json()
                    items = r.get('results', {}).get('data', [])
                    if items:
                        track_ids = [str(i.get('SNG_ID') or i.get('id')) for i in items]
                        if track_ids:
                            selected_method = method
                            logger.debug(f"Success: {len(track_ids)} tracks found via {method}")
                            break
                except Exception as e:
                    logger.debug(f"Method {method} failed: {e}")
                    continue

            # FAILSAFE: Direct HTML Scrape
            if not track_ids:
                logger.debug(f"AJAX methods failed for {list_name}. Falling back to Regex scrape.")
                track_ids = re.findall(r'"SNG_ID":"?(\d+)"?', page_text)
                if track_ids:
                    selected_method = "regex_fallback"

            if not track_ids:
                logger.error(f"Failed to find any tracks for '{list_name}' after trying all strategies.")
                return []

            # Deduplicate and format
            track_ids = list(dict.fromkeys(track_ids))
            tracks = []
            date_time = datetime.now().isoformat()
            
            for tid in track_ids:
                tracks.append({
                    'id': str(tid),
                    'collection': f"smarttracklist__{list_name}",
                    'date_cached': date_time
                })
            
            logger.debug(f"Sample Track IDs from source: {track_ids[:5]}")
            logger.debug(
                f"SmartTracklist live fetch end: method={selected_method}, unique_ids={len(track_ids)}"
            )
            return tracks

        # Execute via Cache Manager (with database collection support)
        results = handle_cached_data(cache_file, retention_hrs, logger, fetch_smart_list, "smarttracklist", collection_name=collection_name)
        
        # Consolidated INFO: One line for the user
        logger.debug(f"Loaded {len(results)} tracks from SmartTracklist '{list_name}'.")
        logger.debug(f"SmartTracklist source end: name='{list_name}', returned={len(results)}")
        return results

    except Exception as e:
        logger.error(f"SmartTracklist execution failed for '{list_name}': {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []