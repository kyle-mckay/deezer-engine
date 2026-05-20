# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
import logging
import random
from collections import defaultdict
from utils.metadata.orchestration import update_unprocessed

def smart_shuffle(logger, current_tracks, client=None):
    logger.debug(f"Initiating smart shuffle for {len(current_tracks)} tracks.")
    # Group tracks by artist
    by_artist = defaultdict(list)
    for track in current_tracks:
        artist_key = track.get('artist_id') or track.get('artist_name', 'Unknown Artist')
        by_artist[artist_key].append(track)
    
    logger.debug(f"Grouped tracks into {len(by_artist)} unique artist buckets.")
    
    # Shuffle within each artist's list to ensure variety if the same artist appears twice
    for artist_id in by_artist:
        random.shuffle(by_artist[artist_id])
    
    # Interleave them 
    shuffled_list = []
    try:
        bucket_sizes = [len(t) for t in by_artist.values()]
        max_tracks = max(bucket_sizes)
        min_tracks = min(bucket_sizes)
    except ValueError:
        logger.debug("Smart shuffle received an empty track dictionary.")
        return []

    logger.debug(f"Shuffle Stats - Largest bucket: {max_tracks} | Smallest bucket: {min_tracks}")

    for i in range(max_tracks):
        # Shuffle artist keys each iteration to vary the sequence of the "interleave"
        artists = list(by_artist.keys())
        random.shuffle(artists)
        
        for artist_id in artists:
            if i < len(by_artist[artist_id]):
                shuffled_list.append(by_artist[artist_id][i])
    
    logger.debug(f"Smart shuffle complete. Interleaved {len(shuffled_list)} tracks.")
    return shuffled_list

def random_shuffle(logger, current_tracks):
    if not current_tracks:
        logger.debug("Random shuffle received an empty track list.")
        return []

    logger.debug(f"Performing true random (Fisher-Yates) shuffle on {len(current_tracks)} tracks.")

    # Create a copy to avoid modifying the original list in-place
    shuffled_list = list(current_tracks)
    random.shuffle(shuffled_list)
    
    logger.debug("Sequence randomized successfully.")
    return shuffled_list


def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Shuffle tracks by trying to ensure an artist repeats as infrequently as possible. 
    """
    shuffle_type = mod_data.get('order', 'random').lower()

    try:
        logger.info(f"Action: Shuffling with '{shuffle_type}' shuffle.")
        match shuffle_type:
            case "smart":
                shuffled_tracks = smart_shuffle(logger, current_tracks, client)
            case "random":
                shuffled_tracks = random_shuffle(logger,current_tracks)
            case _:
                logger.warning(f"Shuffle type '{shuffle_type}' not supported. Skipping.")
                return current_tracks

    except Exception as e:
        logger.error(f"Failed to shuffle tracks: {e}")
        logger.debug("Error details:", exc_info=True)
        shuffled_tracks = current_tracks

    return shuffled_tracks