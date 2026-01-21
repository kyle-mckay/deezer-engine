import yaml
import sys
import logging
import os
from pathlib import Path
from utils.logger import setup_logger
from utils.paths import get_data_dir
from utils.config_loader import load_config_with_env_overrides, load_strategies_with_env_overrides, check_for_updates, get_global_value
from utils.deezer_auth import get_authenticated_client, get_tracks
from strategies.base import StrategyController
from utils.database import initialize_all
from utils.db_manager import get_unprocessed_track_ids, update_track_metadata,fetch_collection, is_collection_cached, get_expired_track_ids, update_tracks_partial_batch
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

    containerized = get_global_value('containerized', default=False)
    print_banner = get_global_value('print_banner', default=True)
    
    # Print banner within script if not containerized, enabled and verbosity is info or higher
    if  containerized == False and print_banner == True and logger.isEnabledFor(logging.INFO):
        print_startup()

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

    # Initialize database
    initialize_all(logger)
    
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
            source_list = []
            # Source Phase
            sources = s_data.get('source', [])
            for src in sources:
                logger.debug(f"Handling source type: {src.get('type')}")
                source_name=src.get('type')
                if source_name == 'favorites':
                    source_list.append(f"{source_name}")
                elif source_name == "smarttracklist":
                    source_list.append(f"{source_name}__{src.get('name')}")
                else:
                    source_list.append(f"{source_name}__{src.get('id')}")

                # Get new tracklist if cache expired
                if is_collection_cached(source_name,config,logger) == False:
                    controller.handle_source(src)
                
                # Identify new tracks to fetch metadata for.
                unprocessed = get_unprocessed_track_ids(logger)
                if len(unprocessed) > 0:
                    logger.info(f"Fetching metadata for new {len(unprocessed)} new tracks... This may take a while")
                    unprocessed = get_tracks(client,logger,"database","tracks","null",unprocessed)
                    logger.debug(f"Metadata fetched, updating database.")
                    update_track_metadata(unprocessed,logger)
                refresh_stats = get_expired_track_ids(logger)
                if len(refresh_stats) > 0:
                    logger.info(f"Fetching new stats (rank, unseen) for existing tracks... This should be quicker")
                    refresh_stats = get_tracks(client, logger, "database", "stats", "null", refresh_stats)
                    logger.debug(f"New stats fetched, updating database.")
                    update_tracks_partial_batch(refresh_stats)
            

            # Modifier Phase
            tracks = []
            for source in source_list:
                tracks.extend(fetch_collection(source,logger))
            controller._write_tmp(tracks)

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