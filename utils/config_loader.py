import os
import yaml
from pathlib import Path
from utils.paths import get_data_dir

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
    }
    
    for env_var, config_key in env_mappings.items():
        if env_var in os.environ:
            value = os.environ[env_var]
            
            # Type conversion for specific keys
            if config_key == 'batch_size':
                try:
                    value = int(value)
                except ValueError:
                    pass
            elif config_key == 'write_logs':
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
