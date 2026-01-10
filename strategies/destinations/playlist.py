import time
import requests

def run(client, config, logger, dest_data, track_ids):
        """
        Docstring for run
        Retrieve track IDs from a Deezer playlist.
        keys:
          - type: str (the method in which songs will be added to the playlist: 'append' or 'replace')
        """
    target_id = dest_data.get('target')
    method = dest_data.get('type', 'append')
    arl = config.get('config', {}).get('arl_token')

    if not target_id:
        logger.error("Destination 'playlist' requires a 'target'.")
        return

    session = requests.Session()
    session.cookies.set('arl', arl, domain='.deezer.com')

    try:
        # Fetch a fresh copy of the playlist
        playlist = client.get_playlist(target_id)
        logger.info(f"Checking '{playlist.title}' for changes...")
        dst_ids = [t.id for t in playlist.get_tracks()]
        
        # Compare playlist to source tracks
        if dst_ids == track_ids:
            logger.info("Playlist is already perfectly in sync. Skipping.")
            return

        # Perform CSRF Handshake
        api_token_url = "https://www.deezer.com/ajax/gw-light.php?method=deezer.getUserData&api_version=1.0&api_token="
        res = session.get(api_token_url).json()
        api_token = res['results']['checkForm']

        # Determine Sync Strategy
        src_set = set(track_ids)
        dst_set = set(dst_ids)
        
        # Are all current songs still in our source?
        is_subset = dst_set.issubset(src_set)
        
        if is_subset and method == 'replace':
            # SMART APPEND: Only need to add what's missing
            new_tracks = [tid for tid in track_ids if tid not in dst_set]
            if new_tracks:
                logger.info(f"✨ Smart Sync: Appending {len(new_tracks)} new tracks (existing tracks preserved).")
                _internal_add(session, target_id, api_token, new_tracks, client.batch_size, logger)
            else:
                logger.info("All tracks present (likely just a difference in order). Skipping.")
        else:
            # FULL REPLACE: Either tracks were removed from source, or order changed significantly
            logger.info(f"Full Sync: Resetting playlist (Current: {len(dst_ids)} | Desired: {len(track_ids)})")
            if dst_ids:
                _internal_delete(session, target_id, api_token, dst_ids, client.batch_size, logger)
            _internal_add(session, target_id, api_token, track_ids, client.batch_size, logger)

        logger.info(f"Sync complete.")

    except Exception as e:
        logger.error(f"Sync failed: {e}")

def _internal_add(session, playlist_id, token, ids, batch_size, logger):
        """
        Add tracks to a playlist in batches.
        """
    for batch in _chunks(ids, batch_size):
        payload = {"playlist_id": playlist_id, "songs": [[str(tid), 0] for tid in batch], "offset": -1}
        session.post(f"https://www.deezer.com/ajax/gw-light.php?method=playlist.addSongs&api_version=1.0&api_token={token}", json=payload)
        logger.debug(f"Added batch of {len(batch)}")
        time.sleep(0.3)

def _internal_delete(session, playlist_id, token, ids, batch_size, logger):
        """
        Remove tracks from the playlist in batches
        """
    for batch in _chunks(ids, batch_size):
        session.post(f"https://www.deezer.com/ajax/gw-light.php?method=playlist.deleteSongs&api_version=1.0&api_token={token}", json={"playlist_id": playlist_id, "songs": batch})
        logger.debug(f"Deleted batch of {len(batch)}")
        time.sleep(0.3)

def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

