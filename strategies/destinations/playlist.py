import time
import json
import math
import random
from utils.deezer_auth import get_authenticated_session

def run(client, config, logger, dest_data, tracks):
    """
    Synchronizes tracks to Deezer with high-fidelity browser emulation.
    """
    target_id = str(dest_data.get('target'))
    method = dest_data.get('type', 'smart')
    arl = config.get('config', {}).get('arl_token')
    user_id = str(config.get('config', {}).get('user_id'))

    if not target_id:
        logger.error("Destination 'playlist' requires a 'target' ID.")
        return

    # Use Utility for Auth
    warm_url = f"https://www.deezer.com/us/playlist/{target_id}"
    session, api_token = get_authenticated_session(arl, logger, warm_url)
    
    if not session:
        return

    try:
        playlist = client.get_playlist(target_id)
        
        # Extract IDs from tracks
        track_ids = []
        for track in tracks:
            track_id = str(track.get('id') if isinstance(track, dict) else track.id)
            track_ids.append(track_id)
        
        # Get current tracks from the playlist
        dst_ids = [str(t.id) for t in playlist.get_tracks()]
        current_set = set(dst_ids)
        target_set = set(track_ids)

        # Prepare for Writes
        session.headers.update({
            'x-deezer-user': user_id,
            'Referer': warm_url,
            'Origin': 'https://www.deezer.com'
        })

        # --- SMART STRATEGY ---
        if method in ['smartreplace', 'smart']:
            logger.info(f"Connected to '{playlist.title}'. Running Smart Sync...")
            to_add = [tid for tid in track_ids if str(tid) not in current_set]
            to_remove = [tid for tid in dst_ids if str(tid) not in target_set]
            
            if not to_add and not to_remove:
                logger.info(f"'{playlist.title}' is already in sync.")
                return

            logger.info(f"Analysis: {len(to_add)} to add, {len(to_remove)} to remove.")
            if to_remove:
                _gateway_request(session, "playlist.deleteSongs", target_id, api_token, to_remove, client.batch_size, logger)
            if to_add:
                _gateway_request(session, "playlist.addSongs", target_id, api_token, to_add, client.batch_size, logger)

        # --- APPEND / INSERT STRATEGY ---
        elif method in ['append', 'insert']:
            logger.info(f"Connected to '{playlist.title}'. Appending {len(track_ids)} songs...")
            # Just push the tracks
            _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.batch_size, logger)

        # --- REPLACE STRATEGY ---
        else:
            logger.info(f"Connected to '{playlist.title}'. Performing Full Replace...")
            if dst_ids:
                logger.info(f"Wiping {len(dst_ids)} existing tracks...")
                _gateway_request(session, "playlist.deleteSongs", target_id, api_token, dst_ids, client.batch_size, logger)
                
                # Dynamic wait for cloud consistency
                wait_time = max(math.ceil((len(dst_ids) / 1000) * 10), 5)
                logger.info(f"Waiting {wait_time}s for database to clear...")
                time.sleep(wait_time)
            
            if track_ids:
                logger.info(f"Injecting {len(track_ids)} new tracks...")
                _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.batch_size, logger)

        logger.info(f"Strategy '{method}' complete for '{playlist.title}'.")

    except Exception as e:
        logger.error(f"Sync failed: {e}")

def _gateway_request(session, method, playlist_id, token, ids, batch_size, logger):
    """
    Handles batch communication with the Deezer Gateway.
    """
    total = len(ids)
    count = 0
    verb = "Removing" if "delete" in method else "Adding"

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        cid = random.randint(100000000, 999999999)
        url = f"https://www.deezer.com/ajax/gw-light.php?method={method}&input=3&api_version=1.0&api_token={token}&cid={cid}"
        
        batch_ids = [int(tid) for tid in batch]
        
        # Log IDs for debug mode
        if logger.isEnabledFor(10): # DEBUG
            logger.debug(f"Batch Processing IDs: {batch_ids}")

        payload = {
            "playlist_id": str(playlist_id),
            "songs": [[tid, 0] for tid in batch_ids],
            "ctxt": {"id": int(playlist_id), "t": "playlist_page"}
        }
        
        if "addSongs" in method:
            payload["offset"] = -1 # Always appends to end

        try:
            resp = session.post(url, data=json.dumps(payload)).json()
            if resp.get('error'):
                logger.error(f"Gateway Error: {resp['error']}")
            else:
                count += len(batch)
                logger.info(f"{verb} songs... {count}/{total} complete.")
        except Exception as e:
            logger.error(f"Network request failed: {e}")
        
        time.sleep(0.5)