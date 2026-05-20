# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
from utils.collections import get_collection_name, is_collection_cached, fetch_collection, sync_to_collections
from utils.config import get_global_value


def _fetch_inject_tracks(client, config, logger, source_data):
    """Fetch tracks for an inject source, using cache when available."""
    source_type = source_data.get('type')
    source_id = source_data.get('id', None)
    source_name_val = source_data.get('name', None)
    collection_name = get_collection_name(logger, source_type, source_name_val, source_id)

    if collection_name != "unknown" and is_collection_cached(collection_name, source_data, logger):
        logger.debug(f"Inject source '{collection_name}' found in cache.")
        return fetch_collection(collection_name, logger)

    logger.debug(f"Inject source '{collection_name}' not cached. Fetching live.")
    module_path = f"strategies.sources.{source_type}"
    source_worker = importlib.import_module(module_path)
    tracks = source_worker.run(client, config, logger, source_data)
    sync_to_collections(tracks, logger)
    return tracks


def _build_groups(client, config, logger, inject_list):
    """Resolve each inject entry's source and initialise cursor state."""
    groups = []
    for entry in inject_list:
        source_data = entry.get('source')
        if not source_data:
            logger.warning("Interleave inject entry missing 'source'. Skipping.")
            continue

        source_type = source_data.get('type')
        source_id = source_data.get('id', None)
        source_name_val = source_data.get('name', None)
        collection_name = get_collection_name(logger, source_type, source_name_val, source_id)

        tracks = _fetch_inject_tracks(client, config, logger, source_data)
        for mod_data in entry.get('modifiers', []):
            mod_type = mod_data.get('type')
            try:
                mod_module = importlib.import_module(f"strategies.modifiers.{mod_type}")
                tracks = mod_module.run(client, config, logger, mod_data, tracks)
                logger.debug(f"Inject source '{collection_name}': applied modifier '{mod_type}' → {len(tracks)} tracks.")
            except Exception as e:
                logger.warning(f"Inject source '{collection_name}': modifier '{mod_type}' failed ({e}). Skipping.")
        every = max(1, int(entry.get('every', 1)))
        add = max(1, int(entry.get('add', 1)))
        global_default = get_global_value('interleave_continue_on_exhaust', False)
        continue_on_exhaust = entry.get('continue_on_exhaust', global_default)

        groups.append({
            'name': collection_name,
            'tracks': tracks,
            'every': every,
            'add': add,
            'continue_on_exhaust': continue_on_exhaust,
            '_cursor': 0,
            '_next_at': every,
            '_active': True,
        })
        logger.debug(
            f"Inject group loaded: source='{collection_name}', every={every}, add={add}, "
            f"tracks={len(tracks)}, continue_on_exhaust={continue_on_exhaust}"
        )
    return groups


def _get_batch(group):
    """Return the next inject batch for a group, respecting continue_on_exhaust."""
    if not group['_active']:
        return []

    tracks = group['tracks']
    cursor = group['_cursor']
    add = group['add']
    available = tracks[cursor:cursor + add]

    if not available:
        group['_active'] = False
        return []

    if len(available) < add:
        group['_active'] = False
        group['_cursor'] += len(available)  # consume the partial batch either way
        if group['continue_on_exhaust']:
            return available
        return []

    group['_cursor'] += add
    if group['_cursor'] >= len(tracks):
        group['_active'] = False
    return available


def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Interleaves tracks from inject sources into the current pipeline.

    For each inject entry: after every N origin tracks, M tracks from that
    source are inserted. When origin exhausts, remaining inject tracks are
    appended if top-level continue_on_exhaust is True (default).

    When the pipeline is empty the modifier acts as a simple append, loading
    all inject sources into the result in definition order.
    """
    inject_list = mod_data.get('inject', [])
    if not inject_list:
        logger.warning("Interleave modifier has no 'inject' entries. Returning pipeline unchanged.")
        return current_tracks

    global_default = get_global_value('interleave_continue_on_exhaust', False)
    top_continue = mod_data.get('continue_on_exhaust', global_default)

    groups = _build_groups(client, config, logger, inject_list)
    if not groups:
        logger.warning("Interleave modifier: all inject entries failed to load. Returning pipeline unchanged.")
        return current_tracks

    # Standalone / append mode — empty origin, just collect inject sources in order
    if not current_tracks:
        result = []
        for group in groups:
            result.extend(group['tracks'])
        logger.info(f"Action: Interleaved (empty origin): appended {len(result)} inject tracks.")
        return result

    result = []
    origin_consumed = 0
    origin_total = len(current_tracks)

    for track in current_tracks:
        result.append(track)
        origin_consumed += 1
        title = track.get('title', track.get('id', '?'))
        artist = track.get('artist_name', '')
        logger.debug(
            f"[origin {origin_consumed}/{origin_total}] '{title}'"
            + (f" - {artist}" if artist else "")
        )
        for group in groups:
            if group['_active'] and origin_consumed >= group['_next_at']:
                batch = _get_batch(group)
                for injected in batch:
                    inj_title = injected.get('title', injected.get('id', '?'))
                    inj_artist = injected.get('artist_name', '')
                    logger.debug(
                        f"[inject: {group['name']}] '{inj_title}'"
                        + (f" - {inj_artist}" if inj_artist else "")
                    )
                result.extend(batch)
                group['_next_at'] += group['every']

        if not top_continue and not any(g['_active'] for g in groups):
            logger.debug(
                f"Interleave: all inject sources exhausted at origin {origin_consumed}/{origin_total}. "
                "Stopping (continue_on_exhaust=false)."
            )
            break

    if top_continue:
        appended = 0
        for group in groups:
            remaining = group['tracks'][group['_cursor']:]
            for injected in remaining:
                inj_title = injected.get('title', injected.get('id', '?'))
                inj_artist = injected.get('artist_name', '')
                logger.debug(
                    f"[inject: {group['name']}] (tail) '{inj_title}'"
                    + (f" - {inj_artist}" if inj_artist else "")
                )
            result.extend(remaining)
            appended += len(remaining)
        if appended:
            logger.debug(f"Interleave: appended {appended} remaining inject tracks after origin exhausted.")

    logger.info(
        f"Action: Interleaved {len(groups)} inject source(s) into pipeline. "
        f"Origin={len(current_tracks)}, Result={len(result)}"
    )
    return result
