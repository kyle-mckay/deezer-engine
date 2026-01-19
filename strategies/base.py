import importlib
import os
import json
import logging
from pathlib import Path
from utils.paths import get_data_dir
from utils.config_loader import get_global_value

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
                self.logger.warning(f"Could not clear tmp file {self.tmp_file}: {e}")
        
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Initialized StrategyController for '{strategy_name}'")
            self.logger.debug(f"Working directory: {os.getcwd()}")
            self.logger.debug(f"Temporary state path: {self.tmp_file}")

    def _write_tmp(self, tracks):
        """Writes the current pipeline state to the local filesystem."""
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Writing {len(tracks)} tracks to {self.tmp_file}")
            
        with open(self.tmp_file, 'w') as f:
            json.dump(tracks, f)

    def _read_tmp(self):
        """Reads the current pipeline state. Returns empty list if file doesn't exist."""
        if not os.path.exists(self.tmp_file):
            self.logger.debug(f"State file {self.tmp_file} not found or cleared. Starting empty.")
            return []
            
        with open(self.tmp_file, 'r') as f:
            data = json.load(f)
            
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Read {len(data)} tracks from {self.tmp_file}")
        return data
        
    def chunk_list(self, data_list):
        """
        Yield successive n-sized chunks based on the global batch_size.
        """
        n = self.client.batch_size
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Chunking list of {len(data_list)} items into batches of {n}")
            
        for i in range(0, len(data_list), n):
            yield data_list[i:i + n]

    def handle_source(self, source_data):
        """Dynamically loads a source worker and appends its results to the strategy's tmp file."""
        src_type = source_data.get('type')
        # Use 'name' if available (e.g. 'discovery'), otherwise fallback to type
        src_label = source_data.get('name', src_type) 
        module_path = f"strategies.sources.{src_type}"
        
        self.logger.debug(f"Attempting to load source module: {module_path}")
        try:
            module = importlib.import_module(module_path)
            
            # Retrieve what we have in the current strategy pipeline so far
            current_tracks = self._read_tmp()
            
            # Run the worker logic
            new_tracks = module.run(self.client, self.config, self.logger, source_data)
            
            # Check for source specific modifiers
            local_modifiers = source_data.get('modifiers', [])
            if local_modifiers:
                self.logger.debug(f"Applying {len(local_modifiers)} local modifiers to source '{src_label}'")
                for mod_data in local_modifiers:
                    mod_type = mod_data.get('type')
                    mod_module_path = f"strategies.modifiers.{mod_type}"
                    try:
                        mod_module = importlib.import_module(mod_module_path)
                        new_tracks = mod_module.run(self.client, self.config, self.logger, mod_data, new_tracks)
                        self.logger.debug(f"Local modifier '{mod_type}' applied. Source tracks: {len(new_tracks)}")
                    except Exception as mod_e:
                        self.logger.error(f"Failed to apply local modifier '{mod_type}' to source '{src_label}': {mod_e}")

            # Combine tracks
            seen_ids = set()
            combined = []
            for track in current_tracks + new_tracks:
                track_id = str(track.get('id') if isinstance(track, dict) else track.id)
                if track_id not in seen_ids:
                    combined.append(track)
                    seen_ids.add(track_id)
            
            self._write_tmp(combined)
            
            self.logger.info(f"Found {len(new_tracks)} songs in source: {src_label}")
            
            # Detailed tracking for DEBUG
            self.logger.debug(
                f"Source '{src_label}' ({src_type}) resolved. "
                f"Pipeline grew: {len(current_tracks)} -> {len(combined)} tracks. "
                f"Net gain: +{len(combined) - len(current_tracks)} unique tracks."
            )

        except Exception as e:
            self.logger.error(f"Failed to process source '{src_label}': {e}")
            raise

    def handle_modifier(self, mod_data, tracks_override=None):
        """
        Dynamically loads a modifier worker to transform the current track list.
        If tracks_override is provided, it processes those tracks instead of reading from tmp.
        """
        mod_type = mod_data.get('type')
        module_path = f"strategies.modifiers.{mod_type}"
        
        # Determine if we are working on the global pipeline or an override (local)
        if tracks_override is not None:
            current_tracks = tracks_override
        else:
            current_tracks = self._read_tmp()
            
        self.logger.debug(f"Applying modifier '{mod_type}' to {len(current_tracks)} tracks.")
        
        try:
            module = importlib.import_module(module_path)
            # Modifiers are 'pure': they take tracks, modify them, and return results
            modified_tracks = module.run(self.client, self.config, self.logger, mod_data, current_tracks)
            
            # Only write to disk if we are in "Global" mode (no override)
            if tracks_override is None:
                self._write_tmp(modified_tracks)
                current_length=len(current_tracks)
                new_length=len(modified_tracks)
                if current_length != new_length:
                    self.logger.info(f"Modifier '{mod_type}' applied. Pipeline changed from {len(current_tracks)} to {len(modified_tracks)} tracks.")
                else:
                    self.logger.info(f"Modifier '{mod_type}' applied to {current_length} tracks")
            
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
                    self.logger.warning(f"Destination type '{dest_type}' does not have a defined content limit.")
                    return tracks
            
            current_count = len(tracks)
            warning_threshold = cap * 0.9
            
            # Shrink the tracks if they exceed the cap
            if current_count > cap:
                self.logger.warning(
                    f"Strategy '{self.strategy_name}' destination ({dest_type}) is at {current_count} tracks, "
                    f"exceeding the defined cap ({cap})."
                )
                self.logger.warning(f"Your tracks pipeline will shrink to '{cap}' tracks.")
                
                # This is the modification: slice the list to the cap
                tracks = tracks[:cap]

            # Log a warning if approaching the limit
            elif current_count >= warning_threshold:
                self.logger.warning(
                    f"Strategy '{self.strategy_name}' destination ({dest_type}) is at {current_count} tracks, "
                    f"exceeding 90% of the defined cap ({cap})."
                )
                
        except Exception as e:
            self.logger.error(f"Failed to check for a content limit on destination type '{dest_type}': {e}")
        
        # Always return the (potentially modified) tracks list
        return tracks

    def handle_destination(self, dest_data):
        """Dynamically loads the destination worker using the final tmp state."""
        self.logger.debug("------ strategies.base.handle_destination START------")
        dest_type = dest_data.get('type')
        # Dynamically load module based on type (e.g., strategies.destinations.playlist)
        module_path = f"strategies.destinations.{dest_type}"
        
        # Read the final state of the pipeline
        current_tracks = self._read_tmp()
        
        self.logger.info(f"Preparing destination '{dest_type}' for ID '{dest_data.get('id')}' with {len(current_tracks)} tracks.")
        
        # Run the limit check
        current_tracks = self.check_playlist_limit(dest_data, current_tracks)

        try:
            module = importlib.import_module(module_path)
            # The destination module will now look at dest_data['order'] for 'replace'/'smart'
            module.run(self.client, self.config, self.logger, dest_data, current_tracks)
        except Exception as e:
            self.logger.error(f"Failed to push to destination '{dest_type}': {e}")
            raise
        self.logger.debug("------ strategies.base.handle_destination END------")