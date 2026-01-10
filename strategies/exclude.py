# strategies/modifiers/exclude.py
import importlib

def run(client, config, logger, mod_data, current_tracks):
    # Log the application of the exclusion modifier.
    logger.info(f"Applying exclusion modifier...")
    
    # Import the appropriate source worker based on the type specified in mod_data.
    source_type = mod_data['source']['type']
    source_worker = importlib.import_module(f"strategies.sources.{source_type}")
    
    # Create a set of tracks to exclude based on the source worker's output.
    exclude_tracks = source_worker.run(client, config, logger, mod_data['source'])
    exclude_set = set(exclude_tracks)
    
    # Filter current tracks to remove excluded ones.
    result = [t for t in current_tracks if t not in exclude_set]
    
    # Log the number of tracks removed from the current list.
    logger.info(f"Removed {len(current_tracks) - len(result)} tracks.")
    return result