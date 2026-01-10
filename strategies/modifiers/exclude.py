import importlib

def run(client, config, logger, mod_data, current_tracks):
        """
        Remove tracks provided by a source from the current list.
        mod_data should include a `source` entry, for example:
            - source: { type: 'playlist', id: '12345' }
        """
    logger.info("Applying 'exclude' modifier...")

    # Resolve the exclude source dynamically
    source_info = mod_data.get('source')
    if not source_info:
        logger.error("Exclude modifier missing 'source' definition.")
        return current_tracks

    source_type = source_info.get('type')
    
    try:
        # Reuse a source worker to obtain IDs to exclude
        source_worker = importlib.import_module(f"strategies.sources.{source_type}")
        exclude_tracks = source_worker.run(client, config, logger, source_info)
        
        # Convert to a set for O(1) membership checks
        exclude_set = set(exclude_tracks)
        
        starting_count = len(current_tracks)
        # Preserve the original order while filtering
        result = [t for t in current_tracks if t not in exclude_set]
        
        logger.info(f"Exclusion complete: Removed {starting_count - len(result)} matching tracks.")
        return result

    except Exception as e:
        logger.error(f"Failed to apply exclusion: {e}")
        # On failure, return the original list to avoid breaking the pipeline
        return current_tracks