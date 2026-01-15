import sys
import deezer
import logging
import requests
import random
import logging
import json
from utils.logger import setup_logger
from utils.paths import _cleanup_old_caches

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
    
def get_tracks(client, logger, type, var, cache_file):

    logger.debug(f"Getting tracks for type '{type}' with ID '{var}'")


    if isinstance(var, str) and var.startswith("playlist__"):
        # Split the string by "__"
        parts = var.split("__")
        
        if len(parts) >= 3:
            var = parts[0]
            display_name = parts[1].replace("_", " ")
            playlist_id = parts[2]
            logger.debug(f"Parsed var: Name='{display_name}', ID='{playlist_id}'")

    tracks = []

    # Extract full track metadata
    for i, track in enumerate(client, 1):
            d = track.as_dict()
            
            tracks.append({
                'id': str(d.get('id')),
                'title': d.get('title'),
                'artist': d.get('artist', {}).get('name', 'Unknown'),
                'album': d.get('album', {}).get('title', 'Unknown'),
                'duration': d.get('duration', 0),
                'preview': d.get('preview'),
            })

            # Every 250 tracks, let the user know the progress
            if i % 250 == 0:
                if type == "favorites":
                    logger.info(f"Scanning favorites... cached {i} tracks.")
                elif var == "playlist":
                    logger.info(f"Scanning '{display_name}'... cached {i} tracks.")
                    var = playlist_id
                # Fallback
                else:
                    logger.info(f"Scanning {type}... cached {i} tracks.")
    
    # Remove old files for this ID (e.g., if the playlist was renamed)
    _cleanup_old_caches(type, var, cache_file, logger)

    if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Successfully fetched {len(tracks)} tracks.")
            logger.debug(f"Updating cache file {cache_file} with {len(tracks)} tracks.")
            
    with open(cache_file, 'w') as f:
        json.dump(tracks, f)

    return tracks