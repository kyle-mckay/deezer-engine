import sys
import deezer
import logging
import requests
import random
import time
import logging
import json
from datetime import datetime
from utils.logger import setup_logger
from utils.config_loader import get_global_value

def get_authenticated_client(config, logger):
    """
    Initializes the Deezer Client using an ARL cookie.
    """
    logger.debug(">>> START: utils.deezer_auth.get_authenticated_client")
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

    # Read batch size from config (default: 50)
    batch_size = config.get('config', {}).get('batch_size', 50)
    logger.debug(f"Global batch size set to: {batch_size}")

    try:
        logger.debug("Attempting to instantiate deezer.Client...")
            
        client = deezer.Client(headers=headers)
        
        # Store the batch size on the client for later use
        client.batch_size = batch_size

        # Test connection using the numeric user_id
        if user_id:
            logger.debug(f"Testing connection for User ID: {user_id}")
                
            user = client.get_user(user_id)
            logger.info(f"Authenticated successfully as: {user.name}")
            
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
    finally:
        logger.debug("<<< END: utils.deezer_auth.get_authenticated_client")

def get_authenticated_session(arl, logger, warm_url=None):
    """
    Creates a session, establishes context via a pre-flight GET, 
    and performs the CSRF handshake to return (session, api_token).
    """
    logger.debug(">>> START: utils.deezer_auth.get_authenticated_session")
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
    finally:
        logger.debug("<<< END: utils.deezer_auth.get_authenticated_session")

def get_tracks(client, logger, source_type, identifier, cache_file=None, track_ids=None):
    """
    Transforms Deezer API objects into a list of dictionaries with rate-limiting protection.
    """
    logger.debug(f">>> START: utils.deezer_auth.get_tracks ({source_type})")
    logger.debug(f"Getting tracks for type '{source_type}' with ID '{identifier}'")

    def fetch_track_with_retry(t_id, max_retries=5):
        """
        Helper to fetch track data handling both Rate Limits and Network Drops.
        """
        for attempt in range(max_retries):
            try:
                # Small jitter to keep requests non-rhythmic
                time.sleep(random.uniform(0.2, 0.5))
                return client.get_track(t_id)
            
            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as net_err:
                wait_time = (5 * (attempt + 1))  # 5s, 10s, 15s...
                logger.debug(f"Network retry (Track {t_id}): {net_err}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                
            except Exception as e:
                # Check for rate limiting in the error message
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    # Rate limits remain WARNING to notify user of throttling
                    logger.warning(f"Rate limited (Track {t_id})! Retrying in {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    # Other API errors
                    logger.debug(f"Unexpected API error for {t_id}: {e} (Attempt {attempt+1}/{max_retries})")
                    time.sleep(3)
        
        logger.error(f"CANCELLED: Failed to retrieve track {t_id} after {max_retries} attempts.")
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
    
    if logger.isEnabledFor(logging.DEBUG):
        update_int = 1
    else:
        update_int = get_global_value('batch_size', default=50)
    
    total_len = len(iterable) if hasattr(iterable, '__len__') else "unknown"

    for i, track in enumerate(iterable, 1):
        try:
            # Every 40 requests, take a longer pause to prevent sustained high-load triggers
            if i % 40 == 0:
                logger.debug("Cooldown period: Sleeping for 3 seconds to respect API limits...")
                time.sleep(3)

            if source_type == "database" and (identifier == "tracks" or identifier == "stats"):
                t_id = track.get('id') if isinstance(track, dict) else track
                
                # Use the retry helper for heavy metadata fetching
                track_obj = fetch_track_with_retry(t_id)
                if not track_obj:
                    # Error message provided in fetch_track_with_retry
                    continue
                    
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
                # fetch for source ID collection
                d = track.as_dict()
                tracks.append({
                    'id': str(d.get('id')),
                    'collection': f"{collection}",
                    'date_cached': date_time
                })

            # Progress logging
            if i % update_int == 0 | logger.isEnabledFor(logging.DEBUG):
                progress_str = f"{i}/{total_len}"

            if i % update_int == 0:
                if source_type == "database":
                    logger.info(f"Database '{identifier}' enrichment: processed {progress_str} tracks.")
                elif source_type == "favorites":
                    logger.info(f"Scanning favorites: processed {progress_str} tracks.")
                elif identifier.startswith("playlist__") or identifier.startswith("album__"):
                    logger.info(f"Scanning '{display_name}': processed {progress_str} tracks.")
                else:
                    logger.info(f"Scanning {source_type}: processed {progress_str} tracks.")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Processed track {track}: {progress_str}")

        except Exception as e:
            logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
            time.sleep(1)
            continue

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Successfully transformed {len(tracks)} tracks.")
    
    logger.debug("<<< END: utils.deezer_auth.get_tracks")
    return tracks