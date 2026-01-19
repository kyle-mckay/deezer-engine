import os
import yaml
from pathlib import Path
import requests
from utils.paths import get_data_dir

def get_global_value(key, default=None):
    """
    Retrieves a configuration value. 
    Checks environment variables (DEEZER_<KEY>) first, then falls back to config.yml.
    """
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
            return config.get('config', {}).get(key, default)
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
            
            # Type conversion
            if config_key in ['batch_size', 'playlist_cap', 'favorites_cap']:
                try:
                    value = int(value)
                except ValueError:
                    pass
            elif config_key in ['write_logs', 'print_banner']:
                value = value.lower() in ('true', '1', 'yes', 'on')
            
            config['config'][config_key] = value
    
    return config

def load_strategies_with_env_overrides():
    """
    Load strategies.yml and apply environment variable overrides.
    
    Supported environment variables:
    - DEEZER_SCHEDULE: Cron schedule expression (e.g., "0 2 * * *")
    """
    data_dir = get_data_dir()
    strategies_path = data_dir / 'strategies.yml'
    
    # Load strategies from file
    try:
        with open(strategies_path, 'r') as f:
            strategies = yaml.safe_load(f) or {}
    except FileNotFoundError:
        strategies = {}
    
    # Note: DEEZER_SCHEDULE is used by the entrypoint script
    # This function is here for consistency and future extensibility
    
    return strategies

def check_for_updates(current_version,containerized,logger):
    """
    Checks the GitHub API for a newer release tag.
    Provides context-aware advice for Docker users.
    """
    dh_owner = "kylemmkay"
    gh_owner = "kyle-mckay"
    repo_name = "deezer-engine"

    api_url = f"https://api.github.com/repos/{gh_owner}/{repo_name}/releases/latest"
    
    try:
        response = requests.get(api_url, timeout=3)
        response.raise_for_status()
        latest_version = response.json().get('tag_name')

        if latest_version and latest_version != current_version:
            logger.warning("=" * 60)
            logger.warning(f"  UPDATE AVAILABLE: {current_version} -> {latest_version}")
            
            if containerized:
                # Docker-specific advice
                logger.warning("  Container detected: Please pull the latest image to update.")
                logger.warning(f"  Run: docker pull {dh_owner}/{repo_name}:<tag number>")
            else:
                # Local execution advice
                logger.warning(f"  Download: https://github.com/{gh_owner}/{repo_name}/releases/latest")
                logger.warning("  Or run 'git pull' if you cloned the repository.")
                
            logger.warning("=" * 60 )
        else:
            logger.debug(f"Version check: You are running the latest version ({current_version}).")
            
    except Exception as e:
        logger.debug(f"Update check skipped: {e}")