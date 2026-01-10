import importlib
import os
import json

class StrategyController:
    def __init__(self, client, config, logger, strategy_name):
        self.client = client
        self.config = config
        self.logger = logger
        self.strategy_name = strategy_name
        self.tmp_file = f"./tmp/{strategy_name}.json"
        os.makedirs("./tmp", exist_ok=True)
        os.makedirs("./cache", exist_ok=True)

    # Save track IDs to a temporary file for the strategy run.
    def _write_tmp(self, track_ids):
        with open(self.tmp_file, 'w') as f:
            json.dump(track_ids, f)

    # Load track IDs from the temporary file if it exists, else return empty list.
    def _read_tmp(self):
        if not os.path.exists(self.tmp_file): return []
        with open(self.tmp_file, 'r') as f:
            return json.load(f)
        
    def chunk_list(self, data_list):
        """
        Yield successive n-sized chunks from data_list.
        """
        n = self.client.batch_size
        for i in range(0, len(data_list), n):
            yield data_list[i:i + n]

    def handle_source(self, source_data):
        # Example source_data: {'type': 'favorites', 'retention': 24}
        module = importlib.import_module(f"strategies.sources.{source_data['type']}")
        track_ids = module.run(self.client, self.config, self.logger, source_data)
        self._write_tmp(track_ids)

    def handle_modifier(self, mod_data):
        # Example mod_data: {'type': 'exclude', 'source': {...}}
        current_tracks = self._read_tmp()
        module = importlib.import_module(f"strategies.modifiers.{mod_data['type']}")
        modified_tracks = module.run(self.client, self.config, self.logger, mod_data, current_tracks)
        self._write_tmp(modified_tracks)

    def handle_destination(self, dest_data):
        # Example dest_data: {'type': 'replace', 'target': '...'}
        current_tracks = self._read_tmp()
        module = importlib.import_module(f"strategies.destinations.playlist")
        module.run(self.client, self.config, self.logger, dest_data, current_tracks)