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
import logging
import json
from datetime import datetime, timedelta
from utils.logger import setup_logger
from utils.config_loader import get_global_value
from utils.signals import shutdown_event

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
    from utils.db_manager import update_track_metadata, mark_track_metadata_fetch_failed
    logger.debug(f"Getting tracks for type '{source_type}' with ID '{identifier}'")

    def fetch_track_with_retry(t_id, max_retries=get_global_value('max_retries', 5)):
        """
        Helper to fetch track data handling both Rate Limits and Network Drops.
        """
        last_error_code = "unknown"
        last_error_detail = None
        for attempt in range(max_retries):
            if shutdown_event.is_set():
                logger.debug("fetch_track_with_retry interrupted! Returning partial results.")
                return None
            try:
                # Add small delay to avoid rate limiting
                if attempt == 0:
                    time.sleep(random.uniform(0.1, 0.3))
                return client.get_track(t_id)
            
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as net_err:
                last_error_code = extract_error_code(net_err)
                last_error_detail = str(net_err)
                wait_time = (5 * (attempt + 1))  # 5s, 10s, 15s...
                if attempt < max_retries - 1:
                    logger.debug(f"Network retry (Track {t_id}): {net_err}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                
            except Exception as e:
                # Check for rate limiting in the error message
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    last_error_code = "429"
                    last_error_detail = str(e)
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    if attempt < max_retries - 1:
                        # Rate limits remain WARNING to notify user of throttling.
                        logger.warning(f"Rate limited (Track {t_id})! Retrying in {wait_time:.2f}s...")
                    else:
                        logger.warning(
                            f"Rate limited (Track {t_id}) on final attempt. Cooling down for {wait_time:.2f}s before cancellation."
                        )
                    time.sleep(wait_time)
                else:
                    last_error_code = extract_error_code(e)
                    last_error_detail = str(e)
                    # Other API errors
                    logger.debug(f"Unexpected API error for {t_id}: {e} (Attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(3)
        
        logger.error(f"CANCELLED: Failed to retrieve track {t_id} after {max_retries} attempts.")
        if should_blocklist_failed_fetch(last_error_code, last_error_detail):
            logger.warning(
                f"Blocklisting track {t_id} after repeated fetch failures. "
                f"code={last_error_code}, deezer_response={last_error_detail}"
            )
            try:
                mark_track_metadata_fetch_failed(t_id, last_error_code, logger)
            except Exception as db_err:
                logger.debug(f"Failed to persist track failure state for {t_id}: {db_err}")
        else:
            logger.debug(f"Skipped blocklisting track {t_id} due to transient/non-blocking error ({last_error_code}).")
        return None

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
    
    # Only database enrichment needs delays (not normal source collection)
    is_database_enrichment = source_type == "database"

    rate_limit = get_global_value('rate_limit', 60)
    api_batch_size = get_global_value('api_batch_size', 50)
    target_time_per_batch = (api_batch_size / rate_limit) * 60

    # Track the start time for the batch of requests
    start_time = time.time()

    for i, track in enumerate(iterable, 1):
        try:
            if shutdown_event.is_set():
                logger.debug("Shutdown acknowledged mid-track collection. Returning partial results.")
                return cached_tracks

            # Check rate limiting at configured intervals to prevent sustained high-load triggers
            if i % api_batch_size == 0 and is_database_enrichment:
                elapsed_time = time.time() - start_time
                items_per_second = api_batch_size / elapsed_time if elapsed_time > 0 else 0
                logger.debug(f"Time taken for {api_batch_size} requests: {elapsed_time:.2f} seconds ({items_per_second:.2f} items/sec)")
                
                # If we're under the target time, sleep to maintain rate limit
                if elapsed_time < target_time_per_batch:
                    sleep_time = target_time_per_batch - elapsed_time
                    logger.debug(f"Rate limit cooldown: Sleeping for {sleep_time:.2f} seconds to maintain {rate_limit} req/min limit")
                    time.sleep(sleep_time)
                else:
                    logger.debug("No cooldown needed, proceeding to next batch immediately.")
                
                # Reset the start time for the next batch
                start_time = time.time()

            if source_type == "database" and (identifier == "tracks" or identifier == "stats"):
                t_id = track.get('id') if isinstance(track, dict) else track
                
                # Use the retry helper for heavy metadata fetching
                track_obj = fetch_track_with_retry(t_id)
                if not track_obj:
                    # Error message provided in fetch_track_with_retry
                    continue
                
                # ~ 0.5 tracks/s faster due to single as_dict() call vs 20+ individual getattr() operations - ~ 2 t/s
                d = track_obj.as_dict()
                
                if identifier == "tracks":
                    tracks.append({
                        'id': str(d.get('id')),
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
                        'available_countries': json.dumps(d.get('available_countries', [])),
                        'contributors': json.dumps(d.get('contributors', [])),
                        'md5_image': d.get('md5_image'),
                        'track_token': d.get('track_token'),
                        'artist_id': d.get('artist', {}).get('id'),
                        'album_id': d.get('album', {}).get('id'),
                        'date_cached': date_time
                    })
                else: # stats enrichment
                    tracks.append({
                        'id': str(d.get('id')),
                        'readable': d.get('readable'),
                        'unseen': d.get('unseen', False),
                        'rank': d.get('rank', 0),
                        'bpm': d.get('bpm',0),
                        'gain': d.get('gain',0),
                        'available_countries': json.dumps(d.get('available_countries', [])),
                        'contributors': json.dumps(d.get('contributors', [])),
                        'date_cached': date_time
                    })
            else:
                # fetch for source ID collection - extract ID directly for performance
                track_id = track.id if hasattr(track, 'id') else track.as_dict().get('id')
                tracks.append({
                    'id': str(track_id),
                    'collection': collection,
                    'date_cached': date_time
                })

            logger.debug(f"Processed track {track}: {i}/{total_len}")
            
            current_time = time.time()
            if current_time - last_log_time >= log_interval:
                # 1. Calculate progress
                elapsed_time = current_time - start_log_time
                items_remaining = total_len - i
                
                # 2. Calculate average time and ETA
                time_per_item = elapsed_time / i
                eta_seconds = items_remaining * time_per_item
                
                # 3. Format seconds 
                eta_str = str(timedelta(seconds=int(eta_seconds)))
                percent = f"{i/total_len:.1%}"

                # 4. Create suffix
                suffix = f"{percent} ({i}/{total_len}) complete (ETA: {eta_str})..."

                if source_type == "database":
                    logger.info(f"Database '{identifier}' enrichment: {suffix}")
                elif source_type == "favorites":
                    logger.info(f"Fetching '{source_type}': {suffix}")
                elif identifier.startswith("playlist__"):
                    logger.info(f"Fetching playlist '{display_name}': {suffix}")
                elif identifier.startswith("album__"):
                    logger.info(f"Fetching album '{display_name}': {suffix}")
                else:
                    logger.info(f"Fetching '{source_type}': {suffix}")
                last_log_time = current_time 

            # If performing database enrichment, perform periodic checkpoint at chunk_size interval
            if source_type == "database" and identifier == "tracks" and i % chunk_size == 0:
                logger.debug(f"Database Checkpoint: Pushing chunk of {len(tracks)} tracks to database")
                update_track_metadata(tracks,logger)

                # Merge to total result and reset working batch
                cached_tracks.extend(tracks)
                tracks = []

        except Exception as e:
            logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
            time.sleep(1)
            continue
    
    # Database enrichment cleanup
    if source_type == "database" and identifier == "tracks":
        if tracks:
            logger.debug(f"Database Cleanup: Saving remaining {len(tracks)} tracks...")
            update_track_metadata(tracks,logger)
            cached_tracks.extend(tracks)
    
        tracks = cached_tracks

    logger.debug(f"Successfully transformed {len(tracks)} tracks.")
    
    return tracks

def get_albums(client, logger, identifier, album_ids=None):
    """
    Fetches album metadata from Deezer API with rate-limiting protection.
    """
    from utils.db_manager import update_album_metadata, populate_album_genres, populate_track_genres_for_album, mark_album_metadata_fetch_failed

    def fetch_album_with_retry(album_id, max_retries=get_global_value('max_retries', 5)):
        """
        Helper to fetch album data handling both Rate Limits and Network Drops.
        """
        last_error_code = "unknown"
        last_error_detail = None
        for attempt in range(max_retries):
            if shutdown_event.is_set():
                logger.debug("fetch_album_with_retry interrupted! Returning partial results.")
                return None
            try:
                # Add small delay to avoid rate limiting
                if attempt == 0:
                    time.sleep(random.uniform(0.1, 0.3))
                return client.get_album(album_id)
            
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as net_err:
                last_error_code = extract_error_code(net_err)
                last_error_detail = str(net_err)
                wait_time = (5 * (attempt + 1))  # 5s, 10s, 15s...
                if attempt < max_retries - 1:
                    logger.debug(f"Network retry (Album {album_id}): {net_err}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                
            except Exception as e:
                # Check for rate limiting in the error message
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    last_error_code = "429"
                    last_error_detail = str(e)
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limited (Album {album_id})! Retrying in {wait_time:.2f}s...")
                    else:
                        logger.warning(
                            f"Rate limited (Album {album_id}) on final attempt. Cooling down for {wait_time:.2f}s before cancellation."
                        )
                    time.sleep(wait_time)
                else:
                    last_error_code = extract_error_code(e)
                    last_error_detail = str(e)
                    # Other API errors
                    logger.debug(f"Unexpected API error for album {album_id}: {e} (Attempt {attempt+1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(3)
        
        logger.error(f"CANCELLED: Failed to retrieve album {album_id} after {max_retries} attempts.")
        if should_blocklist_failed_fetch(last_error_code, last_error_detail):
            logger.warning(
                f"Blocklisting album {album_id} after repeated fetch failures. "
                f"code={last_error_code}, deezer_response={last_error_detail}"
            )
            try:
                mark_album_metadata_fetch_failed(album_id, last_error_code, logger)
            except Exception as db_err:
                logger.debug(f"Failed to persist album failure state for {album_id}: {db_err}")
        else:
            logger.debug(f"Skipped blocklisting album {album_id} due to transient/non-blocking error ({last_error_code}).")
        return None
    
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
    target_time_per_batch = (api_batch_size / rate_limit) * 60
    
    total_albums = len(album_ids) if hasattr(album_ids, '__len__') else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value('log_interval', 120)
    
    # Track the start time for the batch of requests
    start_time = time.time()
    
    try:
        for i, album_id in enumerate(album_ids, 1):
            try:
                if shutdown_event.is_set():
                    logger.debug("Shutdown acknowledged mid-album collection. Returning partial results.")
                    return cached_albums
                
                # Check rate limiting at configured intervals
                if i % api_batch_size == 0:
                    elapsed_time = time.time() - start_time
                    items_per_second = api_batch_size / elapsed_time if elapsed_time > 0 else 0
                    logger.debug(f"Time taken for {api_batch_size} album requests: {elapsed_time:.2f} seconds ({items_per_second:.2f} items/sec)")
                    
                    # If we're under the target time, sleep to maintain rate limit
                    if elapsed_time < target_time_per_batch:
                        sleep_time = target_time_per_batch - elapsed_time
                        logger.debug(f"Rate limit cooldown: Sleeping for {sleep_time:.2f} seconds to maintain {rate_limit} req/min limit")
                        time.sleep(sleep_time)
                    
                    # Reset the start time for the next batch
                    start_time = time.time()
                
                # Fetch album data using retry helper
                album_obj = fetch_album_with_retry(album_id)
                if not album_obj:
                    # Error message provided in fetch_album_with_retry
                    continue
                
                # Convert to dictionary
                d = album_obj.as_dict()
                
                # Warn if API returned a different album ID (redirect/canonical version)
                if d.get('id') != album_id:
                    logger.debug(f"API redirect: Requested album {album_id}, but API returned {d.get('id')}. Using requested ID to match database stub.")
                
                if identifier == "database":
                    # Full metadata collection
                    albums.append({
                        'id': album_id,  # Use requested ID to match database stub
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
                        'genres': json.dumps(d.get('genres', [])),
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
                        'contributors': json.dumps(d.get('contributors', [])),
                        'artist_id': d.get('artist', {}).get('id'),
                        'artist_name': d.get('artist', {}).get('name'),
                        'date_cached': date_time
                    })
                else:
                    # Partial enrichment (stats) - only refreshable fields
                    albums.append({
                        'id': album_id,  # Use requested ID to match database stub
                        'fans': d.get('fans', 0),
                        'available': d.get('available', True),
                        'date_cached': date_time
                    })
                
                logger.debug(f"Processed album {album_id}: {i}/{total_albums}")

                # If performing full album enrichment, perform periodic checkpoint at chunk_size interval
                if identifier == "database" and i % chunk_size == 0:
                    logger.debug(f"Database Checkpoint: Pushing chunk of {len(albums)} albums to database")
                    logger.debug(f"Album IDs in checkpoint: {[a.get('id') for a in albums]}")
                    try:
                        update_album_metadata(albums, logger)
                        populate_album_genres(albums, logger)
                        for checkpoint_album in albums:
                            if shutdown_event.is_set():
                                logger.debug("Shutdown acknowledged mid-checkpoint track-genre population. Deferring remaining albums to next run.")
                                break
                            try:
                                populate_track_genres_for_album(checkpoint_album.get('id'), logger)
                            except Exception as album_err:
                                logger.warning(f"Failed to populate track genres for album {checkpoint_album.get('id')}: {album_err}")
                        logger.debug(f"Database Checkpoint: update_album_metadata, populate_album_genres, and populate_track_genres_for_album completed successfully.")
                    except Exception as checkpoint_err:
                        logger.error(f"Database Checkpoint: update_album_metadata, populate_album_genres, or populate_track_genres_for_album raised exception: {checkpoint_err}")
                        logger.exception("Stack trace for checkpoint error:")
                        raise

                    # Merge to total result and reset working batch
                    cached_albums.extend(albums)
                    albums = []
                    if shutdown_event.is_set():
                        return cached_albums
                
                # Log progress at configured intervals
                current_time = time.time()
                if current_time - last_log_time >= log_interval:
                    elapsed_time = current_time - start_log_time
                    items_remaining = total_albums - i if isinstance(total_albums, int) else "unknown"
                    
                    if isinstance(total_albums, int):
                        time_per_item = elapsed_time / i
                        eta_seconds = items_remaining * time_per_item
                        eta_str = str(timedelta(seconds=int(eta_seconds)))
                        percent = f"{i/total_albums:.1%}"
                        suffix = f"{percent} ({i}/{total_albums}) complete (ETA: {eta_str})..."
                    else:
                        suffix = f"{i} albums processed..."
                    
                    logger.info(f"Album '{identifier}' enrichment: {suffix}")
                    last_log_time = current_time
                
            except Exception as e:
                logger.debug(f"Non-critical loop error at index {i} (Album {album_id}): {e}")
                time.sleep(1)
                continue
        
        # Full album enrichment cleanup
        if identifier == "database":
            if albums:
                logger.debug(f"Database Cleanup: Saving remaining {len(albums)} albums...")
                logger.debug(f"Album IDs to save: {[a.get('id') for a in albums]}")
                try:
                    update_album_metadata(albums, logger)
                    populate_album_genres(albums, logger)
                    for cleanup_album in albums:
                        if shutdown_event.is_set():
                            logger.debug("Shutdown acknowledged mid-cleanup track-genre population. Deferring remaining albums to next run.")
                            break
                        try:
                            populate_track_genres_for_album(cleanup_album.get('id'), logger)
                        except Exception as album_err:
                            logger.warning(f"Failed to populate track genres for album {cleanup_album.get('id')}: {album_err}")
                    logger.debug(f"Database Cleanup: update_album_metadata, populate_album_genres, and populate_track_genres_for_album call completed successfully.")
                except Exception as cleanup_err:
                    logger.error(f"Database Cleanup: update_album_metadata, populate_album_genres, or populate_track_genres_for_album raised exception: {cleanup_err}")
                    logger.exception("Stack trace for cleanup error:")
                    raise
                cached_albums.extend(albums)

            albums = cached_albums

        logger.debug(f"Successfully transformed {len(albums)} albums.")
        
    except Exception as e:
        logger.error(f"Critical error in get_albums: {e}")
        raise
    
    return albums
