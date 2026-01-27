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

import yaml
import re
import sys
import logging
import signal
import os
from pathlib import Path
from utils.logger import setup_logger
from utils.paths import get_data_dir
from utils.config_loader import load_config_with_env_overrides, load_strategies_with_env_overrides, check_for_updates, get_global_value
from utils.deezer_auth import get_authenticated_client, get_tracks
from strategies.base import StrategyController
from utils.database import initialize_all
from utils.cache_manager import get_collection_name
from utils.signals import shutdown_event
from utils.db_manager import get_unprocessed_track_ids, update_track_metadata,fetch_collection, is_collection_cached, get_expired_track_ids, update_tracks_partial_batch, update_unprocessed, refresh_stats
from __version__ import __version__, __banner__

def signal_handler(sig, frame):
    """Callback for SIGINT/SIGTERM to trigger a graceful exit."""
    print(f"\n[!] Signal {sig} received. Will exit after current strategy finishes...")
    shutdown_event.set()

def load_configs(type,logger = None):
    """Load configuration and strategies with environment variable overrides."""
    try:

        match type:
            case "config":
                loaded = load_config_with_env_overrides()
                # Validate that required config exists
                if 'config' not in loaded:
                    raise ValueError("No 'config' section found in configuration")
            case "strategy":
                loaded = load_strategies_with_env_overrides(logger)
        
        return loaded
        
    except Exception as e:
        print(f"Critical Error: Could not load configuration. {e}")
        sys.exit(1)

def print_startup():
    print(__banner__)
    print(f"Running Deezer-Engine {__version__}")
    print("This is free software under the GNU GPL v3.0.")
    print("For more details, see https://codeberg.org/kylemmkay/deezer-engine")

def process_sources(s_data, controller, config, client, logger, strategy_name):
    """
    Handles the Source Phase of the strategy.
    Returns a list of tuples containing (source_name, source_specific_modifiers).
    """
    source_metadata = []
    sources = s_data.get('source', [])
    logger.debug(f"Strategy '{strategy_name}' has {len(sources)} sources defined.")
    
    for src in sources:
        logger.debug(f"Handling source type: {src.get('type')}")
        source_type = src.get('type')
        source_retention = src.get('retention',get_global_value('retention',0))
        source_modifiers = src.get('modifiers', []) # Capture child modifiers

        source_name = get_collection_name(logger,source_type,src.get('name',None),src.get('id',None))
        
        # Track the name and its specific modifiers
        source_metadata.append((source_name, source_modifiers))

        # Get new tracklist if cache expired
        if source_retention == 0 or not is_collection_cached(source_name, config, logger):
            logger.debug(f"Cache expired or missing for {source_name}. Fetching from API.")
            controller.handle_source(src,source_name)
        else:
            logger.debug(f"Using cached data for {source_name}.")

        if shutdown_event.is_set():
                logger.debug("Shutdown passing through process_sources acknowledged. Skipping remaining strategies.")
                break
        # Identify new tracks to fetch metadata for.
        update_unprocessed(client, logger)
    
    return source_metadata

def process_modifiers(s_data, controller, source_metadata, logger, strategy_name):
    """Handles the Modifier Phase, including source-specific and global modifiers."""
    
    # 1. Collect and apply source-specific modifiers individually
    all_processed_tracks = []
    
    for source_name, child_modifiers in source_metadata:
        fetched = fetch_collection(source_name, logger)
        logger.debug(f"Fetched {len(fetched)} tracks from {source_name}")
        
        if child_modifiers:
            logger.debug(f"Applying {len(child_modifiers)} child modifiers to source '{source_name}'")
            for mod in child_modifiers:
                logger.debug(f"Applying child modifier: {mod.get('type')}")
                fetched = controller.handle_modifier(mod,fetched,source_name)
            
        all_processed_tracks.extend(fetched)
    
    # 2. Apply Global Strategy Modifiers
    logger.debug(f"Total tracks collected for global pipeline: {len(all_processed_tracks)}")
    controller._write_tmp(all_processed_tracks)

    global_modifiers = s_data.get('modifiers', [])
    if global_modifiers:
        logger.debug(f"Strategy '{strategy_name}' has {len(global_modifiers)} global modifiers defined.")
        for mod in global_modifiers:
            logger.debug(f"Applying global modifier: {mod.get('type')}")
            controller.handle_modifier(mod,None,source_name)
            
            if logger.isEnabledFor(logging.DEBUG):
                modified_tracks = controller._read_tmp()
                logger.debug(f"Pipeline size after '{mod.get('type')}': {len(modified_tracks)} tracks.")

