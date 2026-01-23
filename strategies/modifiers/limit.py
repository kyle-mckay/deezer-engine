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
    logger.debug(">>> START: strategies.modifiers.limit.run")
    
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
    logger.debug("<<< END: strategies.modifiers.limit.run")
    return limited_tracks