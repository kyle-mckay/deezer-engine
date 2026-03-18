import json
import random
import time
from pathlib import Path
from datetime import datetime
from utils.deezer_auth import get_authenticated_session
from utils.config_loader import get_global_value
from utils.collections import get_collection_name
from utils.infrastructure.paths import get_data_dir
from utils.files import read_from_csv, read_from_json

def run(client, config, logger, source_data):
    """
    Fetches tracks an export file
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]
        
        # Pull config keys
        source_type = source_data[0].get('type').lower()
        source_retention = source_data[0].get('retention', get_global_value('retention', 0))
        filename = source_data[0].get('filename', None)
        dir = source_data[0].get('dir', None)

        if filename and dir:
            full_path = Path(f"{dir}/{filename}").resolve()
            logger.debug(f"Full path: {full_path}")
            extention = Path(filename).suffix.lower().removeprefix('.')
            logger.debug(f"Extention: {extention}")
            basename = Path(filename).stem
            logger.debug(f"Basename: {basename}")
        
        # Determine collection name for caching
        collection = get_collection_name(logger, source_type, filename, None)

        # Select appropriate reader
        match extention:
            case 'json':
                imported = read_from_json(full_path, logger)
            case 'csv':
                imported = read_from_csv(full_path, logger)
            case _:
                logger.error(f"Unsupported file type: {extention}")
                return []
        
        # Applies collection name for cache
        tracks = []
        date_time = datetime.now().isoformat()
        for i, track in enumerate(imported, 1):
            try:
                # fetch for source ID collection
                tracks.append({
                    'id': str(track.get('id')),
                    'collection': f"{collection}",
                    'date_cached': date_time
                })
            except Exception as e:
                logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
                time.sleep(1)
                continue
        
        return tracks

    except Exception as e:
        logger.error(f"File import failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []