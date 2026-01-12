import importlib
import os
import json
import logging
from pathlib import Path
from utils.paths import get_data_dir

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

    def _write_tmp(self, track_ids):
        """Writes the current pipeline state to the local filesystem."""
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"Writing {len(track_ids)} IDs to {self.tmp_file}")
            
        with open(self.tmp_file, 'w') as f:
            json.dump(track_ids, f)

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
            
            # Combine IDs 
            combined = list(dict.fromkeys(current_tracks + new_tracks))
            self._write_tmp(combined)
            
            self.logger.info(f"Found {len(new_tracks)} songs in source: {src_label}")
            
            # Detailed tracking for DEBUG
            self.logger.debug(
                f"Source '{src_label}' ({src_type}) resolved. "
                f"Pipeline grew: {len(current_tracks)} -> {len(combined)} tracks. "
                f"Net gain: +{len(combined) - len(current_tracks)} unique IDs."
            )

        except Exception as e:
            self.logger.error(f"Failed to process source '{src_label}': {e}")
            raise

    def handle_modifier(self, mod_data):
        """Dynamically loads a modifier worker to transform the current track list."""
        mod_type = mod_data.get('type')
        module_path = f"strategies.modifiers.{mod_type}"
        
        current_tracks = self._read_tmp()
        self.logger.debug(f"Applying modifier '{mod_type}' to {len(current_tracks)} tracks.")
        
        try:
            module = importlib.import_module(module_path)
            # Modifiers are 'pure': they take tracks from tmp, modify them, and return results
            modified_tracks = module.run(self.client, self.config, self.logger, mod_data, current_tracks)
            
            # Overwrite the strategy's tmp file with the modified results
            self._write_tmp(modified_tracks)
            self.logger.info(f"Modifier '{mod_type}' applied. Pipeline now contains {len(modified_tracks)} tracks.")
        except Exception as e:
            self.logger.error(f"Failed to apply modifier '{mod_type}': {e}")
            raise

    def handle_destination(self, dest_data):
        """Dynamically loads the destination worker using the final tmp state."""
        module_path = "strategies.destinations.playlist"
        
        # Read the final state of the pipeline after all sources and modifiers
        current_tracks = self._read_tmp()
        self.logger.info(f"Preparing destination for type '{dest_data.get('type')}' with {len(current_tracks)} tracks.")
        
        try:
            module = importlib.import_module(module_path)
            module.run(self.client, self.config, self.logger, dest_data, current_tracks)
        except Exception as e:
            self.logger.error(f"Failed to push to destination: {e}")
            raise