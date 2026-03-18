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

def run(client, config, logger, mod_data, current_tracks,source_name=None):
    """
    Removes duplicate track IDs from the pipeline
    """
    if not current_tracks:
        logger.debug("Dedupe modifier received an empty track list. Skipping.")
        return []

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Scanning {len(current_tracks)} tracks for duplicate IDs.")

    try:
        # Use a set to track what we've seen, but iterate through the list and keep order
        seen = set()
        deduplicated_list = []
        
        duplicate_count = 0
        
        for track in current_tracks:
            track_id = str(track.get('id') if isinstance(track, dict) else track.id)
            if track_id not in seen:
                deduplicated_list.append(track)
                seen.add(track_id)
            else:
                duplicate_count += 1
                logger.debug(f"Duplicate found and removed: {track_id}")

        logger.info(f"Action: Deduplicated {duplicate_count} tracks")

        logger.debug(f"Final pipeline count: {len(deduplicated_list)}")
        return deduplicated_list

    except Exception as e:
        logger.error(f"Failed to perform deduplication: {e}")
        logger.debug("Traceback for dedupe failure:", exc_info=True)
        # Return original list as safety net
        return current_tracks