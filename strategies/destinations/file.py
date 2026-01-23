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
import time
from datetime import timedelta
import json
import os
from pathlib import Path
import math
from datetime import datetime
import random
from utils.deezer_auth import get_authenticated_session
from utils.config_loader import get_global_value
from utils.paths import get_data_dir
from utils.files import write_to_json, write_to_csv

def cleanup_old_backups(directory, prefix, extension, retention_hours, logger):
    """
    Deletes files matching 'prefix*' with 'extension' older than retention_hours.
    """
    logger.debug(f">>> START: utils.files.cleanup_old_backups)")

    try:
        path_dir = Path(directory)
        # Match files starting with the prefix and ending with the extension
        search_pattern = f"{prefix}*.{extension}"
        
        # Calculate cutoff using hours
        cutoff_timestamp = (datetime.now() - timedelta(hours=retention_hours)).timestamp()
        deleted_count = 0

        for file_path in path_dir.glob(search_pattern):
            if file_path.is_file():
                # Compare file modification time to our cutoff
                if file_path.stat().st_mtime < cutoff_timestamp:
                    file_path.unlink()
                    logger.info(f"Deleted expired backup: {file_path.name}")
                    deleted_count += 1

        logger.debug(f"Cleanup complete. Deleted {deleted_count} files.")
        logger.debug("<<< END: utils.files.cleanup_old_backups")

    except Exception as e:
        logger.error(f"Error during backup cleanup: {e}")

def run(client, config, logger, dest_data, tracks):
    """
    Takes your current pipeline and saves it as a file.
    """
    logger.debug(">>> START: strategies.destinations.file.run")
    target_id = str(dest_data.get('id'))
    method = dest_data.get('order', 'smart')
    arl = config.get('config', {}).get('arl_token')
    user_id = str(config.get('config', {}).get('user_id'))

    try:
        if isinstance(dest_data, dict):
            dest_data = [dest_data]
        # Extract data

        dest_type = dest_data[0].get('type')
        if dest_type != "file":
            logger.error(f"Error: Entered 'file' destination but was passed type: '{dest_type}'")
        else:
            dest_type = dest_type.lower()
        
        dest_format = dest_data[0].get('format')
        if not dest_format:
            logger.debug(f"File destination was passed invalid or missing format: '{format}'. Defaulting to json")
            dest_format = "json"
        else:
            dest_format = dest_format.lower()
        
        dest_dir = dest_data[0].get('dir')
        root_dir = get_data_dir()
        if not dest_dir:
            final_dir = Path(root_dir).resolve() / "backups"
            logger.debug(f"Destination directory was passed invalid or missing: '{dest_dir}'. Defaulting to '{final_dir}'")
        else:
            final_dir = Path(dest_dir).resolve()
            logger.debug(f"Using passed dest_dir: '{dest_dir}'")

        dest_filename = dest_data[0].get('filename')
        if not dest_filename:
            dest_filename = 'file_{date}'
            logger.debug("No filename has been passed to destination file. Defaulting to timestamp: 'file_{date}'")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        
        # Determine the prefix for cleanup
        if dest_filename:
            cleanup_prefix = dest_filename.replace("{date}", "")
        else:
            cleanup_prefix = None

        if dest_filename:
            dest_filename = dest_filename.replace("{date}", f"_{timestamp}")
            logger.debug(f"Using passed dest_filename: '{dest_filename}'")
        
        # Clean old backups
        dest_retention = dest_data[0].get('retention',get_global_value('file_retention',168))
        
        if dest_retention >= 0 and cleanup_prefix:
            cleanup_old_backups(final_dir, cleanup_prefix, dest_format, dest_retention, logger)

        # Build full path
        final_target = f"{final_dir}/{dest_filename}.{dest_format}"
        logger.debug(f"Saving export to path: '{final_target}")

        match dest_format:
            case "json":
                logger.debug(f"Exporting Tracks to JSON")
                write_to_json(tracks, final_target, logger)
            case "csv":
                logger.debug(f"Exporting tracks to CSV")
                write_to_csv(tracks, final_target, logger)

        logger.debug("<<< END: strategies.destinations.file.run")

    except Exception as e:
        logger.error(f"Sync failed for '{target_id}': {e}")
        logger.debug("Traceback:", exc_info=True)