import os
import re
import yaml
from pathlib import Path
import requests
from utils.paths import get_data_dir
from utils.logger import setup_logger

def get_global_value(key, default=None):
    """
    Retrieves a configuration value. 
    Checks environment variables (DEEZER_<KEY>) first, then falls back to config.yml.
    """

    if key.upper() == "CONTAINERIZED":
        env_key=key.upper()
    else:
        env_key = f"DEEZER_{key.upper()}"
    
    # Check Environment Variables
    if env_key in os.environ:
        value = os.environ[env_key]
        if value.isdigit():
            return int(value)
        if value.lower() in ('true', 'yes', '1'): return True
        if value.lower() in ('false', 'no', '0'): return False
        return value

    # Check config.yml
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
            return config.get('config', {}).get(key.lower(), default)
    except Exception:
        return default

def load_config_with_env_overrides():
    """
    Load config.yml and apply environment variable overrides.
    Environment variables take precedence over file values.
    
    Supported environment variables:
    - DEEZER_USER_ID: Deezer user ID
    - DEEZER_ARL_TOKEN: Deezer ARL authentication token
    - DEEZER_BATCH_SIZE: Batch size for API operations
    - DEEZER_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - DEEZER_WRITE_LOGS: Whether to write logs to file (true/false)
    - DEEZER_PRINT_BANNER: Whether to print the startup banner (true/false)
    """
    data_dir = get_data_dir()
    config_path = data_dir / 'config.yml'
    
    # Load base config from file
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}
    
    # Ensure the 'config' section exists
    if 'config' not in config:
        config['config'] = {}
    
    # Apply environment variable overrides
    env_mappings = {
        'DEEZER_USER_ID': 'user_id',
        'DEEZER_ARL_TOKEN': 'arl_token',
        'DEEZER_BATCH_SIZE': 'batch_size',
        'DEEZER_LOG_LEVEL': 'log_level',
        'DEEZER_WRITE_LOGS': 'write_logs',
        'DEEZER_PRINT_BANNER': 'print_banner',
        'DEEZER_PLAYLIST_CAP': 'playlist_cap',
        'DEEZER_FAVORITES_CAP': 'favorites_cap'
    }
    
    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            
            # Type conversions

            # Integers
            if config_key in ['batch_size', 'playlist_cap', 'favorites_cap', 'retention']:
                try:
                    value = int(value)
                except ValueError:
                    pass
            
            # Booleans
            elif config_key in ['write_logs', 'print_banner']:
                value = value.lower() in ('true', '1', 'yes', 'on')
            
            config['config'][config_key] = value
    
    return config

def load_strategies_with_env_overrides():
    """
    Load strategies.yml and apply environment variable overrides.
    """
    data_dir = get_data_dir()
    strategies_path = data_dir / 'strategies.yml'
    
    # Load strategies from file
    try:
        with open(strategies_path, 'r') as f:
            strategies = yaml.safe_load(f) or {}
    except FileNotFoundError:
        strategies = {}
    
    return strategies

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
        current_version = extract_version(current_version)

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