# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from strategies.sources.track import run as fetch_enriched_tracks
from utils.collections import get_collection_name
from utils.infrastructure.files import read_from_csv, read_from_json
from utils.metadata.tracks import TRACK_HEADERS_AVAILABLE_IN_ALL_FETCH_TYPES, ingest_shallow_tracks
from utils.metadata.orchestration import add_key_to_dicts

# Headers returned from files:
# File source returns imported rows as-is (all columns preserved).
# Files with sufficient metadata to meet shallow ingestion requirements are ingested directly.


def requires_metadata(source_data=None):
    """
    Only extracts track IDs from the file for later enrichment
    """
    return False


def _resolve_input_path(source_dir, filename):
    """Resolve a file-source path across common runtime working directories."""
    worker_path = Path(__file__).resolve()
    app_root = worker_path.parents[3]
    repo_root = worker_path.parents[4]

    filename_path = Path(filename)
    if filename_path.is_absolute():
        return filename_path

    if source_dir:
        relative_path = Path(source_dir) / filename
    else:
        relative_path = Path(filename)

    candidates = [
        relative_path,
        app_root / relative_path,
        repo_root / relative_path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    # Preserve previous behavior when no candidate exists so downstream logging remains informative.
    return candidates[0].resolve()


def _value_is_present(value):
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def _sanitize_imported_row(row, collection):
    sanitized_row = dict(row)
    sanitized_row.pop('date_cached', None)
    sanitized_row.pop('disk_number', None)
    sanitized_row.setdefault('collection', collection)
    return sanitized_row


def _has_minimum_shallow_headers(row):
    for header_name in TRACK_HEADERS_AVAILABLE_IN_ALL_FETCH_TYPES:
        if header_name not in row or not _value_is_present(row.get(header_name)):
            return False

    return True


def run(client, config, logger, source_data):
    """
    Fetches tracks an export file
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]

        source_type = source_data[0].get('type', 'file').lower()
        file_value = source_data[0].get('filename', source_data[0].get('name', None))
        source_dir = source_data[0].get('dir', None)

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

        clean_tracks = []
        for filename in normalized_file_names:
            collection = get_collection_name(logger, source_type, filename, None)
            full_path = _resolve_input_path(source_dir, filename)
            logger.debug(f"Full path: {full_path}")
            extention = Path(filename).suffix.lower().removeprefix('.')
            logger.debug(f"Extention: {extention}")

            match extention:
                case 'json':
                    imported = read_from_json(full_path, logger)
                case 'csv':
                    imported = read_from_csv(full_path, logger)
                case _:
                    logger.error(f"Unsupported file type: {extention}")
                    continue

            if imported is None:
                logger.warning(f"No data loaded from file '{full_path}'. Skipping.")
                continue

            imported_rows = []
            for row in imported:
                if not isinstance(row, dict):
                    logger.warning(f"File source row is not an object in '{full_path}'. Skipping row.")
                    continue

                imported_rows.append(_sanitize_imported_row(row, collection))

            if not imported_rows:
                continue

            good_tracks = []
            bad_tracks = []
            for row in imported_rows:
                if _has_minimum_shallow_headers(row):
                    good_tracks.append(row)
                else:
                    bad_tracks.append(row)

            logger.debug(
                f"File source classified rows for '{filename}': total={len(imported_rows)}, good={len(good_tracks)}, bad={len(bad_tracks)}"
            )

            if good_tracks:
                clean_tracks.extend(ingest_shallow_tracks(good_tracks, logger))

            delegated_ids = []
            seen_ids = set()
            unresolved_rows = 0
            for row in bad_tracks:
                track_id_raw = row.get('id')
                if track_id_raw is None:
                    unresolved_rows += 1
                    logger.warning("File source row is missing 'id' and cannot be enriched. Skipping row.")
                    continue

                track_id = str(track_id_raw).strip()
                if not track_id:
                    unresolved_rows += 1
                    logger.warning("File source row has empty 'id' and cannot be enriched. Skipping row.")
                    continue

                if track_id not in seen_ids:
                    seen_ids.add(track_id)
                    delegated_ids.append(track_id)

            if delegated_ids:
                logger.info(f"Fetching metadata for {len(delegated_ids)} file track IDs...")
                delegated_tracks = fetch_enriched_tracks(client, config, logger, [{
                    'id': delegated_ids,
                    'override_collection': collection,
                }]) or []
                clean_tracks.extend(ingest_shallow_tracks(delegated_tracks, logger))

                resolved_ids = {
                    str(track.get('id')).strip()
                    for track in delegated_tracks
                    if track.get('id') is not None and str(track.get('id')).strip()
                }
                unresolved_ids = [track_id for track_id in delegated_ids if track_id not in resolved_ids]
                if unresolved_ids:
                    logger.warning(
                        f"File source could not enrich {len(unresolved_ids)} delegated IDs. Sample: {unresolved_ids[:5]}"
                    )

            if unresolved_rows:
                logger.debug(f"File source skipped {unresolved_rows} bad rows without usable IDs.")

        if not clean_tracks:
            return []

        return clean_tracks

    except Exception as e:
        logger.error(f"File import failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []