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
import time
import json
import os
import math
import random
from utils.deezer_auth import get_authenticated_session

def run(client, config, logger, dest_data, tracks):
    """
    Synchronizes tracks to Deezer with high-fidelity browser emulation.
    """
    logger.debug(">>> START: strategies.destinations.playlist.run")
    target_id = str(dest_data.get('id'))
    method = dest_data.get('order', 'smart')
    arl = config.get('config', {}).get('arl_token')
    user_id = str(config.get('config', {}).get('user_id'))

    if not target_id:
        logger.error("Destination 'playlist' requires a playlist 'ID'.")
        return

    # Use Utility for Auth
    logger.debug(f"Authenticating for playlist {target_id} using ARL and UserID: {user_id}")
    warm_url = f"https://www.deezer.com/us/playlist/{target_id}"
    session, api_token = get_authenticated_session(arl, logger, warm_url)
    
    if not session:
        logger.debug("Failed to obtain authenticated session.")
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
        
        logger.debug(f"Targeting playlist: '{playlist.title}' (ID: {target_id})")
        logger.debug(f"Current playlist size: {len(dst_ids)} | Target size: {len(track_ids)}")

        # Prepare for Writes
        session.headers.update({
            'x-deezer-user': user_id,
            'Referer': warm_url,
            'Origin': 'https://www.deezer.com'
        })

        # --- SMART STRATEGY ---
        if method in ['smartreplace', 'smart']:
            logger.info(f"Syncing '{playlist.title}' (Smart Sync)")
            to_add = [tid for tid in track_ids if str(tid) not in current_set]
            to_remove = [tid for tid in dst_ids if str(tid) not in target_set]
            
            if not to_add and not to_remove:
                logger.info(f"Playlist '{playlist.title}' is already up to date.")
                return

            logger.debug(f"Smart Sync - To Add: {to_add}")
            logger.debug(f"Smart Sync - To Remove: {to_remove}")
            
            if to_remove:
                logger.info(f"Removing {len(to_remove)} tracks...")
                _gateway_request(session, "playlist.deleteSongs", target_id, api_token, to_remove, client.batch_size, logger)
            if to_add:
                logger.info(f"Adding {len(to_add)} tracks...")
                _gateway_request(session, "playlist.addSongs", target_id, api_token, to_add, client.batch_size, logger)

        # --- APPEND / INSERT STRATEGY ---
        elif method in ['append', 'insert']:
            logger.info(f"Syncing '{playlist.title}' (Appending {len(track_ids)} tracks)")
            _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.batch_size, logger)

        # --- REPLACE STRATEGY ---
        else:
            logger.info(f"Syncing '{playlist.title}' (Full Replace)")
            if dst_ids:
                logger.debug(f"Wiping existing {len(dst_ids)} tracks for clean replace.")
                _gateway_request(session, "playlist.deleteSongs", target_id, api_token, dst_ids, client.batch_size, logger)
                
                # Dynamic wait for cloud consistency
                wait_time = max(math.ceil((len(dst_ids) / 1000) * 10), 5)
                logger.debug(f"Cooldown: Waiting {wait_time}s for cloud database consistency...")
                time.sleep(wait_time)
            
            if track_ids:
                logger.info(f"Injecting {len(track_ids)} tracks...")
                _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.batch_size, logger)

        logger.info(f"Sync complete for '{playlist.title}'.")
        logger.debug("<<< END: strategies.destinations.playlist.run")

    except Exception as e:
        logger.error(f"Sync failed for '{target_id}': {e}")
        logger.debug("Traceback:", exc_info=True)

def _gateway_request(session, method, playlist_id, token, ids, batch_size, logger):
    """
    Handles batch communication with the Deezer Gateway.
    """
    total = len(ids)
    count = 0
    verb = "Removed" if "delete" in method else "Added"

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        cid = random.randint(100000000, 999999999)
        url = f"https://www.deezer.com/ajax/gw-light.php?method={method}&input=3&api_version=1.0&api_token={token}&cid={cid}"
        
        batch_ids = [int(tid) for tid in batch]
        
        logger.debug(f"Gateway Call ({method}): Processing batch of {len(batch_ids)} tracks.")

        payload = {
            "playlist_id": str(playlist_id),
            "songs": [[tid, 0] for tid in batch_ids],
            "ctxt": {"id": int(playlist_id), "t": "playlist_page"}
        }
        
        if "addSongs" in method:
            payload["offset"] = -1 # Always appends to end

        try:
            raw_resp = session.post(url, data=json.dumps(payload))
            resp = raw_resp.json()
            
            if resp.get('error'):
                logger.error(f"Deezer Gateway Error: {resp['error']}")
                logger.debug(f"Failed Payload: {json.dumps(payload)}")
            else:
                count += len(batch)
                logger.debug(f"Batch success. Progress: {count}/{total}")
        except Exception as e:
            logger.error(f"Network request failed during {method}: {e}")
        
        time.sleep(0.5)
    
    logger.info(f"Done: {verb} {count} tracks.")