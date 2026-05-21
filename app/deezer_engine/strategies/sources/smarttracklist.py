# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime
from utils.collections import get_collection_name
from utils.config import get_global_value
from utils.api.playlist import gw_post
from strategies.sources.track import run as fetch_enriched_tracks

# Headers returned from smarttracklists:
# smarttracklists delegates to `track.py` with the extracted id's, so returned rows follow the Track payload shape.


def requires_metadata(source_data=None):
    return False


def _fetch_smarttracklist_tracks(client, logger, list_name, collection_name):
    """Fetch shallow smarttracklist rows via deezer.pageSmartTracklist."""
    logger.debug(f"SmartTracklist live fetch start: name='{list_name}', collection='{collection_name}'")

    try:
        results = gw_post(client, "deezer.pageSmartTracklist", {
            "smarttracklist_id": list_name,
            "lang": "en",
        }, logger)
    except RuntimeError as e:
        logger.error(f"Failed to fetch smarttracklist '{list_name}': {e}")
        return []

    items = results.get('SONGS', {}).get('data', [])
    if not items:
        logger.error(f"No tracks returned for smarttracklist '{list_name}'.")
        return []

    date_time = datetime.now().isoformat()
    unique_ids = list(dict.fromkeys(str(item['SNG_ID']) for item in items if item.get('SNG_ID')))
    tracks = [{'id': tid, 'collection': collection_name, 'date_cached': date_time} for tid in unique_ids]

    logger.debug(f"Sample Track IDs from source: {unique_ids[:5]}")
    logger.debug(f"SmartTracklist live fetch end: unique_ids={len(unique_ids)}")
    return tracks


def run(client, config, logger, source_data):
    """
    Fetches tracks from a specific Deezer smarttracklist with local caching.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        name_value = source_data[0].get('name')

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

        logger.debug(f"SmartTracklist source start: names='{normalized_list_names}', retention={retention_hrs}h")

        all_results = []
        for list_name in normalized_list_names:
            logger.info(f"Fetching tracks for smarttracklist: '{list_name}'...")
            collection_name = get_collection_name(logger, "smarttracklist", name=list_name)
            shallow_tracks = _fetch_smarttracklist_tracks(client, logger, list_name, collection_name)
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

        logger.debug(f"Loaded {len(all_results)} track IDs from SmartTracklists {normalized_list_names}.")
        logger.debug(f"SmartTracklist source end: names='{normalized_list_names}', returned={len(all_results)}")

        return all_results or []

    except Exception as e:
        logger.error(f"SmartTracklist execution failed for '{list_name}': {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []
