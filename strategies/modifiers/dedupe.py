import logging

def run(client, config, logger, mod_data, current_tracks):
    """
    Removes duplicate track IDs from the pipeline
    """
    logger.debug("------ modifiers.dedupe START------")
    logger.info("Applying 'dedupe' modifier...")

    if not current_tracks:
        logger.warning("Dedupe modifier received an empty track list.")
        return []

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Dedupe phase started. Initial pipeline count: {len(current_tracks)}")

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
                if logger.isEnabledFor(logging.DEBUG) and duplicate_count <= 5:
                    logger.debug(f"Found duplicate track ID: {track_id}")

        if duplicate_count > 0:
            logger.info(f"Dedupe complete: Removed {duplicate_count} duplicate songs.")
        else:
            logger.info("Dedupe complete: No duplicates found.")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Final unique track count: {len(deduplicated_list)}")

        logger.debug("------ modifiers.dedupe END------")
        return deduplicated_list

    except Exception as e:
        logger.error(f"Failed to perform deduplication: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Traceback for dedupe failure:")
        # Return original list as safety net
        return current_tracks