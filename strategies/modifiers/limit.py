# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

def normalize_order(logger, order):
    """Normalizes the limit order to either 'top' or 'tail'"""
    logger.debug(f"Normalizing limit order string: '{order}'")
    match order:
        case "top" | "head" | "first":
            order = "top"
        case "tail" | "bottom" | "last":
            order = "tail"
        case _:
            logger.debug(f"Order '{order}' not recognized. Falling back to 'top'.")
            order = "top"
    return order

def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Slices the track list to return only the top or bottom N tracks.
    """
    # Get configuration with defaults
    order = normalize_order(logger, str(mod_data.get('order', 'top')).lower())
    total_available = len(current_tracks)
    
    try:
        count = int(mod_data.get('count', total_available))
    except (ValueError, TypeError):
        logger.error(f"Invalid count value: {mod_data.get('count')}. Returning all tracks.")
        return current_tracks

    logger.debug(f"Limit Config: {order} {count} | Current Pipeline Size: {total_available}")

    # Perform the slice
    try:
        if count >= total_available:
            logger.info(f"Action: Limit not required")
            return current_tracks

        if order == "top":
            logger.debug(f"Slicing tracks from index 0 to {count}")
            limited_tracks = current_tracks[:count]
        else:  # tail
            # Handles case where count might be larger than list length
            start_index = max(0, total_available - count)
            logger.debug(f"Slicing tracks from index {start_index} to {total_available}")
            limited_tracks = current_tracks[start_index:]
            
        logger.info(f"Action: Limited to '{order}' {len(limited_tracks)} tracks.")
            
    except Exception as e:
        logger.error(f"Failed to limit tracks: {e}")
        logger.debug("Exception details:", exc_info=True)
        return current_tracks

    logger.debug(f"Limit complete. Pipeline size: {len(limited_tracks)}")
    return limited_tracks