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
import os
import json
import logging
from pathlib import Path
from utils.infrastructure.paths import get_data_dir
from utils.config import get_global_value
from utils.collections import sync_to_collections, is_collection_cached, fetch_collection
from utils.metadata.tracks import insert_shallow_track_stubs
from utils.metadata.orchestration import update_unprocessed
from utils.api.fetching import fetch_shallow_tracks 
from utils.metadata.tracks import track_header_available

class StrategyController:

    def _validate_io(self, stage, expected, actual, mode, label):
        """
        Universal IO validation wrapper for input/output checks.
        """
        LOG_TAG = "[I/O Validation]"
        if expected is not None:
            passed = (expected == actual)
            match stage:
                case 'i':
                    stage_desc = "input"
                case 'o':
                    stage_desc = "output"
                case _:
                    logger.warning(f"{LOG_TAG} Unknown stage '{stage}' for {label} validation. Defaulting to generic description.")
                    stage_desc = stage
            if passed:
                self.logger.info(f"{LOG_TAG} PASSED {label}: {stage_desc} count matches expected value of {expected}.")
            else:
                self.logger.debug(f"{LOG_TAG} FAILED {label}: {stage_desc} count does not match expected value. Expected {expected}, got {actual}.")

                msg = f"{LOG_TAG} FAILED for {label}: expected {stage_desc}={expected}, got {actual}"
                match mode:
                    case 'fail':
                        self.logger.error(msg)
                        raise ValueError(msg)
                    case 'warn' | None:
                        self.logger.warning(msg)
                    case _:
                        self.logger.warning(f"{LOG_TAG} Unknown validation mode '{mode}' for {label} {stage_desc} check. Defaulting to 'info'.")
                        self.logger.info(msg)
            
    def refresh_pipeline_metadata(self):
        """
        Refresh the in-memory pipeline with the latest metadata from the database for all track IDs in the pipeline.
        """
        from utils.db.fetch import fetch_entities_by
        if not self.pipeline:
            return
        id_list = [t['id'] for t in self.pipeline if 'id' in t]
        if not id_list:
            return
        # Fetch latest track data from DB
        latest_tracks = fetch_entities_by('tracks', 'id', 'IN', id_list, return_ids_only=False, logger=self.logger)
        self.logger.debug(f"Fetched {len(latest_tracks)} tracks from DB. Sample: {latest_tracks[0] if latest_tracks else None}")
        # Map by ID
        latest_by_id = {t['id']: t for t in latest_tracks}
        # Update pipeline memory
        updated = 0
        for i, t in enumerate(self.pipeline):
            tid = t.get('id')
            if tid in latest_by_id:
                self.pipeline[i] = latest_by_id[tid]
                updated += 1
        self.logger.debug(f"Refreshed pipeline metadata for {updated} tracks from DB.")

    def __init__(self, client, config, logger, strategy_name):
        self.client = client
        self.config = config
        self.logger = logger
        self.strategy_name = strategy_name
        self.pipeline = []  # In-memory pipeline for current strategy
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Initialized StrategyController for '{strategy_name}' (in-memory pipeline)")
        
    def chunk_list(self, data_list):
        """
        Yield successive n-sized chunks based on the global chunk_size.
        """
        n = self.client.chunk_size
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Chunking {len(data_list)} items into chunks of {n} for processing.")
            
        for i in range(0, len(data_list), n):
            self.logger.debug(f"Processing batch { (i // n) + 1} of {(len(data_list) + n - 1) // n}")
            yield data_list[i:i + n]

    def handle_source(self, source_data, source_name = None):
        """Dynamically loads a source worker and returns its tracklist."""
        src_type = source_data.get('type')
        # Use 'name' if available (e.g. 'discovery'), otherwise fallback to type
        src_label = source_data.get('name', src_type) 
        module_path = f"strategies.sources.{src_type}"
        # Check if this source requires metadata and enrich if needed
        self._ensure_metadata_enriched_for_component(module_path, source_data)
        self.logger.debug(f"Targeting source module: {module_path}")
        try:
            module = importlib.import_module(module_path)
            # Run the worker logic
            self.logger.debug(f"Executing {src_type}.run()")
            # Get new tracklist if cache expired
            if not is_collection_cached(source_name, source_data, self.logger):
                self.logger.debug(f"Cache expired or missing for {source_name}. Fetching from API.")
                new_tracks = module.run(self.client, self.config, self.logger, source_data)
                self.logger.debug(f"Fetched {len(new_tracks)} tracks from source '{src_label}'. Sample: {new_tracks[0] if new_tracks else None}")
                self.logger.debug(f"Syncing to local collection database.")
                sync_to_collections(new_tracks, self.logger, source_name)
            else:
                self.logger.debug(f"Using cached data for {source_name}.")
                new_tracks = fetch_collection(source_name, self.logger)
                self.logger.debug(f"Source '{src_label}': Found {len(new_tracks)} tracks.")
            return new_tracks
        except Exception as e:
            self.logger.error(f"Critical failure processing source '{src_label}': {e}")
            raise

    def handle_modifier(self, mod_data, tracks_override=None, source_name=None):
        """
        Dynamically loads a modifier worker to transform the current track list.
        If tracks_override is provided, it processes those tracks instead of reading from tmp.
        """
        mod_type = mod_data.get('type')
        module_path = f"strategies.modifiers.{mod_type}"
        
        # Check if this modifier requires metadata and enrich if needed
        self._ensure_metadata_enriched_for_component(module_path, mod_data)
        
        # Determine if we are working on the global pipeline or an override (local)
        if tracks_override is not None:
            self.logger.debug(f"Modifier '{mod_type}' operating on local track override.")
            current_tracks = tracks_override
        else:
            self.logger.debug(f"Modifier '{mod_type}' operating on global pipeline state.")
            current_tracks = self.pipeline
        self.logger.debug(f"Applying '{mod_type}' to {len(current_tracks)} items.")
        
        #IO Validation (input)
        expected_i = mod_data.get('i', None)
        validation_mode = mod_data.get('validation_mode',get_global_value('validation_mode', None))
        if expected_i is not None:
            self.logger.debug(f"Modifier '{mod_type}' expects input count: {expected_i}")
            self._validate_io('i', expected_i, len(current_tracks), validation_mode, f"Modifier '{mod_type}'")
        # ---
        try:
            self.logger.debug(f"Importing modifier module: {module_path}")
            module = importlib.import_module(module_path)
            # Modifiers are 'pure': they take tracks, modify them, and return results
            modified_tracks = module.run(self.client, self.config, self.logger, mod_data, current_tracks, source_name)
            # Only update pipeline if we are in "Global" mode (no override)
            if tracks_override is None:
                current_length = len(self.pipeline)
                new_length = len(modified_tracks)
                self.pipeline = modified_tracks
                if current_length != new_length:
                    self.logger.debug(f"Applied '{mod_type}': Pipeline changed from {current_length} to {new_length} tracks.")
                else:
                    self.logger.debug(f"Applied '{mod_type}': Processed {current_length} tracks.")
            
            # IO Validation (output)
            expected_o = mod_data.get('o', None)
            if expected_o is not None:
                self.logger.debug(f"Modifier '{mod_type}' expects output count: {expected_o}")
                self._validate_io('o', expected_o, len(modified_tracks), validation_mode, f"Modifier '{mod_type}'")
            # ---
            return modified_tracks
        except Exception as e:
            self.logger.error(f"Failed to apply modifier '{mod_type}': {e}")
            raise

    def check_playlist_limit(self, dest_data, tracks):
        """Checks if the track list is approaching the environment-defined playlist cap and shrinks it if necessary."""
        dest_type = dest_data.get('type', '').lower()

        try:
            # Determine the cap based on destination type
            match dest_type:
                case "playlist":
                    cap = get_global_value('playlist_cap', default=5000)
                case "favorites":
                    cap = get_global_value('favorites_cap', default=10000)
                case _:
                    self.logger.debug(f"Destination type '{dest_type}' has no enforced content limit.")
                    return tracks
            
            current_count = len(tracks)
            warning_threshold = cap * 0.9
            self.logger.debug(f"Checking limit for {dest_type}: {current_count}/{cap}")
            
            # Shrink the tracks if they exceed the cap
            if current_count > cap:
                self.logger.warning(
                    f"Content limit exceeded: {current_count} tracks exceeds {dest_type} cap of {cap}."
                )
                self.logger.info(f"Truncating track list to {cap} for destination compatibility.")
                
                # This is the modification: slice the list to the cap
                tracks = tracks[:cap]

            # Log a warning if approaching the limit
            elif current_count >= warning_threshold:
                self.logger.warning(
                    f"Approaching content limit: {current_count}/{cap} for {dest_type}."
                )
                
        except Exception as e:
            self.logger.error(f"Error validating content limits for '{dest_type}': {e}")
        
        # Always return the (potentially modified) tracks list
        return tracks

    def handle_destination(self, dest_data):
        """Dynamically loads the destination worker using the final in-memory pipeline."""
        dest_type = dest_data.get('type')
        module_path = f"strategies.destinations.{dest_type}"
        # Check if this destination requires metadata and enrich if needed
        self._ensure_metadata_enriched_for_component(module_path, dest_data)
        # Use the in-memory pipeline
        current_tracks = self.pipeline
        self.logger.debug(f"Syncing {len(current_tracks)} tracks to {dest_type} (ID: {dest_data.get('id')}).")
        # Run the limit check
        current_tracks = self.check_playlist_limit(dest_data, current_tracks)
        # IO Validation (input)
        expected_i = dest_data.get('i')
        if expected_i is not None:
            self.logger.debug(f"Destination '{dest_type}' expects input count: {expected_i}")
            validation_mode = dest_data.get('validation_mode',get_global_value('validation_mode', None))
            self._validate_io('i', expected_i, len(current_tracks), validation_mode, f"Destination '{dest_type}'")
        try:
            self.logger.debug(f"Loading destination module: {module_path}")
            module = importlib.import_module(module_path)
            module.run(self.client, self.config, self.logger, dest_data, current_tracks)
        except Exception as e:
            self.logger.error(f"Failed to push to destination '{dest_type}': {e}")
            raise

    def check_requires_metadata(self, module_path, config_data):
        """
        Check if a dynamically loaded module has a requires_metadata function.
        Returns the result if it exists and is callable, otherwise defaults to True.
        """
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, 'requires_metadata') and callable(module.requires_metadata):
                try:
                    result = module.requires_metadata(config_data)
                    if isinstance(result, bool):
                        if self.logger.isEnabledFor(logging.DEBUG):
                            self.logger.debug(f"Module '{module_path}' requires_metadata() returned {result}")
                        if not result:
                            return False

                        # For modifiers that declare metadata requirements, only force enrichment
                        # when they reference fields unavailable in shallow track payloads.
                        if module_path.startswith("strategies.modifiers."):
                            modifier_fields = []
                            if isinstance(config_data, dict):
                                field_value = config_data.get("field")
                                if isinstance(field_value, str) and field_value.strip():
                                    modifier_fields.append(field_value.strip())

                                fields_value = config_data.get("fields")
                                if isinstance(fields_value, (list, tuple, set)):
                                    for field_name in fields_value:
                                        if isinstance(field_name, str) and field_name.strip():
                                            modifier_fields.append(field_name.strip())

                            if modifier_fields:
                                unavailable_fields = [
                                    field_name for field_name in modifier_fields
                                    if not track_header_available(field_name)
                                ]
                                if unavailable_fields:
                                    if self.logger.isEnabledFor(logging.DEBUG):
                                        self.logger.debug(
                                            f"Modifier '{module_path}' requires full metadata; fields not available in shallow payload: {unavailable_fields}"
                                        )
                                    return True

                                if self.logger.isEnabledFor(logging.DEBUG):
                                    self.logger.debug(
                                        f"Modifier '{module_path}' field requirements are available in shallow payload: {modifier_fields}. Skipping metadata enrichment."
                                    )
                                return False

                        return True
                    else:
                        self.logger.debug(f"Module '{module_path}' requires_metadata() returned non-bool {type(result)}, defaulting to True")
                        return True
                except Exception as hook_error:
                    self.logger.warning(f"Module '{module_path}' requires_metadata() raised exception: {hook_error}. Defaulting to True for safety.")
                    return True
            else:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"Module '{module_path}' has no requires_metadata hook, defaulting to True")
                return True
        except Exception as e:
            self.logger.warning(f"Failed to import module '{module_path}' for metadata check: {e}. Defaulting to True.")
            return True

    def _ensure_metadata_enriched_for_component(self, module_path, config_data):
        """
        Check if a component requires metadata and trigger enrichment when needed.
        """
        requires_it = self.check_requires_metadata(module_path, config_data)
        pull_metadata = get_global_value('pull_metadata', True)

        if requires_it and pull_metadata:
            self.logger.debug(f"Component '{module_path}' requires metadata. Fetching before processing...")
            try:
                update_unprocessed(self.client, self.logger)
                self.refresh_pipeline_metadata()
            except Exception as e:
                self.logger.error(f"Failed to enrich metadata before processing '{module_path}': {e}")
                raise
        elif requires_it:
            self.logger.debug(
                f"Component '{module_path}' requested metadata enrichment, but pull_metadata is disabled. "
                "Continuing with shallow/cached data."
            )