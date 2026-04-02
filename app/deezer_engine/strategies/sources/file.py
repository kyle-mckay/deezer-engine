# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import time
from pathlib import Path
from utils.config import get_global_value
from utils.collections import get_collection_name
from utils.infrastructure.files import read_from_csv, read_from_json
from strategies.sources.track import run as fetch_enriched_tracks

# Headers returned from files:
# File  delegates to `track.py` with the extracted id's, so returned rows follow the Track payload shape.

def requires_metadata(source_data=None):
    """
    Only extracts track IDs from the file for later enrichment
    """
    return False

def run(client, config, logger, source_data):
    """
    Fetches tracks an export file
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]

        # Pull config keys
        source_type = source_data[0].get('type').lower()
        file_value = source_data[0].get('filename', source_data[0].get('name', None))
        dir = source_data[0].get('dir', None)

        if file_value is None:
            logger.error("Source type 'file' failed: missing 'filename' or 'name' in configuration.")
            return []

        file_names = file_value if isinstance(file_value, list) else [file_value]
        normalized_file_names = []
        for raw_name in file_names:
            if raw_name is None:
                logger.warning("File source received null filename in list input. Skipping entry.")
                continue

            filename = str(raw_name).strip()
            if not filename:
                logger.warning("File source received empty filename in list input. Skipping entry.")
                continue

            normalized_file_names.append(filename)

        if not normalized_file_names:
            logger.warning("File source has no valid filenames after filtering invalid list entries.")
            return []

        collection = get_collection_name(
            logger,
            source_type,
            normalized_file_names if len(normalized_file_names) > 1 else normalized_file_names[0],
            None,
        )

        tracks = []
        for filename in normalized_file_names:
            full_path = Path(f"{dir}/{filename}").resolve() if dir else Path(filename).resolve()
            logger.debug(f"Full path: {full_path}")
            extention = Path(filename).suffix.lower().removeprefix('.')
            logger.debug(f"Extention: {extention}")

            # Select appropriate reader
            match extention:
                case 'json':
                    imported = read_from_json(full_path, logger)
                case 'csv':
                    imported = read_from_csv(full_path, logger)
                case _:
                    logger.error(f"Unsupported file type: {extention}")
                    continue

            # Collect IDs for enrichment
            for i, track in enumerate(imported, 1):
                try:
                    tracks.append(str(track.get('id')))
                except Exception as e:
                    logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
                    time.sleep(1)
                    continue

        if not tracks:
            return []

        collected_ids = list(dict.fromkeys(tracks))
        logger.info(f"Fetching metadata for {len(collected_ids)} file-imported track IDs...")
        return fetch_enriched_tracks(client, config, logger, [{
            'id': collected_ids,
            'override_collection': collection,
        }])

    except Exception as e:
        logger.error(f"File import failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []