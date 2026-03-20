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
import sys
import deezer
import logging
import requests
import random
import time
import json
from datetime import datetime, timedelta
from utils.config import get_global_value
from utils.infrastructure.signals import shutdown_event

# Error codes/types that should NOT trigger blocklisting on fetch cancellation.
NON_BLOCKLIST_ERROR_CODES = {
    "429",
    "ConnectionError",
    "ReadTimeout",
    "ConnectTimeout",
    "Timeout",
}

# Transient/network-like patterns that should not trigger blocklisting.
NON_BLOCKLIST_ERROR_PATTERNS = (
    "timed out",
    "timeout",
    "connection",
    "temporarily unavailable",
    "service unavailable",
    "network",
    "quota",
)

def extract_error_code(err):
    """Extract a compact error code/type from Deezer or network exceptions."""
    if err is None:
        return "unknown"

    if isinstance(err, (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.Timeout)):
        return type(err).__name__

    err_str = str(err)
    err_str_lower = err_str.lower()

    if "429" in err_str_lower or "quota" in err_str_lower:
        return "429"

    marker = "'code':"
    marker_index = err_str_lower.find(marker)
    if marker_index != -1:
        remainder = err_str[marker_index + len(marker):].strip()
        code_chars = []
        for ch in remainder:
            if ch.isdigit():
                code_chars.append(ch)
            elif code_chars:
                break
        if code_chars:
            return "".join(code_chars)

    return type(err).__name__

def should_blocklist_failed_fetch(error_code, error_detail):
    """Returns True when a cancelled fetch should be blocklisted."""
    configured_days = get_global_value("blocklist_expiry_days", default=7)
    try:
        expiry_days = int(configured_days)
        if expiry_days == 0:
            return False
    except (TypeError, ValueError):
        pass

    if error_code in NON_BLOCKLIST_ERROR_CODES:
        return False

    detail = str(error_detail).lower() if error_detail is not None else ""
    return not any(pattern in detail for pattern in NON_BLOCKLIST_ERROR_PATTERNS)

def log_enrichment_progress(logger, log_prefix, i, total_items, last_log_time, start_log_time, log_interval):
    """
    Log enrichment progress at configured intervals. Called for every loop iteration.
    Returns updated last_log_time if logging occurred, otherwise returns original last_log_time.
    """
    #Noisy logging for debugging progress logging behavior
    #logger.debug(f"log_enrichment_progress called: log_prefix='{log_prefix}', i={i}, total_items={total_items}, last_log_time={last_log_time}, start_log_time={start_log_time}, log_interval={log_interval}")
    current_time = time.time()
    if current_time - last_log_time >= log_interval:
        elapsed_time = current_time - start_log_time
        
        if isinstance(total_items, int):
            items_remaining = total_items - i
            time_per_item = elapsed_time / i
            eta_seconds = items_remaining * time_per_item
            eta_str = str(timedelta(seconds=int(eta_seconds)))
            percent = f"{i/total_items:.1%}"
            suffix = f"{percent} ({i}/{total_items}) complete (ETA: {eta_str})..."
        else:
            suffix = f"{i} items processed..."
        
        logger.info(f"{log_prefix} enrichment: {suffix}")
        return current_time
    
    return last_log_time

