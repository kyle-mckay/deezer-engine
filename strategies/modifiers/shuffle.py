import importlib
import logging
import random
from collections import defaultdict

import random
from collections import defaultdict

def smart_shuffle(logger, current_tracks):
    logger.info(f"Starting smart shuffle for {len(current_tracks)} tracks.")
    
    # Group tracks by artist
    by_artist = defaultdict(list)
    for track in current_tracks:
        # Changed: Accessing the string 'artist' from your data
        by_artist[track['artist']].append(track)
    
    logger.debug(f"Grouped tracks into {len(by_artist)} unique artists.")
    
    # Shuffle within each artist's list
    for artist_id in by_artist:
        random.shuffle(by_artist[artist_id])
    
    # Interleave them 
    shuffled_list = []
    try:
        max_tracks = max(len(t) for t in by_artist.values())
        min_tracks = min(len(t) for t in by_artist.values())
    except ValueError:
        logger.warn("Attempted to shuffle an empty track dictionary.")
        return []

    logger.debug(f"Largest artist bucket size: {max_tracks}.")
    logger.debug(f"Smallest artist bucket size: {min_tracks}. Beginning shuffle.")

    for i in range(max_tracks):
        # Shuffle artist keys
        artists = list(by_artist.keys())
        random.shuffle(artists)
        
        for artist_id in artists:
            if i < len(by_artist[artist_id]):
                shuffled_list.append(by_artist[artist_id][i])
    
    return shuffled_list

import random

def random_shuffle(logger, current_tracks):
    logger.info(f"Starting true random shuffle for {len(current_tracks)} tracks.")
    
    if not current_tracks:
        logger.warn("Attempted to shuffle an empty track list.")
        return []

    # Create a copy to avoid modifying the original list in-place
    shuffled_list = list(current_tracks)
    
    # Standard Fisher-Yates shuffle
    random.shuffle(shuffled_list)
    
    logger.debug("Sequence randomized without artist or album grouping.")
    
    return shuffled_list


def run(client, config, logger, mod_data, current_tracks):
    """
    Shuffle tracks by trying to ensure an artist repeats as infrequently as possible. 
    """
    logger.debug("------ modifiers.shuffle START------")

    sort_order=mod_data.get('order').lower()

    try:
        logger.info(f"Applying '{sort_order}' shuffle")
        match sort_order:
            case "smart":
                shuffled_tracks = smart_shuffle(logger, current_tracks)
            case "random":
                shuffled_tracks = random_shuffle(logger,current_tracks)
            case _:
                logger.warn(f"Shuffle order '{sort_order}' is not supported. Returning tracks with no modification.")
                return current_tracks

    except Exception as e:
        logger.error(f"Failed to shuffle tracks: {e}")
        logger.warn("Tracks will be returned without modification.")
        shuffled_tracks = current_tracks

    logger.debug("------ modifiers.shuffle END------")
    return shuffled_tracks