import logging

def run(client, config, logger, mod_data, current_tracks,source_name=None):
    """
    Removes duplicate track IDs from the pipeline
    """
    logger.debug(">>> START: strategies.modifiers.dedupe.run")

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

        if duplicate_count > 0:
            logger.info(f"Dedupe applied: Removed {duplicate_count} duplicate tracks.")
        else:
            logger.info("Dedupe applied: No duplicates found.")

        logger.debug(f"Final pipeline count: {len(deduplicated_list)}")
        logger.debug("<<< END: strategies.modifiers.dedupe.run")
        return deduplicated_list

    except Exception as e:
        logger.error(f"Failed to perform deduplication: {e}")
        logger.debug("Traceback for dedupe failure:", exc_info=True)
        # Return original list as safety net
        return current_tracks