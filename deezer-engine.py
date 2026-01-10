import yaml
import sys
from utils.logger import setup_logger
from utils.deezer_auth import get_authenticated_client
from strategies.base import StrategyController

def load_configs():
    """Load the main configuration and playlist strategies."""
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
    # Load configuration and strategies
    config, strategies_config = load_configs()
    # Configure logger
    log_level = config.get('config', {}).get('log_level', 'INFO')
    logger = setup_logger("DeezerEngine", log_level)
    
    logger.info("--- Starting Deezer Smart Playlist Engine ---")

    # Authenticate with Deezer
    client = get_authenticated_client(config, logger)
    # Execute configured strategies
    if not strategies_config or 'playlists' not in strategies_config:
        logger.warning("No strategies found in strategies.yml.")
        return

    for s_data in strategies_config['playlists']:
        strategy_name = s_data.get('name', 'unnamed_strategy')
        
        # Sanitize the strategy name for use in filenames
        safe_name = strategy_name.lower().replace(" ", "_")
        
        logger.info(f"--- Executing Strategy: {strategy_name} ---")
        
        # Initialize a controller instance for this strategy
        controller = StrategyController(client, config, logger, safe_name)
        
        try:
            # Source phase: collect track IDs from configured sources
            sources = s_data.get('source', [])
            if not sources:
                logger.error(f"Strategy '{strategy_name}' has no sources.")
                continue
            
            for src in sources:
                controller.handle_source(src)
            
            # Modifier phase: apply any transformations/filters
            modifiers = s_data.get('modifiers', [])
            for mod in modifiers:
                controller.handle_modifier(mod)
            
            # Destination phase: push results to the target
            destination = s_data.get('destination')
            if destination:
                controller.handle_destination(destination)
            else:
                logger.warning(f"Strategy '{strategy_name}' has no destination defined.")

        except Exception as e:
            logger.error(f"Strategy '{strategy_name}' failed: {e}")
            logger.debug("Exception details:", exc_info=True)

if __name__ == "__main__":
    main()