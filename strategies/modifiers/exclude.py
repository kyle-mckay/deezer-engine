import importlib
import logging

def run(client, config, logger, mod_data, current_tracks):
    """
    Subtracts tracks found in a specific source from the current pipeline.
    
    Order of operations:
    1. Loads the 'Exclusion Source' (the tracks we WANT to remove).
    2. Compares them against 'current_tracks' (the pipeline from ./tmp/).
    3. Returns the filtered list to the Controller to overwrite ./tmp/.
    """
    logger.info("Applying 'exclude' modifier...")

    # 1. Resolve the exclude source dynamically
    source_info = mod_data.get('source')
    if not source_info:
        logger.error("Exclude modifier missing 'source' definition.")
        return current_tracks

    source_type = source_info.get('type')
    
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Exclusion logic started. Target source type: {source_type}")
        logger.debug(f"Current pipeline size: {len(current_tracks)} tracks.")

    try:
        # We reuse the source workers to get the list of IDs to exclude.
        module_path = f"strategies.sources.{source_type}"
        logger.debug(f"Loading exclusion source worker: {module_path}")
        
        source_worker = importlib.import_module(module_path)
        exclude_tracks = source_worker.run(client, config, logger, source_info)
        
        # 2. Perform the subtraction
        # Convert to a set for O(1) membership checks
        exclude_set = set(exclude_tracks)
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Exclusion list loaded: {len(exclude_set)} unique tracks to filter out.")
            # Verify if there is any overlap at all before filtering
            intersection = set(current_tracks).intersection(exclude_set)
            logger.debug(f"Intersection found: {len(intersection)} tracks in pipeline match the exclusion list.")

        starting_count = len(current_tracks)
        
        # Preserve the original order while filtering
        result = [t for t in current_tracks if t not in exclude_set]
        
        removed_count = starting_count - len(result)
        logger.info(f"Exclusion complete: Removed {removed_count} matching tracks.")
        
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Final pipeline count after exclusion: {len(result)}")
            
        return result

    except Exception as e:
        logger.error(f"Failed to apply exclusion: {e}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.exception("Traceback for exclusion failure:")
        # On failure, return the original list to avoid breaking the pipeline
        return current_tracks