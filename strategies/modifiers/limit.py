import logging

def normalize_order(logger, order):
    """Normalizes the limit order to either 'top' or 'tail'"""
    logger.debug(f"Normalizing limit order: '{order}'")
    match order:
        case "top" | "head" | "first":
            order = "top"
        case "tail" | "bottom" | "last":
            order = "tail"
        case _:
            logger.warning(f"Unknown limit order: '{order}'. Defaulting to 'top'")
            order = "top"
    return order

def run(client, config, logger, mod_data, current_tracks):
    """
    Slices the track list to return only the top or bottom N tracks.
    """
    logger.debug("------ modifiers.limit START ------")
    
    # Get configuration with defaults
    order = normalize_order(logger, str(mod_data.get('order', 'top')).lower())
    try:
        count = int(mod_data.get('count', len(current_tracks)))
    except (ValueError, TypeError):
        logger.error(f"Invalid count value: {mod_data.get('count')}. Returning all tracks.")
        return current_tracks

    total_available = len(current_tracks)
    logger.debug(f"Limiting dataset to {order} {count} tracks (Total tracks available: {total_available})")

    # Perform the slice
    try:
        if order == "top":
            limited_tracks = current_tracks[:count]
        else:  # tail
            # Handles case where count might be larger than list length
            start_index = max(0, total_available - count)
            limited_tracks = current_tracks[start_index:]
            
    except Exception as e:
        logger.error(f"Failed to limit tracks: {e}")
        return current_tracks

    logger.debug(f"Returned {len(limited_tracks)} tracks")
    logger.debug("------ modifiers.limit END ------")
    return limited_tracks