def fetch_with_retry(fetch_func, entity_id, entity_label, logger, mark_failed_fetch=None, max_retries=None):
    """Fetch an entity with retry, backoff, and optional failed-fetch persistence."""
    max_retries_value = max_retries if max_retries is not None else get_global_value('max_retries', 4)
    attempts = max_retries_value + 1  # Convert "number of retries" to "total attempts"
    last_error_code = "unknown"
    last_error_detail = None
    entity_name = entity_label.capitalize()

    for attempt in range(attempts):
        if shutdown_event.is_set():
            logger.debug(f"fetch_with_retry interrupted while fetching {entity_label} {entity_id}. Returning partial results.")
            return None

        try:
            if attempt == 0:
                time.sleep(random.uniform(0.1, 0.3))
            return fetch_func(entity_id)

        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as net_err:
            last_error_code = extract_error_code(net_err)
            last_error_detail = str(net_err)
            wait_time = 5 * (attempt + 1)
            if attempt < attempts - 1:
                logger.debug(
                    f"Network retry ({entity_name} {entity_id}): {net_err}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        except Exception as err:
            err_str = str(err).lower()
            if "429" in err_str or "quota" in err_str:
                last_error_code = "429"
                last_error_detail = str(err)
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                if attempt < attempts - 1:
                    logger.warning(
                        f"Rate limited ({entity_name} {entity_id})! Retrying in {wait_time:.2f}s..."
                    )
                else:
                    logger.warning(
                        f"Rate limited ({entity_name} {entity_id}) on final attempt. Cooling down for {wait_time:.2f}s before cancellation."
                    )
                time.sleep(wait_time)
            else:
                last_error_code = extract_error_code(err)
                last_error_detail = str(err)
                logger.debug(
                    f"Unexpected API error for {entity_label} {entity_id}: {err} (Attempt {attempt + 1}/{attempts})"
                )
                if attempt < attempts - 1:
                    time.sleep(3)

    logger.error(f"CANCELLED: Failed to retrieve {entity_label} {entity_id} after {attempts} total attempts ({max_retries_value} retries).")
    if should_blocklist_failed_fetch(last_error_code, last_error_detail):
        logger.warning(
            f"Blocklisting {entity_label} {entity_id} after repeated fetch failures. "
            f"code={last_error_code}, deezer_response={last_error_detail}"
        )
        if mark_failed_fetch is not None:
            try:
                mark_failed_fetch(entity_id, last_error_code, logger)
            except Exception as db_err:
                logger.debug(f"Failed to persist {entity_label} failure state for {entity_id}: {db_err}")
    else:
        logger.debug(
            f"Skipped blocklisting {entity_label} {entity_id} due to transient/non-blocking error ({last_error_code})."
        )

    return None

def apply_rate_limit_checkpoint(
    logger,
    batch_start_time,
    iteration_index,
    api_batch_size,
    rate_limit,
    request_label,
    log_no_cooldown=False,
    cooldown_task=None,
):
    """Throttle batched requests to stay within the configured request rate."""
    if iteration_index % api_batch_size != 0:
        return batch_start_time, False

    target_time_per_batch = (api_batch_size / rate_limit) * 60
    elapsed_time = time.time() - batch_start_time
    items_per_second = api_batch_size / elapsed_time if elapsed_time > 0 else 0

    logger.debug(
        f"Time taken for {api_batch_size} {request_label}: {elapsed_time:.2f} seconds ({items_per_second:.2f} items/sec)"
    )

    if elapsed_time < target_time_per_batch:
        sleep_time = target_time_per_batch - elapsed_time
        logger.debug(
            f"Rate limit cooldown: target={target_time_per_batch:.2f}s, sleeping for {sleep_time:.2f}s to maintain {rate_limit} req/min limit"
        )
        interrupted = cooldown_wait_with_tasks(
            logger,
            sleep_time,
            request_label,
            cooldown_task=cooldown_task,
        )
        return time.time(), interrupted
    elif log_no_cooldown:
        logger.debug("No cooldown needed, proceeding to next batch immediately.")

    return time.time(), False

def cooldown_wait_with_tasks(logger, sleep_time, request_label, cooldown_task=None):
    """Wait in interruptible chunks and optionally run one cooldown task during the wait window."""
    max_chunk_seconds = 5.0
    remaining = max(0.0, float(sleep_time))
    task_ran = False

    while remaining > 0:
        if shutdown_event.is_set():
            logger.debug(
                f"Rate limit cooldown interrupted before waiting for {request_label}."
            )
            return True

        if not task_ran and cooldown_task is not None:
            task_start = time.time()
            cooldown_task()
            task_elapsed = max(0.0, time.time() - task_start)
            remaining = max(0.0, remaining - task_elapsed)
            task_ran = True
            if remaining <= 0:
                logger.debug("Cooldown task consumed the full cooldown window.")
                break

        wait_chunk = min(max_chunk_seconds, remaining)
        logger.debug(
            f"Rate limit cooldown progress for {request_label}: waiting {wait_chunk:.2f}s (remaining {remaining:.2f}s)."
        )
        interrupted = shutdown_event.wait(timeout=wait_chunk)
        if interrupted:
            logger.debug(
                f"Rate limit cooldown interrupted while waiting for {request_label}."
            )
            return True
        remaining = max(0.0, remaining - wait_chunk)

    logger.debug(f"Rate limit cooldown complete for {request_label}.")
    return False

def persist_track_batch(tracks, cached_tracks, logger, phase_label, update_track_metadata):
    """Persist a track batch and reset the working list."""
    if not tracks:
        return cached_tracks, tracks

    if phase_label == "Database Checkpoint":
        logger.debug(f"{phase_label}: Pushing chunk of {len(tracks)} tracks to database")
    else:
        logger.debug(f"{phase_label}: Saving remaining {len(tracks)} tracks...")

    update_track_metadata(tracks, logger)
    cached_tracks.extend(tracks)
    return cached_tracks, []

def persist_album_batch(
    albums,
    cached_albums,
    logger,
    phase_label,
    update_album_metadata,
    populate_album_genres,
):
    """Persist an album batch, populate genres, and reset the working list."""
    if not albums:
        return cached_albums, albums

    if phase_label == "Database Checkpoint":
        logger.debug(f"{phase_label}: Pushing chunk of {len(albums)} albums to database")
        logger.debug(f"Album IDs in checkpoint: {[album.get('id') for album in albums]}")
    else:
        logger.debug(f"{phase_label}: Saving remaining {len(albums)} albums...")
        logger.debug(f"Album IDs to save: {[album.get('id') for album in albums]}")

    try:
        update_album_metadata(albums, logger)
        populate_album_genres(albums, logger)
        logger.debug(
            f"{phase_label}: update_album_metadata and populate_album_genres completed successfully."
        )
    except Exception as batch_err:
        logger.error(
            f"{phase_label}: update_album_metadata or populate_album_genres raised exception: {batch_err}"
        )
        logger.exception("Stack trace for batch persistence error:")
        raise

    cached_albums.extend(albums)
    return cached_albums, []

def _is_json_string(value):
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return (stripped.startswith("[") and stripped.endswith("]")) or (
        stripped.startswith("{") and stripped.endswith("}")
    )

def _normalize_json_field(value):
    if value is None:
        return json.dumps([])
    if _is_json_string(value):
        return value
    return json.dumps(value)

def _extract_prefetched_payload(item, required_payload_keys):
    """Returns (payload_dict_or_none, item_id)."""
    if hasattr(item, 'as_dict'):
        payload = item.as_dict()
        return payload, payload.get('id')

    if isinstance(item, dict):
        item_id = item.get('id')
        if item_id is None:
            return None, None

        has_payload = any(key in item for key in required_payload_keys)
        if has_payload:
            return item, item_id

        return None, item_id

    return None, item

def _persist_stats_batch(
    items,
    cached_items,
    logger,
    phase_label,
    update_partial_batch,
    entity_label,
):
    if not items:
        return cached_items, items

    logger.debug(f"{phase_label}: Pushing chunk of {len(items)} {entity_label} stats to database")
    update_partial_batch(items, logger)
    cached_items.extend(items)
    return cached_items, []

def _flush_pending_database_batches_on_shutdown(
    items,
    logger,
    entity_label,
    should_flush_metadata,
    should_flush_stats,
    update_metadata_batch=None,
    update_stats_batch=None,
):
    """Persist pending metadata or stats payloads when shutdown is acknowledged."""
    if not items:
        return items

    if should_flush_metadata and update_metadata_batch is not None:
        logger.debug(f"Shutdown Flush: Persisting {len(items)} pending {entity_label} metadata rows.")
        update_metadata_batch(items, logger)
        return []

    if should_flush_stats and update_stats_batch is not None:
        logger.debug(f"Shutdown Flush: Persisting {len(items)} pending {entity_label} stats rows.")
        update_stats_batch(items, logger)
        return []

    return items

def _apply_rate_limit_post_fetch(
    logger,
    did_api_fetch,
    start_time,
    api_request_count,
    api_batch_size,
    rate_limit,
    request_label,
    flush_on_interrupt,
    interrupted_message,
    log_no_cooldown=False,
    cooldown_task=None,
):
    if not did_api_fetch:
        return start_time, False

    start_time, cooldown_interrupted = apply_rate_limit_checkpoint(
        logger,
        start_time,
        api_request_count,
        api_batch_size,
        rate_limit,
        request_label,
        log_no_cooldown=log_no_cooldown,
        cooldown_task=cooldown_task,
    )
    if cooldown_interrupted:
        flush_on_interrupt()
        logger.debug(interrupted_message)
        return start_time, True

    return start_time, False

def get_authenticated_client(config, logger):
    """
    Initializes the Deezer Client using an ARL cookie.
    """
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("--- Initializing Deezer Authentication ---")
        logger.debug(f"Raw config keys available: {list(config.get('config', {}).keys())}")

    arl = config.get('config', {}).get('arl_token')
    user_id = config.get('config', {}).get('user_id')

    if not arl or arl == "PASTE_YOUR_ARL_HERE":
        logger.error("ARL token is missing in config.yml")
        sys.exit(1)

    # Build request headers with the ARL cookie
    headers = {
        "Cookie": f"arl={arl}",
        "Accept-Language": "en-US",
    }
    
    if logger.isEnabledFor(logging.DEBUG):
        # Mask the ARL for security in logs
        masked_arl = f"{arl[:6]}...{arl[-6:]}" if len(arl) > 12 else "***"
        logger.debug(f"Auth headers prepared with ARL: {masked_arl}")

    # Read chunk size from config (default: 50)
    chunk_size = config.get('config', {}).get('chunk_size', get_global_value('chunk_size', 50))
    logger.debug(f"Global chunk size set to: {chunk_size}")

    try:
        logger.debug("Attempting to instantiate deezer.Client...")
            
        client = deezer.Client(headers=headers)
        
        # Store the chunk size on the client for later use in operations
        client.chunk_size = chunk_size

        # Test connection using the numeric user_id
        if user_id:
            logger.debug(f"Testing connection for User ID: {user_id}")
                
            user = client.get_user(user_id)
            masked_name = f"{user.name[0]}...{user.name[-1]}" if len(user.name) > 2 else "***"
            logger.info(f"Authenticated successfully as: {masked_name}")
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"User Metadata: Name='{user.name}', "
                             f"Status='{getattr(user, 'status', 'N/A')}', "
                             f"Link={user.link}")
        else:
            # Fallback test if user_id isn't provided (checking a public track)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("No user_id provided. Performing fallback connectivity test...")
                
            track = client.get_track(3135553) # Testing with 'Daft Punk - One More Time'
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Fallback test successful. Track retrieved: '{track.title}'")
                
            logger.warning("Connection successful, but user_id is missing in config.yml. "
                           "Exclusion strategies may fail without it.")
        
        return client

    except Exception as e:
        logger.error(f"Failed to connect to Deezer API: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Traceback for authentication failure:")
            
        logger.debug("Check if your ARL token has expired or if your user_id is correct.")
        sys.exit(1)

