import os
from pathlib import Path

def get_data_dir():
    """Get the data directory path, using app/data in containers, current dir otherwise."""
    if os.getenv('CONTAINERIZED', 'false').lower() == 'true':
        return Path('/app/data')
    else:
        return Path('.')

def get_cache_dir():
    """Get the cache directory path."""
    return get_data_dir() / 'cache'

def get_tmp_dir():
    """Get the tmp directory path."""
    return get_data_dir() / 'tmp'

def get_logs_dir():
    """Get the logs directory path."""
    return get_data_dir() / 'logs'

def _cleanup_old_caches(type, var, current_cache_path, logger):
    """Deletes old cache files for the same playlist ID to prevent folder clutter."""
    try:
        cache_dir = get_cache_dir()
        current_filename = os.path.basename(current_cache_path)
        cleanup = False
        for f in os.listdir(cache_dir):
            if type == "playlist":
                # Check for files with same ID but different names
                if f.startswith(f"playlist_{var}") and f != current_filename:
                    cleanup = True
            elif type == "favorites":
                if f.startswith(f"favorites_{var}") and f != current_filename:
                    cleanup = True
            
            if cleanup:
                    os.remove(os.path.join(cache_dir, f))
                    logger.debug(f"Cleaned up old cache file: {f}")
    
    except Exception as e:
        logger.warn(f"Cleanup failed (non-critical): {e}")