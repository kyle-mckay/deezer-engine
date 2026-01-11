import logging

def run(client, config, logger, mod_data, current_tracks):
    """
    Removes duplicate track IDs from the pipeline
    """
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
        
        for tid in current_tracks:
            if tid not in seen:
                deduplicated_list.append(tid)
                seen.add(tid)
            else:
                duplicate_count += 1
                if logger.isEnabledFor(logging.DEBUG) and duplicate_count <= 5:
                    logger.debug(f"Found duplicate track ID: {tid}")

        if duplicate_count > 0:
            logger.info(f"Dedupe complete: Removed {duplicate_count} duplicate songs.")
        else:
            logger.info("Dedupe complete: No duplicates found.")

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Final unique track count: {len(deduplicated_list)}")

        return deduplicated_list

    except Exception as e:
        logger.error(f"Failed to perform deduplication: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Traceback for dedupe failure:")
        # Return original list as safety net
        return current_tracks