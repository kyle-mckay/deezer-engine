import yaml
import sys
import logging
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
    # 1. Load data
    config, strategies_config = load_configs()
    
    # 2. Setup Logger & Validate Level
    user_log_level = config.get('config', {}).get('log_level', 'INFO').upper()
    
    # Check if the level is officially recognized by the logging module
    # logging.getLevelName(str) returns the numeric level if valid, 
    # but only if it's a known string like 'DEBUG'.
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    actual_level = user_log_level
    warning_needed = False
    
    if user_log_level not in valid_levels:
        actual_level = 'INFO'
        warning_needed = True

    logger = setup_logger("DeezerEngine", actual_level)

    # Issue the warning if config was bad
    if warning_needed:
        logger.warning(f"Unsupported log level '{user_log_level}' found in config.yml. Defaulting to 'INFO'.")

    logger.info("--- Starting Deezer Smart Playlist Engine ---")

    # Log Config Metadata (Debug Only)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Configuration metadata: UserID={config.get('config', {}).get('user_id')}, "
                     f"BatchSize={config.get('config', {}).get('batch_size', 50)}")

    
    # 3. Authenticate
    client = get_authenticated_client(config, logger)
    
    # 4. Strategy Execution Loop
    if not strategies_config or 'playlists' not in strategies_config:
        logger.warning("No strategies found in strategies.yml.")
        return

    for s_data in strategies_config['playlists']:
        strategy_name = s_data.get('name', 'unnamed_strategy')
        
        # Sanitize the name for the temp filename
        safe_name = strategy_name.lower().replace(" ", "_")
        
        logger.info(f"--- Executing Strategy: {strategy_name} ---")
        
        # Log Strategy Definition (Debug Only)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Strategy definition for '{strategy_name}': {s_data}")
        
        # Initialize the Controller for this specific strategy
        controller = StrategyController(client, config, logger, safe_name)
        
        try:
            # Source Phase
            sources = s_data.get('source', [])
            for src in sources:
                logger.debug(f"Handling source type: {src.get('type')}")
                controller.handle_source(src)
                
                # Check for large dataset logging performance
                if logger.isEnabledFor(logging.DEBUG):
                    current_ids = controller._read_tmp()
                    logger.debug(f"Pipeline size after source: {len(current_ids)} tracks.")
                    # Only log the actual IDs if the list is manageable, or just head/tail
                    if len(current_ids) > 100:
                        logger.debug(f"Sample IDs: {current_ids[:5]} ... {current_ids[-5:]}")
                    else:
                        logger.debug(f"Full ID list: {current_ids}")
            
            # Modifier Phase
            modifiers = s_data.get('modifiers', [])
            for mod in modifiers:
                logger.debug(f"Applying modifier: {mod.get('type')}")
                controller.handle_modifier(mod)
                
                if logger.isEnabledFor(logging.DEBUG):
                    modified_ids = controller._read_tmp()
                    logger.debug(f"Pipeline size after modifier: {len(modified_ids)} tracks.")

            # Destination Phase
            destination = s_data.get('destination')
            if destination:
                logger.debug(f"Routing to destination: {destination.get('type')} (Target: {destination.get('target')})")
                controller.handle_destination(destination)
            else:
                logger.warning(f"Strategy '{strategy_name}' has no destination defined.")

        except Exception as e:
            logger.error(f"Strategy '{strategy_name}' failed: {e}")
            logger.debug("Exception details:", exc_info=True)

if __name__ == "__main__":
    main()