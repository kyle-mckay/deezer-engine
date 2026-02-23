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
from utils.signals import shutdown_event
from pathlib import Path
from utils.paths import get_data_dir
from utils.config_loader import get_global_value
from utils.db_manager import sync_to_collections, update_unprocessed, is_collection_cached

class StrategyController:
    def __init__(self, client, config, logger, strategy_name):
        self.client = client
        self.config = config
        self.logger = logger
        self.strategy_name = strategy_name
        
        # Get base data directory
        data_dir = get_data_dir()
        self.tmp_file = str(data_dir / 'tmp' / f"{strategy_name}.json")
        
        # Ensure working directories exist
        os.makedirs(data_dir / 'tmp', exist_ok=True)
        os.makedirs(data_dir / 'cache', exist_ok=True)

        # Clear the tmp file at the start of a fresh strategy run.
        if os.path.exists(self.tmp_file):
            try:
                os.remove(self.tmp_file)
                self.logger.debug(f"Cleared existing tmp file for fresh run: {self.tmp_file}")
            except Exception as e:
                self.logger.debug(f"Non-critical: Could not clear tmp file {self.tmp_file}: {e}")
        
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Initialized StrategyController for '{strategy_name}'")
            self.logger.debug(f"Working directory: {os.getcwd()}")
            self.logger.debug(f"Temporary state path: {self.tmp_file}")

    def _write_tmp(self, tracks):
        """Writes the current pipeline state to the local filesystem."""
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Persisting {len(tracks)} tracks to temporary storage: {self.tmp_file}")
            
        with open(self.tmp_file, 'w') as f:
            json.dump(tracks, f)

    def _read_tmp(self):
        """Reads the current pipeline state. Returns empty list if file doesn't exist."""
        if not os.path.exists(self.tmp_file):
            self.logger.debug(f"No temporary state file found at {self.tmp_file}. Initializing with empty list.")
            return []
            
        with open(self.tmp_file, 'r') as f:
            data = json.load(f)
            
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Loaded {len(data)} tracks from {self.tmp_file}")
        return data
        
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
        """Dynamically loads a source worker and appends its results to the strategy's tmp file."""
        self.logger.debug(">>> START: strategies.base.handle_source")
        src_type = source_data.get('type')
        # Use 'name' if available (e.g. 'discovery'), otherwise fallback to type
        src_label = source_data.get('name', src_type) 
        src_retention = source_data.get('retention',get_global_value('retention',0))
        module_path = f"strategies.sources.{src_type}"
        
        self.logger.debug(f"Targeting source module: {module_path}")
        try:
            module = importlib.import_module(module_path)
            
            # Retrieve what we have in the current strategy pipeline so far
            current_tracks = self._read_tmp()
            
            # Run the worker logic
            self.logger.debug(f"Executing {src_type}.run()")

            # Get new tracklist if cache expired
            if src_retention == 0 or not is_collection_cached(source_name, self.config, self.logger):
                self.logger.debug(f"Cache expired or missing for {source_name}. Fetching from API.")
                #controller.handle_source(src)
                new_tracks = module.run(self.client, self.config, self.logger, source_data)
            else:
                self.logger.debug(f"Using cached data for {source_name}.")


            
            # Log tracks and their source
            if new_tracks:
                self.logger.debug(f"Syncing {len(new_tracks)} tracks from '{src_label}' to local collection database.")
                sync_to_collections(new_tracks,self.logger)
                self.logger.debug(f"Source '{src_label}': Found {len(new_tracks)} tracks.")
            
            self.logger.debug("<<< END: strategies.base.handle_source")

        except Exception as e:
            self.logger.error(f"Critical failure processing source '{src_label}': {e}")
            raise

    def handle_modifier(self, mod_data, tracks_override=None, source_name=None):
        """
        Dynamically loads a modifier worker to transform the current track list.
        If tracks_override is provided, it processes those tracks instead of reading from tmp.
        """
        self.logger.debug(">>> START: strategies.base.handle_modifier")
        mod_type = mod_data.get('type')
        module_path = f"strategies.modifiers.{mod_type}"
        
        # Determine if we are working on the global pipeline or an override (local)
        if tracks_override is not None:
            self.logger.debug(f"Modifier '{mod_type}' operating on local track override.")
            current_tracks = tracks_override
        else:
            self.logger.debug(f"Modifier '{mod_type}' operating on global pipeline state.")
            current_tracks = self._read_tmp()
            
        self.logger.debug(f"Applying '{mod_type}' to {len(current_tracks)} items.")
        
        try:
            self.logger.debug(f"Importing modifier module: {module_path}")
            module = importlib.import_module(module_path)
            # Modifiers are 'pure': they take tracks, modify them, and return results
            modified_tracks = module.run(self.client, self.config, self.logger, mod_data, current_tracks,source_name)
            
            # Only write to disk if we are in "Global" mode (no override)
            if tracks_override is None:
                self._write_tmp(modified_tracks)
                current_length=len(current_tracks)
                new_length=len(modified_tracks)
                if current_length != new_length:
                    self.logger.debug(f"Applied '{mod_type}': Pipeline changed from {current_length} to {new_length} tracks.")
                else:
                    self.logger.debug(f"Applied '{mod_type}': Processed {current_length} tracks.")
            
            self.logger.debug("<<< END: strategies.base.handle_modifier")
            return modified_tracks

        except Exception as e:
            self.logger.error(f"Failed to apply modifier '{mod_type}': {e}")
            raise

    def check_playlist_limit(self, dest_data, tracks):
        """Checks if the track list is approaching the environment-defined playlist cap and shrinks it if necessary."""
        self.logger.debug(">>> START: strategies.base.check_playlist_limit")
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
        self.logger.debug("<<< END: strategies.base.check_playlist_limit")
        return tracks

    def handle_destination(self, dest_data):
        """Dynamically loads the destination worker using the final tmp state."""
        self.logger.debug(">>> START: strategies.base.handle_destination")
        dest_type = dest_data.get('type')
        # Dynamically load module based on type (e.g., strategies.destinations.playlist)
        module_path = f"strategies.destinations.{dest_type}"
        
        # Read the final state of the pipeline
        current_tracks = self._read_tmp()
        
        self.logger.debug(f"Syncing {len(current_tracks)} tracks to {dest_type} (ID: {dest_data.get('id')}).")
        
        # Run the limit check
        current_tracks = self.check_playlist_limit(dest_data, current_tracks)

        try:
            self.logger.debug(f"Loading destination module: {module_path}")
            module = importlib.import_module(module_path)
            # The destination module will now look at dest_data['order'] for 'replace'/'smart'
            module.run(self.client, self.config, self.logger, dest_data, current_tracks)
        except Exception as e:
            self.logger.error(f"Failed to push to destination '{dest_type}': {e}")
            raise
        self.logger.debug("<<< END: strategies.base.handle_destination")