# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import re
import random
from datetime import datetime
from utils.api.auth import get_authenticated_session
from utils.collections import get_collection_name
from utils.config import get_global_value
from strategies.sources.track import run as fetch_enriched_tracks

# Headers returnd from smarttracklists:
# smarttracklists delegates to `track.py` with the extracted id's, so returned rows follow the Track payload shape.


def requires_metadata(source_data=None):
    """
    No requirements to pull beyond user ID and arl for authentication
    """
    return False


def _fetch_smarttracklist_tracks(arl, logger, list_name, collection_name):
    """Fetch shallow smarttracklist rows already tagged with the target collection."""
    logger.debug(f"SmartTracklist live fetch start: name='{list_name}', collection='{collection_name}'")

    warm_url = f"https://www.deezer.com/us/smarttracklist/{list_name}"
    session, api_token = get_authenticated_session(arl, logger, warm_url)

    if not session or not api_token:
        logger.error(f"Auth failed for {list_name}: Session or API token missing.")
        return []

    page_response = session.get(warm_url)
    page_text = page_response.text

    real_id_match = re.search(r'"SMART_TRACKLIST":\{.*?"id":"([^"]+)"', page_text)
    target_id = real_id_match.group(1) if real_id_match else list_name.replace('-', '_')
    logger.debug(f"Resolved Internal ID for {list_name}: {target_id}")

    fetch_strategies = [
        ("deezer.pageSmartTracklist", {"smartTracklist_id": target_id, "tab": 0}),
        ("song.getListData", {"sng_ids": [], "type": "smarttracklist", "id": target_id}),
    ]

    track_ids = []
    selected_method = "none"
    for method, payload in fetch_strategies:
        cid = random.randint(100000000, 999999999)
        gw_url = (
            f"https://www.deezer.com/ajax/gw-light.php?method={method}&input=3&api_version=1.0"
            f"&api_token={api_token}&cid={cid}"
        )
        try:
            logger.debug(f"Attempting Gateway method: {method}")
            response = session.post(gw_url, data=json.dumps(payload)).json()
            items = response.get('results', {}).get('data', [])
            if items:
                track_ids = [str(item.get('SNG_ID') or item.get('id')) for item in items]
                if track_ids:
                    selected_method = method
                    logger.debug(f"Success: {len(track_ids)} tracks found via {method}")
                    break
        except Exception as exc:
            logger.debug(f"Method {method} failed: {exc}")
            continue

    if not track_ids:
        logger.debug(f"AJAX methods failed for {list_name}. Falling back to Regex scrape.")
        track_ids = re.findall(r'"SNG_ID":"?(\d+)"?', page_text)
        if track_ids:
            selected_method = "regex_fallback"

    if not track_ids:
        logger.error(f"Failed to find any tracks for '{list_name}' after trying all strategies.")
        return []

    unique_track_ids = list(dict.fromkeys(track_ids))
    date_time = datetime.now().isoformat()
    tracks = [
        {
            'id': str(track_id),
            'collection': collection_name,
            'date_cached': date_time,
        }
        for track_id in unique_track_ids
    ]

    logger.debug(f"Sample Track IDs from source: {unique_track_ids[:5]}")
    logger.debug(
        f"SmartTracklist live fetch end: method={selected_method}, unique_ids={len(unique_track_ids)}"
    )
    return tracks

def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer smarttracklists with local caching.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        # Extract configuration
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        name_value = source_data[0].get('name')
        arl = config.get('config', {}).get('arl_token')

        if name_value is None:
            logger.error("Source type 'smarttracklist' failed: missing 'name' in configuration.")
            return []

        list_names = name_value if isinstance(name_value, list) else [name_value]
        normalized_list_names = []
        for raw_name in list_names:
            if raw_name is None:
                logger.warning("SmartTracklist source received null name in list input. Skipping entry.")
                continue

            list_name = str(raw_name).strip()
            if not list_name:
                logger.warning("SmartTracklist source received empty name in list input. Skipping entry.")
                continue

            normalized_list_names.append(list_name)

        if not normalized_list_names:
            logger.warning("SmartTracklist source has no valid names after filtering invalid list entries.")
            return []

        # Security: Mask ARL in debug logs
        masked_arl = f"{arl[:6]}...{arl[-6:]}" if arl else "None"
        logger.debug(f"Params: names='{normalized_list_names}', retention={retention_hrs}h, arl={masked_arl}")
        logger.debug(f"SmartTracklist source start: names='{normalized_list_names}', retention={retention_hrs}h")

        all_results = []
        for list_name in normalized_list_names:
            logger.info(f"Fetching tracks for smarttracklist: '{list_name}'...")
            collection_name = get_collection_name(logger, "smarttracklist", name=list_name)
            shallow_tracks = _fetch_smarttracklist_tracks(arl, logger, list_name, collection_name)
            collected_ids = list(
                dict.fromkeys(
                    str(track.get('id')).strip()
                    for track in shallow_tracks
                    if track.get('id') is not None and str(track.get('id')).strip()
                )
            )
            if not collected_ids:
                logger.debug(f"No track IDs resolved for smarttracklist '{list_name}'. Skipping metadata delegation.")
                continue

            results = fetch_enriched_tracks(client, config, logger, [{
                'id': collected_ids,
                'override_collection': collection_name,
                'retention': retention_hrs,
            }]) or []
            if results:
                all_results.extend(results)

        # Consolidated INFO: One line for the user
        logger.debug(f"Loaded {len(all_results)} track IDs from SmartTracklists {normalized_list_names}.")
        logger.debug(f"SmartTracklist source end: names='{normalized_list_names}', returned={len(all_results)}")

        if not all_results:
            return []
        return all_results

    except Exception as e:
        logger.error(f"SmartTracklist execution failed for '{list_name}': {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []