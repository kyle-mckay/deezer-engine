import yaml
import sys
import logging
import os
from pathlib import Path
from utils.logger import setup_logger
from utils.paths import get_data_dir
from utils.config_loader import load_config_with_env_overrides, load_strategies_with_env_overrides, check_for_updates
from utils.deezer_auth import get_authenticated_client
from strategies.base import StrategyController
from __version__ import __version__, __banner__

def load_configs():
    """Load configuration and strategies with environment variable overrides."""
    try:
        config = load_config_with_env_overrides()
        strategies = load_strategies_with_env_overrides()
        
        # Validate that required config exists
        if 'config' not in config:
            raise ValueError("No 'config' section found in configuration")
        
        return config, strategies
    except Exception as e:
        print(f"Critical Error: Could not load configuration. {e}")
        sys.exit(1)

def print_startup():
    print(__banner__)
    print(f"Running Deezer-Engine {__version__}")

def main():
    # 1. Load data
    config, strategies_config = load_configs()

    # 2. Setup Logger & Validate Level
    user_log_level = config.get('config', {}).get('log_level', 'INFO').upper()
    should_write_logs = config.get('config', {}).get('write_logs', True)
    
    # Check if the level is officially recognized by the logging module
    # logging.getLevelName(str) returns the numeric level if valid, 
    # but only if it's a known string like 'DEBUG'.
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    actual_level = user_log_level
    warning_needed = False
    
    if user_log_level not in valid_levels:
        actual_level = 'INFO'
        warning_needed = True

    logger = setup_logger("DeezerEngine", actual_level,log_to_file=should_write_logs)
    
    # Issue the warning if config was bad
    if warning_needed:
        logger.warning(f"Unsupported log level '{user_log_level}' found in config.yml. Defaulting to 'INFO'.")
    logger.debug("--- Starting Deezer Engine ---")

    # Print banner if enabled and verbosity is info or higher
    if  config.get('config', {}).get('print_banner', True) and logger.isEnabledFor(logging.INFO):
        print_startup()

    containerized = os.getenv('CONTAINERIZED', 'false').lower()
    check_for_updates(__version__,containerized,logger)

    if containerized == 'true':
        logger.info("Deezer Engine is running in DOCKER mode.")
        logger.debug("Defaulting paths to '/app/data/'")
    else:
        logger.debug("Deezer Engine is running in LOCAL mode.")
        logger.debug(f"Using standard paths './'")
    
        
    
    # Log Config Metadata (Debug Only )
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
                    current_tracks = controller._read_tmp()
                    logger.debug(f"Pipeline size after source: {len(current_tracks)} tracks.")
                    # Only log the tracks if the list is manageable, or just head/tail
                    if len(current_tracks) > 100:
                        sample = [t.get('title', str(t))[:30] if isinstance(t, dict) else str(t.title)[:30] for t in current_tracks[:3]]
                        logger.debug(f"Sample tracks: {sample}...")
                    else:
                        titles = [t.get('title', str(t)) if isinstance(t, dict) else t.title for t in current_tracks[:5]]
                        logger.debug(f"Track titles: {titles}")
            
            # Modifier Phase
            modifiers = s_data.get('modifiers', [])
            for mod in modifiers:
                logger.debug(f"Applying modifier: {mod.get('type')}")
                controller.handle_modifier(mod)
                
                if logger.isEnabledFor(logging.DEBUG):
                    modified_tracks = controller._read_tmp()
                    logger.debug(f"Pipeline size after modifier: {len(modified_tracks)} tracks.")

            # Destination Phase
            destinations = s_data.get('destination', [])
            if destinations:
                for dest in destinations:
                    dest_type = dest.get('type')
                    dest_id = dest.get('id', 'Unknown')
                    logger.debug(f"Routing to destination: {dest_type} (ID: {dest_id})")
                    controller.handle_destination(dest)
            else:
                logger.warning(f"Strategy '{strategy_name}' has no destination defined.")

        except Exception as e:
            logger.error(f"Strategy '{strategy_name}' failed: {e}")
            logger.debug("Exception details:", exc_info=True)

if __name__ == "__main__":
    main()