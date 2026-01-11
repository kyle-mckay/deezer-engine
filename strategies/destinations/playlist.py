import time
import json
import logging
import math
import random
from utils.deezer_auth import get_authenticated_session

def run(client, config, logger, dest_data, track_ids):
    """
    Synchronizes tracks to Deezer with high-fidelity browser emulation.
    """
    target_id = str(dest_data.get('target'))
    method = dest_data.get('type', 'replace')
    arl = config.get('config', {}).get('arl_token')
    user_id = str(config.get('config', {}).get('user_id'))

    # Use Utility for Auth
    warm_url = f"https://www.deezer.com/us/playlist/{target_id}"
    session, api_token = get_authenticated_session(arl, logger, warm_url)
    
    if not session:
        return

    try:
        playlist = client.get_playlist(target_id)
        logger.info(f"Connected to '{playlist.title}'. Checking changes...")
        dst_ids = [t.id for t in playlist.get_tracks()]
        
        if dst_ids == track_ids:
            logger.info("Up to date.")
            return

        # Prepare for Writes
        session.headers.update({
            'x-deezer-user': user_id,
            'Referer': warm_url,
            'Origin': 'https://www.deezer.com'
        })

        # Perform Synchronization
        src_set = set(track_ids)
        dst_set = set(dst_ids)
        
        if dst_set.issubset(src_set) and method == 'replace':
            # SMART SYNC: Only add what is missing
            new_tracks = [tid for tid in track_ids if tid not in dst_set]
            if new_tracks:
                logger.info(f"Smart Sync: Adding {len(new_tracks)} new songs to '{playlist.title}'...")
                _gateway_request(session, "playlist.addSongs", target_id, api_token, new_tracks, client.batch_size, logger)
            else:
                logger.info("Tracks are present but order differs. Sync skipped.")
        else:
            # FULL REPLACE
            logger.info(f"Full Sync: Rebuilding '{playlist.title}' to match your strategy.")
            
            if dst_ids:
                num_removed = len(dst_ids)
                logger.info(f"Step 1/2: Removing {num_removed} songs...")
                _gateway_request(session, "playlist.deleteSongs", target_id, api_token, dst_ids, client.batch_size, logger)
                
                # Dynamic Buffer: 10s for every 1000 songs.
                # Example: 909 songs -> (909/1000)*10 = 9.09s -> math.ceil(9.09) = 10s
                wait_time = math.ceil((num_removed / 1000) * 10)
                
                # Safety Floor: Ensure we always wait at least 5 seconds if tracks were removed
                wait_time = max(wait_time, 5)
                
                logger.info(f"Waiting {wait_time}s for Deezer to process removals...")
                time.sleep(wait_time)
            
            if track_ids:
                logger.info(f"Step 2/2: Adding {len(track_ids)} songs...")
                _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.batch_size, logger)

        logger.info(f"Sync complete for '{playlist.title}'.")

    except Exception as e:
        logger.error(f"Sync interrupted: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Full technical traceback:")

def _gateway_request(session, method, playlist_id, token, ids, batch_size, logger):
    """
    Handles batch communication with the Deezer Gateway.
    - INFO: Shows user-friendly progress (e.g. Adding songs... 50/1125).
    - DEBUG: Shows technical batch data and the specific Track IDs being processed.
    """
    total = len(ids)
    count = 0
    verb = "Removing" if "delete" in method else "Adding"

    for batch in _chunks(ids, batch_size):
        # Generate a unique CID for every single request to maintain browser authenticity
        cid = random.randint(100000000, 999999999)
        url = f"https://www.deezer.com/ajax/gw-light.php?method={method}&input=3&api_version=1.0&api_token={token}&cid={cid}"
        
        # Casting Track IDs to integers is critical for Gateway acceptance
        batch_ids = [int(tid) for tid in batch]

        # Debug: Log the specific IDs being sent in this batch
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Batch Request: {method} | Playlist: {playlist_id} | CID: {cid}")
            logger.debug(f"Processing Track IDs: {batch_ids}")

        payload = {
            "playlist_id": str(playlist_id),
            "songs": [[tid, 0] for tid in batch_ids],
            "ctxt": {"id": int(playlist_id), "t": "playlist_page"}
        }
        
        if "addSongs" in method:
            payload["offset"] = -1

        try:
            # We send as a raw string to match the browser's 'text/plain' content-type
            resp = session.post(url, data=json.dumps(payload)).json()
            
            if resp.get('error'):
                logger.error(f"Deezer Gateway Error ({method}): {resp['error']}")
                logger.debug(f"Failed Payload: {json.dumps(payload)}")
            else:
                count += len(batch)
                logger.info(f"{verb} songs... {count}/{total} complete.")
        
        except Exception as e:
            logger.error(f"Network error during {method}: {e}")
        
        # Pace the requests to avoid server-side rate limiting
        time.sleep(0.5)

def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]