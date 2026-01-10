import yaml
from utils.logger import setup_logger
from utils.deezer_auth import get_authenticated_client

def load_configs():
    """Loads both the main configuration and the playlist strategies."""
    try:
        with open('config.yml', 'r') as f:
            config = yaml.safe_load(f)
        with open('strategies.yml', 'r') as f:
            strategies = yaml.safe_load(f)
        return config, strategies
    except Exception as e:
        print(f"Critical Error: Could not load YAML files. {e}")
        sys.exit(1)

def main():
    # 1. Load data
    config, strategies_config = load_configs()
    
    # 2. Setup Logger
    log_level = config.get('config', {}).get('log_level', 'INFO')
    logger = setup_logger("DeezerEngine", log_level)
    
    logger.info("--- Starting Deezer Smart Playlist Engine ---")

    # 3. Authenticate
    client = get_authenticated_client(config, logger)
    
    # 4. Strategy Execution Loop
    if not strategies_config or 'playlists' not in strategies_config:
        logger.warning("No strategies found in strategies.yml.")
        return

    for s_data in strategies_config['playlists']:
        strategy_name = s_data.get('name', 'Unknown Strategy')
        strategy_type = s_data.get('type')
        
        logger.info(f"Processing: {strategy_name} [{strategy_type}]")
        
        # To call strategy class
if __name__ == "__main__":
    main()