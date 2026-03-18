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
import os
import re
import logging
import yaml
from pathlib import Path
import requests
from utils.paths import get_data_dir
from utils.logger import setup_logger

config_logger = logging.getLogger("DeezerEngine")

def get_bootstrap_logging_settings():
    """
    Resolve logging settings early, before full config loading.
    """
    log_level = os.getenv("DEEZER_LOG_LEVEL")
    write_logs_env = os.getenv("DEEZER_WRITE_LOGS")

    # Prioritize environment variables
    if log_level is not None or write_logs_env is not None:
        resolved_level = (log_level or "INFO").upper()
        resolved_write_logs = True if write_logs_env is None else write_logs_env.lower() in ('true', '1', 'yes', 'on')
        return resolved_level, resolved_write_logs

    # Fall back to config.yml values
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            cfg = config.get('config', {})
            resolved_level = str(cfg.get('log_level', 'INFO')).upper()
            resolved_write_logs = cfg.get('write_logs', True)
            if isinstance(resolved_write_logs, str):
                resolved_write_logs = resolved_write_logs.lower() in ('true', '1', 'yes', 'on')
            return resolved_level, bool(resolved_write_logs)
    except Exception:
        return "INFO", True

def get_global_value(key, default=None):
    """
    Retrieves a configuration value. 
    Checks environment variables (DEEZER_<KEY>) first, then falls back to config.yml.
    """
    config_logger.debug(f"Resolving global config key='{key}' (default_provided={default is not None}).")
    if key.upper() == "CONTAINERIZED":
        env_key=key.upper()
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
        config_logger.debug(
            f"Resolved key='{key}' from environment variable '{env_key}' "
            f"(type={type(value).__name__}, value={display_value})."
        )
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
            config_logger.debug(
                f"Resolved key='{key}' from {source} "
                f"(type={type(resolved_value).__name__}, value={display_value})."
            )
            return resolved_value
    except Exception as e:
        config_logger.debug(
            f"Config read failed while resolving key='{key}' from '{config_path}': {e}. "
            f"Using default value."
        )
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
    
    # Ensure the 'config' section exists
    if 'config' not in config:
        config['config'] = {}
    
    # Apply environment variable overrides
    env_mappings = {
        'DEEZER_USER_ID': 'user_id',
        'DEEZER_ARL_TOKEN': 'arl_token',
        'DEEZER_CHUNK_SIZE': 'chunk_size',
        'DEEZER_API_BATCH_SIZE': 'api_batch_size',
        'DEEZER_RATE_LIMIT': 'rate_limit',
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
            if config_key in ['chunk_size', 'api_batch_size', 'rate_limit', 'playlist_cap', 'favorites_cap', 'retention', 'file_retention', 'track_stats_refresh', 'album_stats_refresh', 'blocklist_expiry_days']:
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

def _validate_modifiers(logger, strategy_name, modifiers, depth=1, path="root"):
    """
    Validates modifiers. If a modifier contains a source (like 'exclude'), 
    it triggers a recursive call back to _validate_sources.
    """
    if not isinstance(modifiers, list):
        logger.error(f"[Depth: {depth}] Strategy '{strategy_name}' at {path}: Modifiers must be a list.")
        return False
    
    vtype = "Modifier"
    logger.debug(f"[Depth: {depth}] Modifiers found for validation: {len(modifiers)}")
    for idx, mod in enumerate(modifiers):
        mod_type = mod.get("type", "unknown")
        current_path = f"{path} > modifier[{mod_type}]"
        
        logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Validating {current_path}")
        
        if "type" not in mod:
            logger.error(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Strategy '{strategy_name}' at {current_path}: Missing 'type'.")
            return False

        # Recursion: Modifier contains a nested source
        if "source" in mod:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Found child source in {mod_type}. Recursing...")
            child_source = mod["source"]
            # Normalize single source dict to a list for the validator
            source_to_validate = child_source if isinstance(child_source, list) else [child_source]
            
            if not _validate_sources(logger, strategy_name, source_to_validate, depth=depth + 1, path=current_path):
                return False
        else:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Found no nested source in {mod_type}.")
    return True

def _validate_sources(logger, strategy_name, sources, depth=1, path="root"):
    """
    Validates sources. If a source contains nested modifiers, 
    it triggers a recursive call back to _validate_modifiers.
    """
    if not sources or not isinstance(sources, list):
        logger.error(f"[Depth: {depth}] Strategy '{strategy_name}' at {path}: Missing or invalid 'source' list.")
        return False
    vtype = "Source"
    logger.debug(f"[Depth: {depth}] Sources found for validation: {len(sources)}")
    for idx, source in enumerate(sources):
        source_type = source.get("type", "unknown")
        current_path = f"{path} > source[{source_type}]"
        
        logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Validating {current_path}")
        
        if "type" not in source:
            logger.error(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Strategy '{strategy_name}' at {current_path}: Missing 'type'.")
            return False
        
        # Recursion: Source contains nested modifiers
        if "modifiers" in source:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Found nested modifiers in {source_type}. Recursing...")
            if not _validate_modifiers(logger, strategy_name, source["modifiers"], depth=depth + 1, path=current_path):
                return False
        else:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Found no nested modifiers in {source_type}.")
            
    return True

def _validate_destination(logger, strategy_name, destination):
    """Validates the destination block."""
    path = "root > destination"
    if not destination or not isinstance(destination, list):
        logger.error(f"[Depth: 1] Strategy '{strategy_name}' at {path}: Missing or invalid list.")
        return False
    
    if len(destination) != 1:
        logger.warning(f"[Depth: 1] Strategy '{strategy_name}' at {path}: Expected 1, found {len(destination)}.")
    
    if "type" not in destination[0]:
        logger.error(f"[Depth: 1] Strategy '{strategy_name}' at {path}: Missing 'type'.")
        return False

    logger.debug(f"[Depth: 1] {path} verified.")
    return True

def load_strategies_with_env_overrides(logger):
    """
    Load strategies.yml, verify the schema recursively, and apply overrides.
    """
    data_dir = get_data_dir()
    strategies_path = data_dir / 'strategies.yml'
    
    logger.debug(f"Attempting to load strategies from {strategies_path}")
    
    try:
        with open(strategies_path, 'r') as f:
            strategies = yaml.safe_load(f)
            if strategies is None or strategies.get("playlists") is None:
                logger.warning(f"Strategies file at {strategies_path} is empty or missing playlists.")
                return {"playlists": []}
    except Exception as e:
        logger.error(f"Error loading YAML: {e}")
        return {"playlists": []}

    if not isinstance(strategies, dict) or "playlists" not in strategies:
        logger.error("Invalid config format: Root element must be 'playlists' list.")
        logger.error("Should be: 'playlists:' not '- playlists:")
        return {"playlists": []}
    
    raw_playlists = strategies.get("playlists", [])
    logger.debug(f"Verifying {len(raw_playlists)} strategies...")
    
    valid_playlists = []
    raw_playlists = strategies.get("playlists", [])

    for idx, strategy in enumerate(raw_playlists):
        name = strategy.get("name", f"Unnamed_Strategy_{idx}")
        logger.debug(f"--- Processing Strategy {idx + 1}/{len(raw_playlists)}: '{name}' ---")

        # Start recursion with explicit path tracking
        sources_ok = _validate_sources(logger, name, strategy.get("source", []), depth=1, path="strategy")
        
        # Top-level modifiers
        modifiers_ok = True
        if "modifiers" in strategy:
            modifiers_ok = _validate_modifiers(logger, name, strategy.get("modifiers"), depth=1, path="strategy")
        
        dest_ok = _validate_destination(logger, name, strategy.get("destination", []))

        if sources_ok and modifiers_ok and dest_ok:
            valid_playlists.append(strategy)
            logger.debug(f"Successfully verified strategy: {name}")
        else:
            logger.error(f"Strategy '{name}' failed validation and will be skipped.")

    invalid_count = len(raw_playlists) - len(valid_playlists)
    logger.debug(
        f"Strategy loading completed. valid={len(valid_playlists)}, invalid={invalid_count}, "
        f"total={len(raw_playlists)}"
    )

    return {"playlists": valid_playlists}

def version_to_int(version_str):
    """
    Equivalent to: sed 's/v//' | awk -F. '{ printf("%03d%03d%03d\n", $1,$2,$3); }'
    Converts 'v1.2.3' or '1.2.3' into 1002003
    """
    if not version_str:
        return 0
    
    clean_v = re.sub(r'^[^0-9]+', '', version_str)

    parts = clean_v.split('.')
    
    while len(parts) < 3:
        parts.append('0')
        
    try:
        normalized_str = "{:03d}{:03d}{:03d}".format(
            int(parts[0]), 
            int(parts[1]), 
            int(parts[2])
        )
        return normalized_str
    except (ValueError, IndexError):
        return 0

def extract_version(version_str):
    """
    Extracts version numbers (e.g., 0.7.0) from a string.
    """
    if not version_str:
        return ""
    
    # Matches sequences of digits and dots (e.g., 1.2.3)
    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_str)
    return match.group(1) if match else version_str

def check_for_updates(current_version, containerized, logger):
    """
    Checks the Codeberg API for a newer release tag.
    Provides context-aware advice for Docker users.
    """
    owner = "kylemmkay" 
    repo_name = "deezer-engine"

    # Updated to Codeberg/Gitea API v1 format
    api_url = f"https://codeberg.org/api/v1/repos/{owner}/{repo_name}/releases/latest"
    
    

    try:
        response = requests.get(api_url, timeout=3)
        response.raise_for_status()
        
        # Codeberg/Gitea uses 'name' for the tag/release title in the 'latest' endpoint
        latest_version = extract_version(response.json().get('name'))
        logger.debug(f"Latest version from Codeberg: {latest_version}")
        current_version = extract_version(current_version)
        logger.debug(f"Current source version: {current_version}")

        if latest_version and version_to_int(latest_version) > version_to_int(current_version):
            logger.warning("=" * 60)
            logger.warning(f"  UPDATE AVAILABLE: {current_version} -> {latest_version}")
            
            if containerized:
                logger.warning("  Container detected: Please pull the latest image to update.")
                # Update this if you move your image hosting to Codeberg as well
                logger.warning(f"  Run: docker pull {owner}/{repo_name}:latest")
            else:
                # Updated link to Codeberg
                logger.warning(f"  Download: https://codeberg.org/{owner}/{repo_name}/releases")
                logger.warning("  Or run 'git pull' if you cloned the repository.")
                
            logger.warning("=" * 60 )
        else:
            logger.debug(f"Version check: You are running the latest version ({current_version}).")
            
    except Exception as e:
        logger.debug(f"Update check skipped: {e}")