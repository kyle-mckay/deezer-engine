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
import math
import random
from datetime import timedelta

from utils.infrastructure.signals import shutdown_event
from utils.api.playlist import fetch_playlist_info, fetch_playlist_track_ids, update_playlist
from utils.collections import get_collection_name, sync_to_collections, is_collection_cached, fetch_collection
from utils.config import get_global_value

_VISIBILITY_VALUES = ('public', 'private', 'collaborative')

def _normalize_visibility(value):
    """
    Normalize a visibility string to 'public', 'private', or 'collaborative'.
    Accepts unambiguous prefixes and abbreviations (e.g. 'pub', 'pri', 'col', 'collab').
    Returns None and logs nothing if value is None; returns the canonical string on success.
    Raises ValueError on ambiguous or unrecognised input.
    """
    v = str(value).strip().lower()
    if v in _VISIBILITY_VALUES:
        return v
    matches = [k for k in _VISIBILITY_VALUES if k.startswith(v)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous visibility '{value}': matches {matches}. Use a longer prefix.")
    raise ValueError(f"Unknown visibility '{value}'. Must be one of: {', '.join(_VISIBILITY_VALUES)}.")


def requires_metadata(dest_data=None):
    return False

def run(client, config, logger, dest_data, tracks):
    """
    Synchronizes tracks to Deezer with high-fidelity browser emulation.
    """
    target_id = str(dest_data.get('id'))
    method = dest_data.get('order', 'smart')
    user_id = str(config.get('config', {}).get('user_id', ''))

    if not target_id:
        logger.error("Destination 'playlist' requires a playlist 'ID'.")
        return

    session = client.session
    api_token = client.api_token
    if not session or not api_token:
        logger.error("Playlist destination requires an authenticated session on the client.")
        return

    logger.debug(
        f"Playlist destination start: target_id={target_id}, method={method}, incoming_tracks={len(tracks)}"
    )

    try:
        collection = get_collection_name(logger, "playlist", id=target_id)

        # Resolve playlist title — deezer-python first, web API fallback for private playlists
        playlist_title, _playlist_obj = _resolve_playlist_title(client, target_id, logger)
        if playlist_title is None:
            logger.error(f"Failed to retrieve playlist info for {target_id}.")
            return

        # Extract IDs from incoming tracks
        track_ids = [
            str(track.get('id') if isinstance(track, dict) else track.id)
            for track in tracks
        ]

        # Get current tracks from the playlist
        if is_collection_cached(collection, dest_data, logger):
            logger.debug(f"Using cached collection for playlist {target_id}")
            current_set = set(str(track['id']) for track in fetch_collection(collection, logger))
        elif _playlist_obj is not None:
            logger.debug(f"Fetching current tracks for playlist {target_id} via deezer-python")
            current_set = set(str(t.id) for t in _playlist_obj.get_tracks())
        else:
            logger.debug(f"Fetching current tracks for playlist {target_id} via gw-light")
            current_set = set(fetch_playlist_track_ids(client, target_id, logger))

        target_set = set(track_ids)

        logger.debug(f"Targeting playlist: '{playlist_title}' (ID: {target_id})")
        logger.debug(f"Current playlist size: {len(current_set)} | Target size: {len(target_set)}")

        # Tag session with user identity for write operations
        playlist_url = f"https://www.deezer.com/us/playlist/{target_id}"
        session.headers.update({
            'x-deezer-user': user_id,
            'Referer': playlist_url,
            'Origin': 'https://www.deezer.com',
        })

        # --- SMART STRATEGY ---
        if method in ['smartreplace', 'smart']:
            logger.info(f"Syncing {len(tracks)} to '{playlist_title}' (Smart Sync)")
            to_add = [tid for tid in target_set if str(tid) not in current_set]
            to_remove = [tid for tid in current_set if str(tid) not in target_set]
            
            if not to_add and not to_remove:
                # Already in sync
                logger.debug(f"Smart Sync not needed for '{playlist_title}' - already in sync.")
            else:
                logger.debug(f"Smart Sync - To Add: {to_add}")
                logger.debug(f"Smart Sync - To Remove: {to_remove}")
                
                if to_remove:
                    logger.debug(f"Removing {len(to_remove)} tracks...")
                    _gateway_request(session, "playlist.deleteSongs", target_id, api_token, to_remove, client.chunk_size, logger)
                if to_add:
                    logger.debug(f"Adding {len(to_add)} tracks...")
                    _gateway_request(session, "playlist.addSongs", target_id, api_token, to_add, client.chunk_size, logger)

        # --- APPEND / INSERT STRATEGY ---
        elif method in ['append', 'insert']:
            logger.info(f"Syncing {len(tracks)} to '{playlist_title}' (Appending)")
            _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.chunk_size, logger)

        # --- REPLACE STRATEGY ---
        else:
            logger.info(f"Syncing {len(tracks)} tracks to '{playlist_title}' (Full Replace)")
            if current_set:
                logger.debug(f"Wiping existing {len(current_set)} tracks for clean replace.")
                _gateway_request(session, "playlist.deleteSongs", target_id, api_token, current_set, client.chunk_size, logger)
                
                # Dynamic wait for cloud consistency
                wait_time = max(math.ceil((len(current_set) / 1000) * 10), 5)
                logger.debug(f"Cooldown: Waiting {wait_time}s for cloud database consistency...")
                time.sleep(wait_time)
            
            if track_ids:
                logger.debug(f"Injecting {len(track_ids)} tracks...")
                _gateway_request(session, "playlist.addSongs", target_id, api_token, track_ids, client.chunk_size, logger)

        logger.info(f"Sync complete for '{playlist_title}'.")
        logger.debug(
            f"Playlist destination end: target_id={target_id}, method={method}, "
            f"target_unique={len(target_set)}"
        )

        sync_to_collections(tracks, logger, collection)

        # Optional metadata update — only runs if any of the keys are set
        new_title = dest_data.get('title')
        new_description = dest_data.get('description')
        new_visibility_raw = dest_data.get('visibility')

        new_is_private = None
        new_is_collaborative = None
        if new_visibility_raw is not None:
            try:
                vis = _normalize_visibility(new_visibility_raw)
                new_is_private = vis == 'private'
                new_is_collaborative = vis == 'collaborative'
            except ValueError as e:
                logger.warning(f"Playlist destination: {e} Skipping visibility change.")
                new_visibility_raw = None  # prevent changes list from including it

        if any(v is not None for v in [new_title, new_description, new_visibility_raw]):
            changes = []
            if new_title is not None:
                changes.append(f"title='{new_title}'")
            if new_description is not None:
                changes.append(f"description='{new_description}'")
            if new_visibility_raw is not None:
                changes.append(f"visibility={_normalize_visibility(new_visibility_raw)}")
            try:
                update_playlist(
                    client, target_id, logger,
                    title=new_title,
                    description=new_description,
                    is_private=new_is_private,
                    is_collaborative=new_is_collaborative,
                )
                logger.info(f"Playlist metadata updated for '{playlist_title}': {', '.join(changes)}.")
            except RuntimeError as e:
                logger.warning(f"Playlist metadata update skipped: {e}")

    except Exception as e:
        logger.error(f"Sync failed for '{target_id}': {e}")
        logger.debug("Traceback:", exc_info=True)