def process_destinations(s_data, controller, logger, strategy_name):
    """Handles the Destination Phase of the strategy."""
    destinations = s_data.get('destination', [])
    if destinations:
        for dest in destinations:
            dest_type = dest.get('type')
            dest_id = dest.get('id', 'Unknown')
            logger.debug(f"Routing to destination: {dest_type} (ID: {dest_id})")
            controller.handle_destination(dest)
        logger.debug(f"Successfully completed: {strategy_name}")
    else:
        logger.warning(f"Strategy '{strategy_name}' has no destination defined.")

def main():
    # Register signal handlers for Ctrl+C (SIGINT) and Docker stop (SIGTERM)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 1. Load data
    config = load_configs("config")

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

    logger = setup_logger("DeezerEngine", actual_level, log_to_file=should_write_logs)
    
    # Issue the warning if config was bad
    if warning_needed:
        logger.warning(f"Unsupported log level '{user_log_level}' found in config.yml. Defaulting to 'INFO'.")

    strategies_config = load_configs("strategy", logger)

    containerized = get_global_value('containerized', default=False)
    print_banner = get_global_value('print_banner', default=True)
    
    # Print banner within script if not containerized, enabled and verbosity is info or higher
    if containerized == False and print_banner == True and logger.isEnabledFor(logging.INFO):
        print_startup()

    check_for_updates(__version__, containerized, logger)

    if containerized == 'true':
        logger.debug("Environment: Docker")
        logger.debug("Defaulting paths to '/app/data/'")
    else:
        logger.debug("Environment: Local")
        logger.debug("Deezer Engine is running in LOCAL mode.")
        logger.debug(f"Using standard paths './'")

    # Initialize database
    logger.debug("Initializing database components...")
    initialize_all(logger)
    
    # 3. Authenticate
    logger.debug("Requesting Deezer authentication...")
    client = get_authenticated_client(config, logger)
    
    # 4. Strategy Execution Loop
    if not strategies_config or 'playlists' not in strategies_config:
        logger.warning("No strategies found in strategies.yml.")
        return

    total_strategies = len(strategies_config['playlists'])

    for i, s_data in enumerate(strategies_config['playlists'],1):
        # Check for shutdown signal
        if shutdown_event.is_set():
            logger.info("Shutdown signal acknowledged. Skipping remaining strategies.")
            break

        strategy_name = s_data.get('name', 'unnamed_strategy')
        
        # Sanitize the name for the temp filename
        safe_name = strategy_name.lower().replace(" ", "_")
        
        logger.info(f">>> START {i}/{total_strategies}: Processing Strategy: {strategy_name}")
        
        # Log Strategy Definition (Debug Only)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Strategy definition for '{strategy_name}': {s_data}")
        
        # Initialize the Controller for this specific strategy
        controller = StrategyController(client, config, logger, safe_name)
        
        # Update stale dynamic track data
        refresh_stats(client, logger)

        try:
            source_metadata = []
            # Source Phase
            source_metadata = process_sources(s_data, controller, config, client, logger, strategy_name)

            # Modifier Phase
            if shutdown_event.is_set():
                logger.info("Shutdown signal acknowledged. Skipping remaining strategies.")
                break
            update_unprocessed
            process_modifiers(s_data, controller, source_metadata, logger, strategy_name)

            # Destination Phase
            if shutdown_event.is_set():
                logger.info("Shutdown signal acknowledged. Skipping remaining strategies.")
                break
            process_destinations(s_data, controller, logger, strategy_name)

        except Exception as e:
            logger.error(f"Strategy '{strategy_name}' failed: {e}")
            logger.debug("Exception details:", exc_info=True)

if __name__ == "__main__":
    main()