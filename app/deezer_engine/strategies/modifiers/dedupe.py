# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

def requires_metadata(mod_data=None):
    """
    Only needs track IDs, no metadata enrichment required.
    """
    return False

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