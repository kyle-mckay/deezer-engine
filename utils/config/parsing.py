# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import logging
import copy
from threading import RLock
import yaml
from utils.infrastructure.paths import get_data_dir
from .key_validation import (
    CONFIG_ROOT_KEYS,
    CONFIG_SECTION_KEYS,
    format_unknown_key_list,
    get_unknown_keys,
)

config_logger = logging.getLogger("DeezerEngine")

_CONFIG_LOCK = RLock()
_CONFIG_SNAPSHOT = None
_ENV_SNAPSHOT = {}

ENV_MAPPINGS = {
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
    'DEEZER_BLOCKLIST_EXPIRY_DAYS': 'blocklist_expiry_days',
    'DEEZER_LOG_INTERVAL': 'log_interval',
    'DEEZER_HISTORY_LOOKBACK': 'history_lookback',
    'DEEZER_HISTORY_LIMIT': 'history_limit',
}

INT_CONFIG_KEYS = {
    'chunk_size',
    'api_batch_size',
    'rate_limit',
    'max_retries',
    'playlist_cap',
    'favorites_cap',
    'retention',
    'file_retention',
    'track_stats_refresh',
    'album_stats_refresh',
    'blocklist_expiry_days',
    'log_interval',
    'history_lookback',
    'history_limit',
}

BOOL_CONFIG_KEYS = {'write_logs', 'print_banner'}

SENSITIVE_KEY_TOKENS = ("arl", "token", "secret", "password", "key")


def _coerce_general_env_value(value):
    if not isinstance(value, str):
        return value
    if value.isdigit():
        return int(value)

    lowered = value.lower()
    if lowered in ('true', 'yes', '1'):
        return True
    if lowered in ('false', 'no', '0'):
        return False
    return value


def _is_sensitive_key(key):
    return any(token in str(key).lower() for token in SENSITIVE_KEY_TOKENS)


def _snapshot_debug_summary(config_snapshot, env_snapshot):
    config_section = config_snapshot.get('config', {}) if isinstance(config_snapshot, dict) else {}
    config_keys = sorted(config_section.keys())
    env_override_keys = [config_key for env_var, config_key in ENV_MAPPINGS.items() if env_var in env_snapshot]

    masked_override_keys = [
        config_key if not _is_sensitive_key(config_key) else f"{config_key}:***"
        for config_key in sorted(env_override_keys)
    ]

    return (
        f"snapshot_id={hex(id(config_snapshot))}, "
        f"config_keys={len(config_keys)}, "
        f"env_snapshot_keys={len(env_snapshot)}, "
        f"env_overrides_applied={len(env_override_keys)}, "
        f"override_keys={masked_override_keys}"
    )


def _coerce_config_value(config_key, value):
    if config_key in INT_CONFIG_KEYS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    if config_key in BOOL_CONFIG_KEYS:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ('true', '1', 'yes', 'on')

    return value


def _build_env_snapshot():
    return {
        env_key: env_value
        for env_key, env_value in os.environ.items()
        if env_key.startswith('DEEZER_') or env_key == 'CONTAINERIZED'
    }


def _load_base_config():
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    config_logger.debug(f"Loading configuration from '{config_path}' with environment overrides.")

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

    if 'config' not in config:
        config['config'] = {}

    if not isinstance(config['config'], dict):
        config_logger.warning("The 'config' section must be an object. Ignoring invalid section structure.")
        config['config'] = {}

    unknown_config_keys = get_unknown_keys(config['config'], CONFIG_SECTION_KEYS)
    if unknown_config_keys:
        formatted_keys = format_unknown_key_list(unknown_config_keys, CONFIG_SECTION_KEYS)
        config_logger.warning(f"Unknown config key(s): {formatted_keys}.")

    return config


def _apply_env_overrides(config, env_snapshot):
    applied_keys = []
    for env_var, config_key in ENV_MAPPINGS.items():
        if env_var in env_snapshot:
            raw_value = env_snapshot[env_var]
            config['config'][config_key] = _coerce_config_value(config_key, raw_value)
            applied_keys.append(config_key)

    if applied_keys:
        config_logger.debug(
            f"Configuration load completed. Applied {len(applied_keys)}/{len(ENV_MAPPINGS)} "
            f"environment overrides: {', '.join(sorted(applied_keys))}."
        )
    else:
        config_logger.debug("Configuration load completed. No environment overrides were applied.")

    return config


def initialize_config_snapshot(force=False):
    """
    Build an in-memory config snapshot once per process startup.
    """
    global _CONFIG_SNAPSHOT, _ENV_SNAPSHOT

    with _CONFIG_LOCK:
        if _CONFIG_SNAPSHOT is not None and not force:
            return _CONFIG_SNAPSHOT

        _ENV_SNAPSHOT = _build_env_snapshot()
        base_config = _load_base_config()
        _CONFIG_SNAPSHOT = _apply_env_overrides(base_config, _ENV_SNAPSHOT)
        return _CONFIG_SNAPSHOT


def reset_config_snapshot():
    """
    Clear in-memory config/env snapshots.
    Intended for tests and explicit re-initialization.
    """
    global _CONFIG_SNAPSHOT, _ENV_SNAPSHOT

    with _CONFIG_LOCK:
        _CONFIG_SNAPSHOT = None
        _ENV_SNAPSHOT = {}


def get_config_snapshot_debug_summary():
    """
    Return a sanitized snapshot summary string for one-time startup logging.
    """
    snapshot = initialize_config_snapshot()
    return _snapshot_debug_summary(snapshot, _ENV_SNAPSHOT)


def _get_env_snapshot_value(key):
    env_key = key.upper() if key.upper() == 'CONTAINERIZED' else f"DEEZER_{key.upper()}"
    if env_key not in _ENV_SNAPSHOT:
        return None, False
    return _coerce_general_env_value(_ENV_SNAPSHOT[env_key]), True


def get_global_value(key, default=None):
    """
    Retrieves a configuration value.
    Checks environment variables (DEEZER_<KEY>) first, then falls back to config.yml.
    """
    try:
        snapshot = initialize_config_snapshot()
    except Exception:
        return default

    env_value, found = _get_env_snapshot_value(key)
    if found:
        return env_value

    return snapshot.get('config', {}).get(key.lower(), default)


def load_config_with_env_overrides():
    """
    Load config.yml and apply environment variable overrides.
    Environment variables take precedence over file values.

    See wiki for all environment overrides
    """
    snapshot = initialize_config_snapshot()
    return copy.deepcopy(snapshot)
