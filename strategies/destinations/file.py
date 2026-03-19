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
from datetime import timedelta, datetime
from pathlib import Path
from utils.config import get_global_value
from utils.infrastructure.paths import get_data_dir

def requires_metadata(dest_data=None):
    """
    Export benefits from having full metadata available for complete exports.
    """
    return True
from utils.files import write_to_json, write_to_csv

def cleanup_old_backups(directory, prefix, extension, retention_hours, logger):
    """
    Deletes files matching 'prefix*' with 'extension' older than retention_hours.
    """
    try:
        path_dir = Path(directory)
        # Ensure extension starts with a dot for globbing
        ext_pattern = f".{extension.lstrip('.')}"
        search_pattern = f"{prefix}*{ext_pattern}"
        
        # Calculate cutoff
        cutoff_dt = datetime.now() - timedelta(hours=retention_hours)
        deleted_count = 0
        scanned_count = 0
        skipped_format_count = 0
        logger.debug(
            f"Backup cleanup start: directory={path_dir}, pattern={search_pattern}, "
            f"retention_hours={retention_hours}, cutoff={cutoff_dt.isoformat()}"
        )

        for file_path in path_dir.glob(search_pattern):
            if file_path.is_file():
                scanned_count += 1
                try:
                    # Extract timestamp from filename (e.g., name_20231027_1430)
                    file_stem = file_path.stem
                    parts = file_stem.split('_')
                    
                    # Expected format: yyyymmdd_hhmm (last two segments)
                    date_str = f"{parts[-2]}_{parts[-1]}"
                    file_dt = datetime.strptime(date_str, "%Y%m%d_%H%M")
                    
                    # Compare extracted file time to our cutoff
                    if file_dt < cutoff_dt:
                        file_path.unlink()
                        logger.info(f"Deleted expired backup: {file_path.name}")
                        deleted_count += 1
                        
                except (ValueError, IndexError):
                    # Skip files that don't match the expected timestamp suffix
                    skipped_format_count += 1
                    logger.debug(f"Skipping file with incompatible name format: {file_path.name}")
                    continue

        logger.debug(
            f"Backup cleanup end: scanned={scanned_count}, deleted={deleted_count}, "
            f"skipped_bad_name={skipped_format_count}"
        )
    except Exception as e:
        logger.error(f"Error during backup cleanup: {e}")

def run(client, config, logger, dest_data, tracks):
    """
    Takes your current pipeline and saves it as a file.
    """
    try:
        if isinstance(dest_data, dict):
            dest_data = [dest_data]
        logger.debug(
            f"File destination start: incoming_tracks={len(tracks)}, dest_keys={list(dest_data[0].keys())}"
        )
            
        # Resolve Directory
        raw_dir = dest_data[0].get('dir')
        if not raw_dir:
            final_dir = Path(get_data_dir()).resolve() / "backups"
            logger.debug(f"No directory passed. Defaulting to '{final_dir}'")
        else:
            final_dir = Path(raw_dir).resolve()
            logger.debug(f"Destination dir resolved: {final_dir}")
        
        final_dir.mkdir(parents=True, exist_ok=True)

        # Resolve Filename and Extension
        # Default to 'export_{date}.json' if no name provided
        raw_filename = dest_data[0].get('filename') or dest_data[0].get('name')
        if not raw_filename:
            raw_filename = "export_{date}.json"
            logger.debug(f"No filename provided. Defaulting to: {raw_filename}")

        # Extract extension from the raw filename
        extension = Path(raw_filename).suffix.lower().removeprefix('.')
        if not extension:
            extension = "json" # Safety fallback
            raw_filename += ".json"
            
        # Handle Timestamps and Cleanup Prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        
        # Create a prefix for cleanup by removing the {date} tag and extension
        cleanup_prefix = Path(raw_filename.replace("{date}", "")).stem
        
        # Finalize the filename
        actual_filename = raw_filename.replace("{date}", timestamp)
        final_target = final_dir / actual_filename

        # Cleanup Logic
        dest_retention = dest_data[0].get('retention', get_global_value('file_retention', 168))
        if dest_retention >= 0:
            cleanup_old_backups(final_dir, cleanup_prefix, extension, dest_retention, logger)

        # Export
        logger.debug(f"Saving export to: {final_target}")
        match extension:
            case "json":
                write_to_json(tracks, str(final_target), logger)
            case "csv":
                write_to_csv(tracks, str(final_target), logger)
            case _:
                logger.error(f"Unsupported export format: {extension}")

        logger.debug(
            f"File destination end: path={final_target}, format={extension}, exported_tracks={len(tracks)}"
        )

    except Exception as e:
        logger.error(f"File export failed: {e}")
        logger.debug("Traceback:", exc_info=True)