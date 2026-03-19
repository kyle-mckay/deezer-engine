# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import logging
import yaml
from utils.infrastructure.paths import get_data_dir
from .key_validation import (
    CONFIG_ROOT_KEYS,
    CONFIG_SECTION_KEYS,
    format_unknown_key_list,
    get_unknown_keys,
)

config_logger = logging.getLogger("DeezerEngine")


def get_global_value(key, default=None):
    """
    Retrieves a configuration value.
    Checks environment variables (DEEZER_<KEY>) first, then falls back to config.yml.
    """
    # Noisy log, deferring until tracing is implemented to avoid cluttering logs during normal operation
    # config_logger.debug(f"Resolving global config key='{key}' (default_provided={default is not None}).")
    if key.upper() == "CONTAINERIZED":
        env_key = key.upper()
    else:
        env_key = f"DEEZER_{key.upper()}"

    is_sensitive_key = any(token in key.lower() for token in ("arl", "token", "secret", "password", "key"))

    # Check Environment Variables
    if env_key in os.environ:
        value = os.environ[env_key]
        if value.isdigit():
            value = int(value)
        elif value.lower() in ('true', 'yes', '1'):
            value = True
        elif value.lower() in ('false', 'no', '0'):
            value = False

        display_value = "***" if is_sensitive_key else value
        # Noisy log, deferring until tracing is implemented to avoid cluttering logs during normal operation
        # config_logger.debug(
        #    f"Resolved key='{key}' from environment variable '{env_key}' "
        #    f"(type={type(value).__name__}, value={display_value})."
        # )
        return value

    # Check config.yml
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            resolved_value = config.get('config', {}).get(key.lower(), default)
            source = "config.yml" if key.lower() in config.get('config', {}) else "default"
            display_value = "***" if is_sensitive_key else resolved_value
            # Noisy log, deferring until tracing is implemented to avoid cluttering logs during normal operation
            # config_logger.debug(
            #    f"Resolved key='{key}' from {source} "
            #    f"(type={type(resolved_value).__name__}, value={display_value})."
            # )
            return resolved_value
    except Exception as e:
        # Noisy log, deferring until tracing is implemented to avoid cluttering logs during normal operation
        # config_logger.debug(
        #     f"Config read failed while resolving key='{key}' from '{config_path}': {e}. "
        #     "Using default value."
        # )
        return default


def load_config_with_env_overrides():
    """
    Load config.yml and apply environment variable overrides.
    Environment variables take precedence over file values.

    See wiki for all environment overrides
    """
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    config_logger.debug(f"Loading configuration from '{config_path}' with environment overrides.")

    # Load base config from file
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config_logger.debug(f"Config file not found at '{config_path}'. Starting from empty config.")
        config = {}

    if not isinstance(config, dict):
        config_logger.warning("Top-level config.yml content must be an object. Ignoring invalid root structure.")
        config = {}

    unknown_top_level = get_unknown_keys(config, CONFIG_ROOT_KEYS)
    if unknown_top_level:
        formatted_keys = format_unknown_key_list(unknown_top_level, CONFIG_ROOT_KEYS)
        config_logger.warning(f"Unknown top-level config key(s): {formatted_keys}.")

    # Ensure the 'config' section exists
    if 'config' not in config:
        config['config'] = {}

    if not isinstance(config['config'], dict):
        config_logger.warning("The 'config' section must be an object. Ignoring invalid section structure.")
        config['config'] = {}

    unknown_config_keys = get_unknown_keys(config['config'], CONFIG_SECTION_KEYS)
    if unknown_config_keys:
        formatted_keys = format_unknown_key_list(unknown_config_keys, CONFIG_SECTION_KEYS)
        config_logger.warning(f"Unknown config key(s): {formatted_keys}.")

    # Apply environment variable overrides
    env_mappings = {
        'DEEZER_USER_ID': 'user_id',
        'DEEZER_ARL_TOKEN': 'arl_token',
        'DEEZER_CHUNK_SIZE': 'chunk_size',
        'DEEZER_API_BATCH_SIZE': 'api_batch_size',
        'DEEZER_RATE_LIMIT': 'rate_limit',
        'DEEZER_MAX_RETRIES': 'max_retries',
        'DEEZER_LOG_LEVEL': 'log_level',
        'DEEZER_WRITE_LOGS': 'write_logs',
        'DEEZER_PRINT_BANNER': 'print_banner',
        'DEEZER_PLAYLIST_CAP': 'playlist_cap',
        'DEEZER_FAVORITES_CAP': 'favorites_cap',
        'DEEZER_RETENTION': 'retention',
        'DEEZER_FILE_RETENTION': 'file_retention',
        'DEEZER_TRACK_STATS_REFRESH': 'track_stats_refresh',
        'DEEZER_ALBUM_STATS_REFRESH': 'album_stats_refresh',
        'DEEZER_BLOCKLIST_EXPIRY_DAYS': 'blocklist_expiry_days'
    }

    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]

            # Type conversions

            # Integers
            if config_key in ['chunk_size', 'api_batch_size', 'rate_limit', 'max_retries', 'playlist_cap', 'favorites_cap', 'retention', 'file_retention', 'track_stats_refresh', 'album_stats_refresh', 'blocklist_expiry_days']:
                try:
                    value = int(value)
                except ValueError:
                    pass

            # Booleans
            elif config_key in ['write_logs', 'print_banner']:
                value = value.lower() in ('true', '1', 'yes', 'on')

            config['config'][config_key] = value

    applied_keys = [config_key for env_var, config_key in env_mappings.items() if env_var in os.environ]
    if applied_keys:
        config_logger.debug(
            f"Configuration load completed. Applied {len(applied_keys)}/{len(env_mappings)} "
            f"environment overrides: {', '.join(sorted(applied_keys))}."
        )
    else:
        config_logger.debug("Configuration load completed. No environment overrides were applied.")

    return config