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
import importlib
import logging
from utils.collections import get_collection_name, is_collection_cached, fetch_collection, sync_to_collections

def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Subtracts tracks found in a specific source from the current pipeline.
    
    Order of operations:
    1. Loads the 'Exclusion Source' (the tracks we WANT to remove).
    2. Compares them against 'current_tracks' (the pipeline from ./tmp/).
    3. Returns the filtered list to the Controller to overwrite ./tmp/.
    """
    # 1. Resolve the exclude source dynamically
    source_data = mod_data.get('source')
    if not source_data:
        logger.error("Exclude modifier missing 'source' definition.")
        return current_tracks
    
    if isinstance(source_data, dict):
            source_data = [source_data]
    logger.debug(
        f"Exclude modifier start: pipeline={len(current_tracks)}, sources={len(source_data)}"
    )
    for src in source_data:
        source_type = src.get('type')
        source_id = src.get('id', None)
        source_name = src.get('name', None)

        if source_id:
            logger.debug(f"Targeting exclusion source: {source_type} (ID: {source_id})")
        elif source_name:
            logger.debug(f"Targeting exclusion source: {source_type} (Name: {source_name})")
        else:
            logger.debug(f"Targeting exclusion source: {source_type}")

        collection_name = get_collection_name(logger, source_type, source_name, source_id)

        logger.debug(f"Pipeline size before exclusion: {len(current_tracks)}")

        try:
            # Check if cache exists
 
            if collection_name != "unknown" and is_collection_cached(collection_name, src, logger):
                logger.debug(f"Tracks for source {collection_name} are cached. Pulling from cache")
                exclude_tracks = fetch_collection(collection_name, logger)
            else:
                logger.debug(f"Cached tracks are not available, pulling live track data.")
                # Reuse source worker
                module_path = f"strategies.sources.{source_type}"
                logger.debug(f"Importing source worker: {module_path}")
                source_worker = importlib.import_module(module_path)
                exclude_tracks = source_worker.run(client, config, logger, source_data)
                # Push to collections for future reference
                sync_to_collections(exclude_tracks,logger)
            
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
            removed_ids = []
            for track in current_tracks:
                track_id = str(track.get('id') if isinstance(track, dict) else track.id)
                if track_id not in exclude_set:
                    result.append(track)
                else:
                    removed_ids.append(track_id)
            
            removed_count = starting_count - len(result)
            logger.info(f"Action: Excluded {removed_count}/{starting_count} tracks based on {source_type}.")
            if removed_ids:
                logger.debug(
                    f"Excluded sample IDs ({min(len(removed_ids), 5)} of {len(removed_ids)}): "
                    f"{removed_ids[:5]}"
                )
            
            logger.debug(f"Final pipeline count: {len(result)}")
            logger.debug(
                f"Exclude modifier end: source={source_type}, removed={removed_count}, remaining={len(result)}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to apply exclusion: {e}")
            logger.debug("Traceback for exclusion failure:", exc_info=True)
            # On failure, return the original list to avoid breaking the pipeline
            return current_tracks