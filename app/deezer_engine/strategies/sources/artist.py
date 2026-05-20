# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

from utils.api.fetching import fetch_album_metadata_batch
from utils.collections import get_collection_name, sync_to_collections
from utils.config import get_global_value
from utils.infrastructure.signals import shutdown_event
from utils.metadata.orchestration import add_key_to_dicts


def requires_metadata(source_data=None):
    return False


def run(client, config, logger, source_data):
    """
    Fetches tracks from a Deezer artist by batching all album IDs through fetch_album_metadata_batch.
    """
    try:
        if isinstance(source_data, dict):
            source_data = [source_data]

        id_value = source_data[0].get('id')

        if id_value is None:
            logger.error("Source type 'artist' failed: missing 'id' in configuration.")
            return []

        artist_ids = id_value if isinstance(id_value, list) else [id_value]
        normalized_artist_ids = []
        for raw_artist_id in artist_ids:
            if raw_artist_id is None:
                logger.warning("Artist source received null ID in list input. Skipping entry.")
                continue

            artist_id = str(raw_artist_id).strip()
            if not artist_id:
                logger.warning("Artist source received empty ID in list input. Skipping entry.")
                continue

            normalized_artist_ids.append(artist_id)

        if not normalized_artist_ids:
            logger.warning("Artist source has no valid IDs after filtering invalid list entries.")
            return []

        artist_tracks = []
        for artist_id in normalized_artist_ids:
            if shutdown_event.is_set():
                logger.debug("Shutdown acknowledged before next artist lookup. Skipping remaining artists.")
                break

            try:
                artist = client.get_artist(artist_id)
                albums = artist.get_albums()
                album_ids = [str(album_obj.id) for album_obj in albums]
                logger.debug(f"Artist: '{artist.name}' | Total albums found: {len(album_ids)}")
            except Exception as e:
                logger.error(f"Failed to retrieve artist metadata for {artist_id}: {e}")
                logger.debug("Stack trace:", exc_info=True)
                continue

            if not album_ids:
                logger.warning(f"Artist '{artist.name}' (ID {artist_id}) returned no albums.")
                continue

            logger.info(f"Fetching tracks for artist '{artist.name}' ({len(album_ids)} albums)...")

            ingested = fetch_album_metadata_batch(client, logger, album_ids, ingest_tracks=True)
            if not ingested:
                logger.warning(f"Artist '{artist.name}' returned no tracks after album fetch.")
                continue

            # Sync each track to its per-album collection using the collection field set by the batch hook
            sync_to_collections(ingested, logger)

            # Override collection to artist for pipeline output
            collection_artist = get_collection_name(logger, "artist", id=artist_id)
            artist_tracks.extend(add_key_to_dicts(logger, ingested, 'collection', collection_artist))

            logger.debug(f"Aggregated {len(ingested)} tracks from artist '{artist.name}'.")

        if not artist_tracks:
            logger.warning("Artist source returned no tracks after processing all valid IDs.")
            return []

        if artist_tracks:
            sample_ids = [t.get('id') for t in artist_tracks[:5]]
            logger.debug(f"Sample Track IDs from source: {sample_ids}")

        return artist_tracks

    except Exception as e:
        logger.error(f"Artist aggregation failed: {e}")
        logger.debug("Stack trace:", exc_info=True)
        return []