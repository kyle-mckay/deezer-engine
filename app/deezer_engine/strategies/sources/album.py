# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from utils.api.fetching import fetch_album_metadata_batch


def requires_metadata(source_data=None):
    return False


def run(client, config, logger, source_data):
    """
    Fetches tracks from a Deezer album, persisting full album metadata as a side effect.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]

        id_value = source_data[0].get('id')
        is_artist = source_data[0].get('source', None)

        if id_value is None:
            logger.error("Source type 'album' failed: missing 'id' in configuration.")
            return []

        album_ids = id_value if isinstance(id_value, list) else [id_value]
        normalized_album_ids = []
        for raw_album_id in album_ids:
            if raw_album_id is None:
                logger.warning("Album source received null ID in list input. Skipping entry.")
                continue

            album_id = str(raw_album_id).strip()
            if not album_id:
                logger.warning("Album source received empty ID in list input. Skipping entry.")
                continue

            normalized_album_ids.append(album_id)

        if not normalized_album_ids:
            logger.warning("Album source has no valid IDs after filtering invalid list entries.")
            return []

        if not is_artist:
            logger.info(f"Fetching tracks for {len(normalized_album_ids)} album(s)...")

        collected_tracks = fetch_album_metadata_batch(client, logger, normalized_album_ids, ingest_tracks=True)
        if not collected_tracks:
            return []

        if collected_tracks:
            sample_ids = [t.get('id') for t in collected_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")
        return collected_tracks

    except Exception as e:
        logger.error(f"Critical failure in album source: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []