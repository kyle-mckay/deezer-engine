# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime, timedelta

from utils.config import get_global_value
from utils.api.fetching import get_tracks
from utils.db.fetch import fetch_entities_by
from utils.metadata.orchestration import add_key_to_dicts

# Header returned from track:
# Returns: all track fields as it performs individual track fetches.

def requires_metadata(source_data=None):
    """
    Track source only requires track ID to fetch tracks.
    """
    return False


def run(client, config, logger, source_data):
    """
    Fetch one or more Deezer tracks by ID using batched DB/API retrieval.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]

        retention_hrs = source_data[0].get('retention', get_global_value('retention', default=0))
        override_collection_raw = source_data[0].get('override_collection')
        id_value = source_data[0].get('id')

        override_collection = None
        if override_collection_raw is not None:
            override_collection = str(override_collection_raw).strip()
            if not override_collection:
                logger.warning("Track source received empty override_collection. Ignoring override.")
                override_collection = None

        if id_value is None:
            logger.error("Source type 'track' failed: missing 'id' in configuration.")
            return []

        track_ids = id_value if isinstance(id_value, list) else [id_value]
        normalized_track_ids = []
        for raw_track_id in track_ids:
            if raw_track_id is None:
                logger.warning("Track source received null ID in list input. Skipping entry.")
                continue

            track_id = str(raw_track_id).strip()
            if not track_id:
                logger.warning("Track source received empty ID in list input. Skipping entry.")
                continue

            normalized_track_ids.append(track_id)

        if not normalized_track_ids:
            logger.warning("Track source has no valid IDs after filtering invalid list entries.")
            return []

        # Preserve source order for output while using a unique ID set for DB/API efficiency.
        unique_track_ids = list(dict.fromkeys(normalized_track_ids))

        db_rows = fetch_entities_by(
            'tracks',
            'id',
            'IN',
            unique_track_ids,
            return_ids_only=False,
            logger=logger,
        )
        db_by_id = {str(row.get('id')): row for row in db_rows if row.get('id') is not None}

        fresh_by_id = {}
        ids_to_fetch = []

        if retention_hrs and retention_hrs > 0:
            expiry_cutoff = datetime.now() - timedelta(hours=retention_hrs)
            for track_id in unique_track_ids:
                row = db_by_id.get(track_id)
                if not row:
                    ids_to_fetch.append(track_id)
                    continue

                cached_at_raw = row.get('date_cached')
                if not cached_at_raw:
                    ids_to_fetch.append(track_id)
                    continue

                try:
                    cached_at = datetime.fromisoformat(str(cached_at_raw))
                except ValueError:
                    ids_to_fetch.append(track_id)
                    continue

                if cached_at > expiry_cutoff:
                    fresh_by_id[track_id] = row
                else:
                    ids_to_fetch.append(track_id)
        else:
            ids_to_fetch = unique_track_ids

        fetched_by_id = {}
        if ids_to_fetch:
            if not override_collection:
                # Only show the info if we're fetching as a track source not using as a wrapper around another collection type (e.g. smarttracklist) that would have its own logging.
                logger.info(f"Fetching metadata for {len(ids_to_fetch)} requested track IDs...")
            fetched_tracks = get_tracks(
                client,
                logger,
                'database',
                'tracks',
                track_ids=ids_to_fetch,
            )
            fetched_by_id = {
                str(track.get('id')): track for track in fetched_tracks if track.get('id') is not None
            }

        resolved_by_id = {**fresh_by_id, **fetched_by_id}
        collected_tracks = []
        unresolved_ids = []
        for track_id in normalized_track_ids:
            resolved_track = resolved_by_id.get(track_id)
            if resolved_track is None:
                unresolved_ids.append(track_id)
                continue
            collected_tracks.append(dict(resolved_track))

        if unresolved_ids:
            unresolved_unique = list(dict.fromkeys(unresolved_ids))
            logger.warning(
                f"Track source could not resolve {len(unresolved_unique)} IDs. Sample: {unresolved_unique[:5]}"
            )

        # Tag each track with collection identity: explicit override or default track__<id> pattern
        tagged_tracks = []
        for track in collected_tracks:
            track_copy = dict(track)
            if override_collection:
                track_copy['collection'] = override_collection
            else:
                track_id = track_copy.get('id')
                if track_id:
                    track_copy['collection'] = f"track__{track_id}"
            tagged_tracks.append(track_copy)
        collected_tracks = tagged_tracks

        if collected_tracks:
            sample_ids = [t.get('id') for t in collected_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        return collected_tracks

    except Exception as e:
        logger.error(f"Critical failure in track source: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []