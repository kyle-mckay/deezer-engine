# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import logging
import random
import time
from datetime import datetime
from utils.api.auth import get_authenticated_session
from utils.config import get_global_value
from utils.collections import get_collection_name
from utils.infrastructure.paths import get_data_dir

def requires_metadata(source_data=None):
    """
    No requirements to pull beyond user ID and arl for authentication
    """
    return False

def get_deezer_history(limit, logger):
    """
    Fetches history using the exact parameters found in your network logs.
    """
    # Setup auth
    arl = get_global_value('arl_token', None)
    logger.debug(f"History fetch start: limit={limit}, has_arl={bool(arl)}")
    if not arl:
        logger.error(f"Unable to fetch history, no arl token available")
        return []
    
    warm_url = "https://www.deezer.com/en/profile/me/history"
    session, api_token = get_authenticated_session(arl, logger, warm_url)
    
    if not session or not api_token:
        raise Exception("Authentication failed.")

    logger.debug("History auth established. Preparing gateway request.")

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
    history_rows = resp_json.get('results', {}).get('data', [])
    logger.debug(f"History fetch end: status={response.status_code}, rows={len(history_rows)}")
    return history_rows

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
        logger.debug(
            f"History source start: type={source_type}, retention={source_retention}h, "
            f"lookback_days={source_lookback}, limit={source_limit}"
        )
        
        collection = get_collection_name(logger, source_type, None, None)

        history_tracks = get_deezer_history(source_limit, logger)
        logger.debug(f"History source raw rows fetched: {len(history_tracks)}")
        if not history_tracks:
            logger.info("Fetched 0 items from history.")
            logger.debug("History source end: no rows returned from API.")
            return []

        # Calculate the cutoff timestamp
        current_ts = int(time.time())
        cutoff_ts = current_ts - (int(source_lookback) * 86400)

        if logger and logger.isEnabledFor(logging.DEBUG):
            # Build timestamp diagnostics from raw history payload before lookback filtering.
            history_timestamps = []
            invalid_ts_count = 0
            for item in history_tracks:
                ts_value = item.get('TS')
                try:
                    ts_int = int(ts_value)
                    if ts_int > 0:
                        history_timestamps.append(ts_int)
                    else:
                        invalid_ts_count += 1
                except (TypeError, ValueError):
                    invalid_ts_count += 1

            if history_timestamps:
                earliest_playback_ts = min(history_timestamps)
                latest_playback_ts = max(history_timestamps)
                logger.debug(
                    "History source playback range (from API history rows): "
                    f"earliest_ts={earliest_playback_ts} ({datetime.fromtimestamp(earliest_playback_ts).isoformat()}), "
                    f"latest_ts={latest_playback_ts} ({datetime.fromtimestamp(latest_playback_ts).isoformat()}), "
                    f"cutoff_ts={cutoff_ts} ({datetime.fromtimestamp(cutoff_ts).isoformat()}), "
                    f"valid_ts_rows={len(history_timestamps)}, invalid_ts_rows={invalid_ts_count}"
                )
            else:
                logger.debug(
                    "History source playback range unavailable: no valid TS values found in API history rows "
                    f"(raw_rows={len(history_tracks)}, invalid_ts_rows={invalid_ts_count}, "
                    f"cutoff_ts={cutoff_ts} ({datetime.fromtimestamp(cutoff_ts).isoformat()}))"
                )

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
            logger.info(
                f"Found 0 songs played within the last {source_lookback} days in history."
            )
            logger.debug(
                f"History source end: raw={len(history_tracks)}, filtered=0, "
                f"lookback_days={source_lookback}"
            )
            return []
        
        # Provide feedback on how many were filtered out by age
        filtered_count = len(history_tracks) - len(filtered_tracks)
        logger.info(f"Fetched {len(filtered_tracks)} tracks from history within the last {source_lookback} days.")
        logger.debug(f"Limit count: {len(history_tracks)}, Filtered count: {len(filtered_tracks)}, Difference: {filtered_count} removed.")
        logger.debug(
            f"History source end: returning={len(filtered_tracks)}, removed_by_lookback={filtered_count}"
        )
        
        return filtered_tracks

    except Exception as e:
        logger.error(f"History execution failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []