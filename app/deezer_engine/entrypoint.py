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
from utils.infrastructure.logger import initialize_deezer_logger
from utils.infrastructure.paths import get_data_dir
from utils.config import load_config_with_env_overrides, load_strategies_with_env_overrides, check_for_updates, get_config_snapshot_debug_summary, get_global_value, get_bootstrap_logging_settings, initialize_config_snapshot
from utils.api.auth import get_authenticated_client
from utils.api.fetching import get_tracks
from strategies.base import StrategyController
from utils.db.connection import initialize_all
from utils.collections import get_collection_name
from utils.infrastructure.signals import shutdown_event
from utils.db.blocklist import release_expired_blocklisted_entities
from utils.metadata.orchestration import update_unprocessed, refresh_stats
from __version__ import __version__, __banner__


def _is_pytest_mode():
    """Return True when the process is running under pytest."""
    return "PYTEST_CURRENT_TEST" in os.environ

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


def _normalize_source_value_list(raw_value):
    if isinstance(raw_value, list):
        normalized_values = []
        for item in raw_value:
            if item is None:
                continue

            item_str = str(item).strip()
            if item_str:
                normalized_values.append(item_str)

        return normalized_values

    if raw_value is None:
        return None

    raw_value_str = str(raw_value).strip()
    if not raw_value_str:
        return []

    return [raw_value_str]


def _expand_source_inputs(src, logger):
    for field_name in ("id", "filename", "name"):
        normalized_values = _normalize_source_value_list(src.get(field_name))
        if normalized_values is None:
            continue

        if len(normalized_values) <= 1:
            if len(normalized_values) == 1 and isinstance(src.get(field_name), list):
                normalized_source = dict(src)
                normalized_source[field_name] = normalized_values[0]
                return [normalized_source]
            return [src]

        logger.debug(
            f"Expanding source type '{src.get('type')}' across {len(normalized_values)} '{field_name}' values."
        )
        expanded_sources = []
        for value in normalized_values:
            expanded_source = dict(src)
            expanded_source[field_name] = value
            expanded_sources.append(expanded_source)
        return expanded_sources

    return [src]


def _get_scalar_source_collection_name(src, logger):
    return get_collection_name(
        logger,
        src.get('type'),
        src.get('name', src.get('filename', None)),
        src.get('id', None),
    )


def _get_grouped_source_name(src, source_index):
    source_type = str(src.get('type') or 'unknown').lower()
    return f"{source_type}__grouped__{source_index}"


def _validate_grouped_source_output(src, grouped_source, controller, logger):
    expected_o = src.get('o')
    if expected_o is None:
        return

    source_label = src.get('name', src.get('type'))
    validation_mode = src.get('validation_mode', get_global_value('validation_mode', None))
    actual_o = len(grouped_source.get('tracks', []))

    logger.debug(f"Source '{source_label}' expects grouped output count: {expected_o}")
    controller._validate_io('o', expected_o, actual_o, validation_mode, f"Source '{source_label}'")

def process_sources(s_data, controller, config, client, logger, strategy_name):
    """
    Handles the Source Phase of the strategy.
    Returns one grouped source block per original source definition.
    Cache resolution for each expanded source is delegated to controller.handle_source.
    """
    source_metadata = []
    sources = s_data.get('source', [])
    logger.debug(f"Strategy '{strategy_name}' has {len(sources)} sources defined.")
    
    for source_index, src in enumerate(sources):
        if shutdown_event.is_set():
            logger.debug("Shutdown acknowledged before next source. Skipping remaining sources.")
            break

        expanded_sources = _expand_source_inputs(src, logger)
        grouped_source = {
            'source': dict(src),
            'expanded_sources': [],
            'collection_names': [],
            'group_name': _get_grouped_source_name(src, source_index),
            'modifiers': src.get('modifiers', []),
            'tracks': [],
        }

        for expanded_src in expanded_sources:
            logger.debug(f"Handling source type: {expanded_src.get('type')}")
            source_name = _get_scalar_source_collection_name(expanded_src, logger)
            grouped_source['expanded_sources'].append(dict(expanded_src))
            grouped_source['collection_names'].append(source_name)

            fetched_tracks = controller.handle_source(expanded_src, source_name) or []

            grouped_source['tracks'].extend(fetched_tracks)
            logger.debug(f"Source '{source_name}': Total tracks collected so far: {len(grouped_source['tracks'])}")

            if shutdown_event.is_set():
                logger.debug("Shutdown passing through process_sources acknowledged. Skipping remaining strategies.")
                break

        _validate_grouped_source_output(src, grouped_source, controller, logger)
        source_metadata.append(grouped_source)
    
    return source_metadata

def process_modifiers(s_data, controller, source_metadata, logger, strategy_name):
    """Handles the Modifier Phase, including source-specific and global modifiers."""
    
    all_processed_tracks = []
    last_modifier_context = None
    for grouped_source in source_metadata:
        if shutdown_event.is_set():
            logger.debug("Shutdown acknowledged before source-specific modifiers. Skipping remaining modifier work.")
            break

        source_name = grouped_source.get('group_name')
        child_modifiers = grouped_source.get('modifiers', [])
        fetched = list(grouped_source.get('tracks', []))
        last_modifier_context = source_name
        logger.debug(f"Fetched {len(fetched)} in-memory tracks from {source_name}")

        if child_modifiers:
            logger.debug(f"Applying {len(child_modifiers)} child modifiers to source '{source_name}'")
            for mod in child_modifiers:
                if shutdown_event.is_set():
                    logger.debug("Shutdown acknowledged during source-specific modifiers. Stopping child modifier execution.")
                    break
                logger.debug(f"Applying child modifier: {mod.get('type')}")
                fetched = controller.handle_modifier(mod, fetched, source_name)
        all_processed_tracks.extend(fetched)
    # 2. Set the in-memory pipeline for global modifiers
    logger.debug(f"Total tracks collected for global pipeline: {len(all_processed_tracks)}")
    controller.pipeline = all_processed_tracks
    global_modifiers = s_data.get('modifiers', [])
    if global_modifiers:
        logger.debug(f"Strategy '{strategy_name}' has {len(global_modifiers)} global modifiers defined.")
        for mod in global_modifiers:
            if shutdown_event.is_set():
                logger.debug("Shutdown acknowledged before global modifiers. Skipping remaining modifiers.")
                break
            logger.debug(f"Applying global modifier: {mod.get('type')}")
            controller.handle_modifier(mod, None, last_modifier_context)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Pipeline size after '{mod.get('type')}': {len(controller.pipeline)} tracks.")

def process_destinations(s_data, controller, logger, strategy_name):
    """Handles the Destination Phase of the strategy."""
    destinations = s_data.get('destination', [])
    if destinations:
        for dest in destinations:
            dest_type = dest.get('type')
            destination_identifier = dest.get('id') or dest.get('name') or 'Unknown'
            logger.debug(
                f"Routing to destination: {dest_type} (ID: {destination_identifier})"
            )
            controller.handle_destination(dest)
        logger.debug(f"Successfully completed: {strategy_name}")
    else:
        logger.warning(f"Strategy '{strategy_name}' has no destination defined.")

def main():
    # 1. Bootstrap logging before full config load
    bootstrap_log_level, bootstrap_write_logs = get_bootstrap_logging_settings()
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    bootstrap_actual_level = bootstrap_log_level if bootstrap_log_level in valid_levels else 'INFO'
    logger = initialize_deezer_logger(bootstrap_actual_level, log_to_file=bootstrap_write_logs)

    # Build startup config/env snapshot once for this process.
    initialize_config_snapshot(force=True)
    logger.debug(f"Config snapshot initialized in memory. {get_config_snapshot_debug_summary()}")

    # 2. Load data
    config = load_configs("config")

    # 3. Validate remaining configuration and keep logger in sync
    user_log_level = config.get('config', {}).get('log_level', 'INFO').upper()
    should_write_logs = config.get('config', {}).get('write_logs', True)
    
    # Check if the level is officially recognized by the logging module
    # logging.getLevelName(str) returns the numeric level if valid, 
    # but only if it's a known string like 'DEBUG'.
    actual_level = user_log_level
    warning_needed = False
    
    if user_log_level not in valid_levels:
        actual_level = 'INFO'
        warning_needed = True

    logger.setLevel(getattr(logging, actual_level, logging.INFO))
    
    if bool(should_write_logs) != bool(bootstrap_write_logs):
        logger.warning(
            f"write_logs changed after startup bootstrap (bootstrap={bootstrap_write_logs}, configured={should_write_logs}). "
            "A restart is required for file-handler changes to take effect."
        )

    # Register signal handlers for CTRL+C (SIGINT) and termination/docker stop (SIGTERM).
    def signal_handler(sig, frame):
        """Logs once and sets the shared shutdown event."""
        logger.warning(f"Signal {sig} received. Finishing current operation then exiting cleanly...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Issue the warning if config was bad
    if warning_needed:
        logger.warning(f"Unsupported log level '{user_log_level}' found in config.yml. Defaulting to 'INFO'.")

    strategies_config = load_configs("strategy", logger)

    containerized = get_global_value('containerized', default=False)
    print_banner = get_global_value('print_banner', default=True)
    
    # Print banner within script if not containerized, enabled and verbosity is info or higher
    if (not containerized) and print_banner and logger.isEnabledFor(logging.INFO):
        print_startup()

    check_for_updates(__version__, containerized, logger)

    if containerized:
        logger.debug("Environment: Docker")
        logger.debug("Defaulting paths to '/deezer_engine/data/'")
    else:
        logger.debug("Environment: Local")
        logger.debug("Deezer Engine is running in LOCAL mode.")
        logger.debug(f"Using standard paths './'")

    # Initialize database
    logger.debug("Initializing database components...")
    initialize_all(logger)
    release_expired_blocklisted_entities(logger)
    
    # 3. Authenticate
    logger.debug("Requesting Deezer authentication...")
    auth_config = None if _is_pytest_mode() else config
    client = get_authenticated_client(auth_config, logger)
    
    # 4. Strategy Execution Loop
    if not strategies_config or 'playlists' not in strategies_config:
        logger.warning("No strategies found in strategies.yml.")
        return

    total_strategies = len(strategies_config['playlists'])
    pull_metadata = get_global_value('pull_metadata', True)

    for i, s_data in enumerate(strategies_config['playlists'],1):
        # Check for shutdown signal
        if shutdown_event.is_set():
            logger.debug("Shutdown acknowledged. No more strategies will be run.")
            break

        strategy_name_raw = s_data.get('name', 'unnamed_strategy')
        if strategy_name_raw is None:
            strategy_name = 'unnamed_strategy'
        else:
            strategy_name = str(strategy_name_raw)

        # Sanitize the name for the temp filename
        safe_name = strategy_name.lower().replace(" ", "_")
        
        logger.info(f">>> START {i}/{total_strategies}: Processing Strategy: {strategy_name}")
        
        # Log Strategy Definition (Debug Only)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Strategy definition for '{strategy_name}': {s_data}")
        
        # Initialize the Controller for this specific strategy
        controller = StrategyController(client, config, logger, safe_name)
        
        # Update stale dynamic track data
        if pull_metadata:
            refresh_stats(client, logger)
        else:
            logger.debug("pull_metadata=false: skipping stats refresh.")

        try:
            source_metadata = []
            # Source Phase
            source_metadata = process_sources(s_data, controller, config, client, logger, strategy_name)

            # Modifier Phase
            if shutdown_event.is_set():
                logger.debug("Shutdown acknowledged. Skipping modifier and destination phases.")
                break
            process_modifiers(s_data, controller, source_metadata, logger, strategy_name)

            # Destination Phase
            if shutdown_event.is_set():
                logger.debug("Shutdown acknowledged. Skipping destination phase.")
                break
            process_destinations(s_data, controller, logger, strategy_name)

        except Exception as e:
            logger.error(f"Strategy '{strategy_name}' failed: {e}")
            logger.debug("Exception details:", exc_info=True)

    # Final enrichment pass
    if not shutdown_event.is_set():
        if pull_metadata:
            logger.info("Performing final metadata enrichment pass...")
            try:
                update_unprocessed(client, logger)
                logger.debug("Final enrichment pass completed.")
            except Exception as e:
                logger.error(f"Final enrichment pass failed: {e}")
                logger.debug("Final enrichment error details:", exc_info=True)
        else:
            logger.info("pull_metadata=false: skipping final metadata enrichment pass.")
    else:
        logger.info("Shutdown signal active; deferring final enrichment to next run.")

if __name__ == "__main__":
    main()