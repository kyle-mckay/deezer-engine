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
from utils.cache_manager import _cleanup_old_caches
from utils.config_loader import get_global_value

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
    Transforms Deezer API objects into a list of dictionaries.
    """
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
    # If track_ids is provided, we fetch full objects for those IDs
    iterable = track_ids if track_ids is not None else client

    # Extract full track metadata
    date_time=datetime.now().isoformat()
    if source_type == "favorites":
        collection = source_type
    elif source_type != "database":
        collection = f"{item_type}__{item_id}"
    update_int = get_global_value('batch_size')
    for i, track in enumerate(iterable, 1):
        try:
            if source_type == "database":
                # Fetch full metadata only for database enrichment
                t_id = track.get('id') if isinstance(track, dict) else track
                track_obj = client.get_track(t_id)
                d = track_obj.as_dict()
                
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
            else:
                # fetch for source ID collection
                d = track.as_dict()
                tracks.append({
                    'id': str(d.get('id')),
                    'collection': f"{collection}",
                    'date_cached': date_time
                })

            # Give the user an update every n tracks, where n is their batch_size
            if i % update_int == 0:
                if source_type == "database":
                    logger.info(f"Database enrichment: processed {i}/{len(iterable)} tracks.")
                elif source_type == "favorites":
                    logger.info(f"Scanning favorites... processed {i}/{len(iterable)} tracks.")
                elif identifier.startswith("playlist__"):
                    logger.info(f"Scanning '{display_name}'... processed {i}/{len(iterable)} tracks.")
                elif identifier.startswith("album__"):
                    logger.info(f"Scanning '{display_name}'... processed {i}/{len(iterable)} tracks.")
                else:
                    logger.info(f"Scanning {source_type}... processed {i}/{len(iterable)} tracks.")

        except Exception as e:
            logger.error(f"Error processing track at index {i}: {e}")
            continue
    
    # Remove old files for this ID (e.g., if the playlist was renamed)
    try:
        from utils.cache_manager import _cleanup_old_caches
        _cleanup_old_caches(source_type, item_id, cache_file, logger)
    except ImportError:
        pass

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Successfully transformed {len(tracks)} tracks.")
    
    time.sleep(0.5)
    return tracks