def get_authenticated_session(arl, logger, warm_url=None):
    """
    Creates a session, establishes context via a pre-flight GET, 
    and performs the CSRF handshake to return (session, api_token).
    """
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    session.cookies.set('arl', arl, domain='.deezer.com')

    # 1. Warm up session (Pre-flight)
    # We load a page to populate 'sid' and other tracking cookies
    target_warm_url = warm_url if warm_url else "https://www.deezer.com/us/"
    logger.debug(f"Warming up Deezer session: {target_warm_url}")
    session.get(target_warm_url)

    # 2. Acquire CSRF Token via Handshake
    cid = random.randint(100000000, 999999999)
    token_url = f"https://www.deezer.com/ajax/gw-light.php?method=deezer.getUserData&input=3&api_version=1.0&api_token=&cid={cid}"
    
    # Handshake requires text/plain and a Referer
    handshake_headers = {
        'Content-Type': 'text/plain;charset=UTF-8',
        'Referer': target_warm_url
    }
    
    try:
        resp = session.post(token_url, data="{}", headers=handshake_headers).json()
        api_token = resp.get('results', {}).get('checkForm')
        
        if not api_token:
            logger.error(f"Handshake failed. Gateway response: {resp}")
            return None, None
            
        logger.debug("Deezer CSRF Handshake successful.")
        return session, api_token
    except Exception as e:
        logger.error(f"Authentication utility error: {e}")
        return None, None