def _resolve_playlist_title(client, playlist_id, logger):
    """
    Try deezer-python first; fall back to the gw-light web API for private playlists.
    Returns (title_str, playlist_obj_or_None).
    Returns (None, None) if both paths fail.
    """
    try:
        playlist_obj = client.get_playlist(playlist_id)
        logger.debug(f"Resolved playlist '{playlist_obj.title}' via deezer-python.")
        return playlist_obj.title, playlist_obj
    except Exception as e:
        logger.debug(
            f"deezer-python failed for playlist {playlist_id} ({e}); "
            "falling back to gw-light."
        )

    info = fetch_playlist_info(client, playlist_id, logger)
    if info is None:
        return None, None
    return info['title'], None


def _gateway_request(session, method, playlist_id, token, ids, chunk_size, logger):
    """
    Processes playlist operations in chunks to avoid API limits.
    """
    ids = list(ids)
    total = len(ids)
    count = 0
    verb = "Removed" if "delete" in method else "Added"
    total_batches = (total + chunk_size - 1) // chunk_size if chunk_size else 0
    logger.debug(
        f"Gateway request start: method={method}, playlist_id={playlist_id}, tracks={total}, "
        f"chunk_size={chunk_size}, batches={total_batches}"
    )
    
    current_time = time.time()
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value('log_interval',120)
    total_tracks = len(ids)
    for i in range(0, len(ids), chunk_size):

        if shutdown_event.is_set():
            logger.warning(f"Interrupt detected. Stopping playlist update.")
            break

        batch = ids[i:i + chunk_size]
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
        
        # Inform user during long waits
        current_time = time.time()
        if current_time - last_log_time >= log_interval:
            # 1. Calculate progress
            elapsed_time = current_time - start_log_time
            items_remaining = total_tracks - i
            
            # 2. Calculate average time and ETA
            time_per_item = elapsed_time / i
            eta_seconds = items_remaining * time_per_item
            
            # 3. Format seconds
            eta_str = str(timedelta(seconds=int(eta_seconds)))
            percent = f"{i/total_tracks:.1%}"

            # 4. Create suffix
            suffix = f"{percent} complete (ETA: {eta_str})..."
            if verb == "Added":
                logger.info(f"Adding {total_tracks} tracks to playlist': {suffix}")
            elif verb == "Removed":
                logger.info(f"Removing {total_tracks} tracks from playlist: {suffix}")
            last_log_time = current_time 
        time.sleep(0.5)
    
    logger.debug(f"Gateway request end: method={method}, {verb.lower()}={count}, requested={total}")