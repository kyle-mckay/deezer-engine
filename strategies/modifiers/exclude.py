import importlib
import logging

def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Subtracts tracks found in a specific source from the current pipeline.
    
    Order of operations:
    1. Loads the 'Exclusion Source' (the tracks we WANT to remove).
    2. Compares them against 'current_tracks' (the pipeline from ./tmp/).
    3. Returns the filtered list to the Controller to overwrite ./tmp/.
    """
    logger.debug(">>> START: strategies.modifiers.exclude.run")

    # 1. Resolve the exclude source dynamically
    source_data = mod_data.get('source')
    if not source_data:
        logger.error("Exclude modifier missing 'source' definition.")
        return current_tracks
    
    if isinstance(source_data, dict):
            source_data = [source_data]
    for src in source_data:
        source_type = src.get('type')
        source_id = src.get('id', 'N/A')
        
        logger.debug(f"Targeting exclusion source: {source_type} (ID: {source_id})")
    
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Pipeline size before exclusion: {len(current_tracks)}")

        try:
            # We reuse the source workers to get the list of IDs to exclude.
            module_path = f"strategies.sources.{source_type}"
            logger.debug(f"Importing source worker: {module_path}")
            
            source_worker = importlib.import_module(module_path)
            exclude_tracks = source_worker.run(client, config, logger, source_data)
            
            # 2. Perform the subtraction
            # Build set of IDs to exclude
            exclude_set = set()
            for track in exclude_tracks:
                track_id = str(track.get('id') if isinstance(track, dict) else track.id)
                exclude_set.add(track_id)
            
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Loaded {len(exclude_set)} IDs to exclude.")
                # Verify if there is any overlap at all before filtering
                current_ids = {str(t.get('id') if isinstance(t, dict) else t.id) for t in current_tracks}
                intersection = current_ids.intersection(exclude_set)
                logger.debug(f"Match found: {len(intersection)} tracks from current pipeline exist in exclusion source.")

            starting_count = len(current_tracks)
            
            # Preserve the original order while filtering
            result = []
            for track in current_tracks:
                track_id = str(track.get('id') if isinstance(track, dict) else track.id)
                if track_id not in exclude_set:
                    result.append(track)
                else:
                    logger.debug(f"Excluding Track ID: {track_id}")
            
            removed_count = starting_count - len(result)
            logger.info(f"Exclusion applied: Removed {removed_count} tracks based on {source_type}.")
            
            logger.debug(f"Final pipeline count: {len(result)}")
            logger.debug("<<< END: strategies.modifiers.exclude.run")
                
            return result

        except Exception as e:
            logger.error(f"Failed to apply exclusion: {e}")
            logger.debug("Traceback for exclusion failure:", exc_info=True)
            # On failure, return the original list to avoid breaking the pipeline
            return current_tracks