def get_tracks(client, logger, source_type, identifier, cache_file=None, track_ids=None):
    """
    Transforms Deezer API objects into a list of dictionaries with rate-limiting protection.
    """
    from utils.db_manager import (
        update_track_metadata,
        mark_track_metadata_fetch_failed,
        update_tracks_partial_batch,
    )
    from utils.collections import sync_to_collections
    logger.debug(f"Getting tracks for type '{source_type}' with ID '{identifier}'")

    display_name = identifier
    item_id = identifier

    # Parse internal variable string for playlists or albums if provided
    if isinstance(identifier, str) and (identifier.startswith("playlist__") or identifier.startswith("album__")):
        parts = identifier.split("__")
        if len(parts) >= 3:
            item_type = parts[0] 
            display_name = parts[1].replace("_", " ")
            item_id = parts[2]
            logger.debug(f"Parsed {item_type} identifier: Name='{display_name}', ID='{item_id}'")

    tracks = []

    # Decide if we are iterating a collection or fetching specific IDs
    iterable = track_ids if track_ids is not None else client

    # Extract full track metadata
    date_time = datetime.now().isoformat()
    if source_type == "favorites":
        collection = source_type
    elif source_type != "database":
        collection = f"{item_type}__{item_id}"
    
    # chunk_size: Database checkpoint interval (how many tracks to process before saving to DB)
    chunk_size = get_global_value('chunk_size', 50)
    cached_tracks = []

    total_len = len(iterable) if hasattr(iterable, '__len__') else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value('log_interval',120)
    
    rate_limit = get_global_value('rate_limit', 60)
    api_batch_size = get_global_value('api_batch_size', 50)

    def persist_tracks_for_cooldown(phase_label):
        """Use cooldown windows for persistence work instead of idling."""
        nonlocal tracks, cached_tracks
        if not tracks:
            return

        if source_type == "database":
            if identifier == "tracks":
                cached_tracks, tracks = persist_track_batch(
                    tracks,
                    cached_tracks,
                    logger,
                    phase_label,
                    update_track_metadata,
                )
            elif identifier == "stats":
                cached_tracks, tracks = _persist_stats_batch(
                    tracks,
                    cached_tracks,
                    logger,
                    phase_label,
                    update_tracks_partial_batch,
                    "track",
                )
            return

        pending_count = len(tracks)
        cached_tracks.extend(tracks)
        tracks = []
        logger.debug(
            f"{phase_label}: Syncing cumulative source snapshot of {len(cached_tracks)} tracks "
            f"({pending_count} newly fetched) for collection '{collection}'."
        )
        sync_to_collections(cached_tracks, logger, collection_name=collection)

    def flush_pending_tracks_on_shutdown():
        """Persist pending track payloads with simple writes only when shutdown is acknowledged."""
        nonlocal tracks
        tracks = _flush_pending_database_batches_on_shutdown(
            tracks,
            logger,
            "track",
            should_flush_metadata=(source_type == "database" and identifier == "tracks"),
            should_flush_stats=(source_type == "database" and identifier == "stats"),
            update_metadata_batch=update_track_metadata,
            update_stats_batch=update_tracks_partial_batch,
        )

    # Track the start time for the batch of requests
    start_time = time.time()
    api_request_count = 0

    for i, track in enumerate(iterable, 1):
        try:
            if shutdown_event.is_set():
                flush_pending_tracks_on_shutdown()
                logger.debug("Shutdown acknowledged mid-track collection. Returning partial results.")
                if source_type == "database":
                    return []
                return cached_tracks + tracks
            
            # Log progress at configured intervals
            log_prefix = f"Database '{identifier}'" if source_type == "database" else f"'{source_type}'"
            last_log_time = log_enrichment_progress(logger, log_prefix, i, total_len, last_log_time, start_log_time, log_interval)

            if source_type == "database" and (identifier == "tracks" or identifier == "stats"):
                if identifier == "tracks":
                    prefetched_required_keys = (
                        "title",
                        "isrc",
                        "track_token",
                        "artist",
                        "album",
                        "artist_id",
                        "album_id",
                    )
                else:
                    prefetched_required_keys = (
                        "readable",
                        "unseen",
                        "rank",
                        "bpm",
                        "gain",
                        "available_countries",
                        "contributors",
                    )

                d, t_id = _extract_prefetched_payload(track, prefetched_required_keys)
                used_prefetched_payload = d is not None

                if not t_id:
                    logger.debug(f"Track payload missing id at index {i}. Skipping.")
                    continue

                did_api_fetch = False
                if not used_prefetched_payload:
                    did_api_fetch = True
                    api_request_count += 1

                    # Use the retry helper for heavy metadata fetching
                    track_obj = fetch_with_retry(
                        client.get_track,
                        t_id,
                        "track",
                        logger,
                        mark_failed_fetch=mark_track_metadata_fetch_failed,
                    )
                    if not track_obj:
                        # Error details are already logged by fetch_with_retry.
                        continue

                    # ~ 0.5 tracks/s faster due to single as_dict() call vs 20+ individual getattr() operations - ~ 2 t/s
                    d = track_obj.as_dict()
                else:
                    logger.debug(f"Using prefetched track payload for track {t_id}; skipping per-track API fetch.")

                artist_blob = d.get('artist') if isinstance(d.get('artist'), dict) else {}
                album_blob = d.get('album') if isinstance(d.get('album'), dict) else {}
                artist_id = d.get('artist_id') if d.get('artist_id') is not None else artist_blob.get('id')
                album_id = d.get('album_id') if d.get('album_id') is not None else album_blob.get('id')
                
                if identifier == "tracks":
                    tracks.append({
                        'id': str(d.get('id') if d.get('id') is not None else t_id),
                        'readable': d.get('readable'),
                        'title': d.get('title'),
                        'title_short': d.get('title_short'),
                        'title_version': d.get('title_version'),
                        'unseen': d.get('unseen', False),
                        'isrc': d.get('isrc'),
                        'link': d.get('link'),
                        'share': d.get('share'),
                        'duration': d.get('duration', 0),
                        'track_position': d.get('track_position'),
                        'disk_number': d.get('disk_number'),
                        'rank': d.get('rank', 0),
                        'release_date': d.get('release_date'),
                        'explicit_lyrics': d.get('explicit_lyrics',False),
                        'explicit_content_lyrics': d.get('explicit_content_lyrics',0),
                        'explicit_content_cover': d.get('explicit_content_cover',0),
                        'preview': d.get('preview'),
                        'bpm': d.get('bpm',0),
                        'gain': d.get('gain',0),
                        'available_countries': _normalize_json_field(d.get('available_countries', [])),
                        'contributors': _normalize_json_field(d.get('contributors', [])),
                        'md5_image': d.get('md5_image'),
                        'track_token': d.get('track_token'),
                        'artist_id': artist_id,
                        'album_id': album_id,
                        'date_cached': date_time
                    })
                else: # stats enrichment
                    tracks.append({
                        'id': str(d.get('id') if d.get('id') is not None else t_id),
                        'readable': d.get('readable'),
                        'unseen': d.get('unseen', False),
                        'rank': d.get('rank', 0),
                        'bpm': d.get('bpm',0),
                        'gain': d.get('gain',0),
                        'available_countries': _normalize_json_field(d.get('available_countries', [])),
                        'contributors': _normalize_json_field(d.get('contributors', [])),
                        'date_cached': date_time
                    })
            else:
                # fetch for source ID collection - extract ID directly for performance
                if isinstance(track, dict):
                    track_id = track.get('id')
                elif hasattr(track, 'id'):
                    track_id = track.id
                else:
                    track_id = track.as_dict().get('id')

                if track_id is None:
                    logger.debug(f"Source track payload missing id at index {i}. Skipping.")
                    continue

                tracks.append({
                    'id': str(track_id),
                    'collection': collection,
                    'date_cached': date_time
                })

            logger.debug(f"Processed track {track}: {i}/{total_len}") 

            # If performing database enrichment, perform periodic checkpoint at chunk_size interval.
            # This runs before cooldown checks so matching chunk/api batch sizes flush full chunks (50, not 49+1).
            if source_type == "database" and identifier == "tracks" and i % chunk_size == 0:
                cached_tracks, tracks = persist_track_batch(
                    tracks,
                    cached_tracks,
                    logger,
                    "Database Checkpoint",
                    update_track_metadata,
                )

            # Check rate limiting only for real API fetches, and only after processing this item.
            if source_type == "database" and identifier in ("tracks", "stats"):
                start_time, cooldown_interrupted = _apply_rate_limit_post_fetch(
                    logger,
                    did_api_fetch,
                    start_time,
                    api_request_count,
                    api_batch_size,
                    rate_limit,
                    "requests",
                    flush_on_interrupt=flush_pending_tracks_on_shutdown,
                    interrupted_message="Shutdown acknowledged during track cooldown. Returning partial results.",
                    log_no_cooldown=True,
                    cooldown_task=lambda: persist_tracks_for_cooldown("Cooldown Checkpoint"),
                )
                if cooldown_interrupted:
                    # cached_tracks items were already persisted by checkpoint, only return new unpersisted items
                    if source_type == "database":
                        return []
                    return tracks

        except Exception as e:
            logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
            time.sleep(1)
            continue
    
    # Database enrichment cleanup
    if source_type == "database" and identifier == "tracks" and tracks:
        cached_tracks, tracks = persist_track_batch(
            tracks,
            cached_tracks,
            logger,
            "Database Cleanup",
            update_track_metadata,
        )
        tracks = cached_tracks
    elif source_type == "database" and identifier == "tracks":
        tracks = cached_tracks

    if source_type == "database" and identifier == "stats" and cached_tracks:
        tracks = cached_tracks + tracks

    if source_type != "database" and cached_tracks:
        tracks = cached_tracks + tracks

    logger.debug(f"Successfully transformed {len(tracks)} tracks.")
    
    return tracks

def get_albums(client, logger, identifier, album_ids=None):
    """
    Fetches album metadata from Deezer API with rate-limiting protection.
    """
    from utils.db_manager import (
        update_album_metadata,
        populate_album_genres,
        mark_album_metadata_fetch_failed,
        update_albums_partial_batch,
    )
    
    albums = []
    cached_albums = []
    date_time = datetime.now().isoformat()
    chunk_size = get_global_value('chunk_size', 50)
    
    # Validate input
    if not album_ids:
        logger.warning("No album IDs provided for enrichment.")
        return albums
    
    # Setup rate limiting
    rate_limit = get_global_value('rate_limit', 60)
    api_batch_size = get_global_value('api_batch_size', 50)
    
    total_albums = len(album_ids) if hasattr(album_ids, '__len__') else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value('log_interval', 120)

    def persist_albums_for_cooldown(phase_label):
        """Use cooldown windows for album persistence work instead of idling."""
        nonlocal albums, cached_albums
        if not albums:
            return

        if identifier == "database":
            cached_albums, albums = persist_album_batch(
                albums,
                cached_albums,
                logger,
                phase_label,
                update_album_metadata,
                populate_album_genres,
            )
            return

        if identifier == "stats":
            cached_albums, albums = _persist_stats_batch(
                albums,
                cached_albums,
                logger,
                phase_label,
                update_albums_partial_batch,
                "album",
            )

    def flush_pending_albums_on_shutdown():
        """Persist pending album payloads with simple writes only when shutdown is acknowledged."""
        nonlocal albums
        albums = _flush_pending_database_batches_on_shutdown(
            albums,
            logger,
            "album",
            should_flush_metadata=(identifier == "database"),
            should_flush_stats=(identifier == "stats"),
            update_metadata_batch=update_album_metadata,
            update_stats_batch=update_albums_partial_batch,
        )
    
    # Track the start time for the batch of requests
    start_time = time.time()
    api_request_count = 0
    
    try:
        for i, album_ref in enumerate(album_ids, 1):
            try:
                if shutdown_event.is_set():
                    flush_pending_albums_on_shutdown()
                    logger.debug("Shutdown acknowledged mid-album collection. Returning partial results.")
                    if identifier in ("database", "stats"):
                        return []
                    return cached_albums + albums
                
                # Log progress at configured intervals
                last_log_time = log_enrichment_progress(logger, f"Album '{identifier}'", i, total_albums, last_log_time, start_log_time, log_interval)

                if identifier == "database":
                    prefetched_required_keys = (
                        "title",
                        "upc",
                        "cover",
                        "genres",
                        "artist",
                        "artist_id",
                    )
                else:
                    prefetched_required_keys = ("fans", "available")

                d, requested_album_id = _extract_prefetched_payload(album_ref, prefetched_required_keys)
                used_prefetched_payload = d is not None

                if not requested_album_id:
                    logger.debug(f"Album payload missing id at index {i}. Skipping.")
                    continue

                did_api_fetch = False
                if not used_prefetched_payload:
                    did_api_fetch = True
                    api_request_count += 1

                    # Fetch album data using retry helper
                    album_obj = fetch_with_retry(
                        client.get_album,
                        requested_album_id,
                        "album",
                        logger,
                        mark_failed_fetch=mark_album_metadata_fetch_failed,
                    )
                    if not album_obj:
                        # Error details are already logged by fetch_with_retry.
                        continue

                    # Convert to dictionary
                    d = album_obj.as_dict()
                else:
                    logger.debug(
                        f"Using prefetched album payload for album {requested_album_id}; skipping per-album API fetch."
                    )
                
                # Warn if API returned a different album ID (redirect/canonical version)
                if not used_prefetched_payload and d.get('id') != requested_album_id:
                    logger.debug(f"API redirect: Requested album {requested_album_id}, but API returned {d.get('id')}. Using requested ID to match database stub.")

                artist_blob = d.get('artist') if isinstance(d.get('artist'), dict) else {}
                artist_id = d.get('artist_id') if d.get('artist_id') is not None else artist_blob.get('id')
                artist_name = d.get('artist_name') if d.get('artist_name') is not None else artist_blob.get('name')
                
                if identifier == "database":
                    # Full metadata collection
                    albums.append({
                        'id': requested_album_id,  # Use requested ID to match database stub
                        'title': d.get('title'),
                        'upc': d.get('upc'),
                        'link': d.get('link'),
                        'share': d.get('share'),
                        'cover': d.get('cover'),
                        'cover_small': d.get('cover_small'),
                        'cover_medium': d.get('cover_medium'),
                        'cover_big': d.get('cover_big'),
                        'cover_xl': d.get('cover_xl'),
                        'md5_image': d.get('md5_image'),
                        'label': d.get('label'),
                        'nb_tracks': d.get('nb_tracks'),
                        'duration': d.get('duration', 0),
                        'fans': d.get('fans', 0),
                        'release_date': d.get('release_date'),
                        'record_type': d.get('record_type'),
                        'available': d.get('available', True),
                        'tracklist': d.get('tracklist'),
                        'explicit_lyrics': d.get('explicit_lyrics', False),
                        'explicit_content_lyrics': d.get('explicit_content_lyrics', 0),
                        'explicit_content_cover': d.get('explicit_content_cover', 0),
                        'contributors': _normalize_json_field(d.get('contributors', [])),
                        'genres': _normalize_json_field(d.get('genres', [])),
                        'artist_id': artist_id,
                        'artist_name': artist_name,
                        'date_cached': date_time
                    })
                else:
                    # Partial enrichment (stats) - only refreshable fields
                    albums.append({
                        'id': requested_album_id,  # Use requested ID to match database stub
                        'fans': d.get('fans', 0),
                        'available': d.get('available', True),
                        'date_cached': date_time
                    })
                
                logger.debug(f"Processed album {requested_album_id}: {i}/{total_albums}")

                # If performing full album enrichment, perform periodic checkpoint at chunk_size interval
                if identifier == "database" and i % chunk_size == 0:
                    cached_albums, albums = persist_album_batch(
                        albums,
                        cached_albums,
                        logger,
                        "Database Checkpoint",
                        update_album_metadata,
                        populate_album_genres,
                    )
                    if shutdown_event.is_set():
                        flush_pending_albums_on_shutdown()
                        return []

                # Check rate limiting only for real API fetches, and only after processing this item.
                start_time, cooldown_interrupted = _apply_rate_limit_post_fetch(
                        logger,
                        did_api_fetch,
                        start_time,
                        api_request_count,
                        api_batch_size,
                        rate_limit,
                        "album requests",
                        flush_on_interrupt=flush_pending_albums_on_shutdown,
                        interrupted_message="Shutdown acknowledged during album cooldown. Returning partial results.",
                        cooldown_task=lambda: persist_albums_for_cooldown("Cooldown Checkpoint"),
                    )
                if cooldown_interrupted:
                    # cached_albums items were already persisted by checkpoint, only return new unpersisted items
                    if identifier in ("database", "stats"):
                        return []
                    return albums
                
            except Exception as e:
                logger.debug(f"Non-critical loop error at index {i} (Album {album_ref}): {e}")
                time.sleep(1)
                continue
        
        # Full album enrichment cleanup
        if identifier == "database" and albums:
            cached_albums, albums = persist_album_batch(
                albums,
                cached_albums,
                logger,
                "Database Cleanup",
                update_album_metadata,
                populate_album_genres,
            )
            albums = cached_albums
        elif identifier == "database":
            albums = cached_albums

        if identifier == "stats" and cached_albums:
            albums = cached_albums + albums

        logger.debug(f"Successfully transformed {len(albums)} albums.")
        
    except Exception as e:
        logger.error(f"Critical error in get_albums: {e}")
        raise
    
    return albums
