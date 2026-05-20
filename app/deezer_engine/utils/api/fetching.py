# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""API fetch orchestration helpers."""

import json
import time
from datetime import datetime

from utils.api.rate_limit import apply_rate_limit_checkpoint
from utils.api.retry import fetch_with_retry, log_enrichment_progress
from utils.config import get_global_value
from utils.infrastructure.signals import shutdown_event


def get_artist_albums(client, entity_id, logger):
    logger.debug(f"Fetching albums for artist with ID {entity_id}")
    return client.get_artist(entity_id).get_albums()


def fetch_shallow_tracks(paginated_tracks, logger):
    """Consume a paginated track source and return flattened shallow metadata rows."""
    from utils.metadata.tracks import ingest_shallow_tracks

    raw_tracks = list(paginated_tracks) if paginated_tracks is not None else []
    logger.debug(f"Fetched {len(raw_tracks)} raw paginated tracks for shallow processing.")
    return ingest_shallow_tracks(raw_tracks, logger, skip_fully_populated=True)


def _is_json_string(value):
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    return (stripped.startswith("[") and stripped.endswith("]")) or (
        stripped.startswith("{") and stripped.endswith("}")
    )


def _normalize_json_field(value):
    if value is None:
        return json.dumps([])
    if _is_json_string(value):
        return value
    return json.dumps(value)


def _extract_prefetched_payload(item, required_payload_keys):
    """Returns (payload_dict_or_none, item_id)."""
    if hasattr(item, "as_dict"):
        payload = item.as_dict()
        return payload, payload.get("id")

    if isinstance(item, dict):
        item_id = item.get("id")
        if item_id is None:
            return None, None

        has_payload = any(key in item for key in required_payload_keys)
        if has_payload:
            return item, item_id

        return None, item_id

    return None, item


def persist_track_batch(tracks, cached_tracks, logger, phase_label, update_track_metadata):
    """Persist a track batch and reset the working list."""
    if not tracks:
        return cached_tracks, tracks

    if phase_label == "Database Checkpoint":
        logger.debug(f"{phase_label}: Pushing chunk of {len(tracks)} tracks to database")
    else:
        logger.debug(f"{phase_label}: Saving remaining {len(tracks)} tracks...")

    update_track_metadata(tracks, logger)
    cached_tracks.extend(tracks)
    return cached_tracks, []


def _prepare_track_metadata_rows(flattened_tracks, date_time):
    """Shape flattened track payloads into full metadata rows for DB updates."""
    metadata_rows = []
    for track in flattened_tracks:
        metadata_rows.append(
            {
                "id": str(track.get("id")) if track.get("id") is not None else None,
                "readable": track.get("readable"),
                "title": track.get("title"),
                "title_short": track.get("title_short"),
                "title_version": track.get("title_version"),
                "unseen": track.get("unseen", False),
                "isrc": track.get("isrc"),
                "link": track.get("link"),
                "share": track.get("share"),
                "duration": track.get("duration", 0),
                "track_position": track.get("track_position"),
                "disk_number": track.get("disk_number"),
                "rank": track.get("rank", 0),
                "release_date": track.get("release_date"),
                "explicit_lyrics": track.get("explicit_lyrics", False),
                "explicit_content_lyrics": track.get("explicit_content_lyrics", 0),
                "explicit_content_cover": track.get("explicit_content_cover", 0),
                "preview": track.get("preview"),
                "bpm": track.get("bpm", 0),
                "gain": track.get("gain", 0),
                "available_countries": _normalize_json_field(track.get("available_countries", [])),
                "contributors": _normalize_json_field(track.get("contributors", [])),
                "md5_image": track.get("md5_image"),
                "track_token": track.get("track_token"),
                "artist_id": track.get("artist_id"),
                "album_id": track.get("album_id"),
                "date_cached": date_time,
            }
        )
    return [row for row in metadata_rows if row.get("id") is not None]


def persist_track_metadata_raw_batch(
    raw_tracks,
    cached_tracks,
    logger,
    phase_label,
    flatten_tracks,
    update_track_metadata,
    date_time,
):
    """Flatten raw track payloads at checkpoint and persist metadata in batch."""
    if not raw_tracks:
        return cached_tracks, raw_tracks

    if phase_label == "Database Checkpoint":
        logger.debug(
            f"{phase_label}: Flattening and persisting chunk of {len(raw_tracks)} raw track payloads"
        )
    else:
        logger.debug(
            f"{phase_label}: Flattening and persisting remaining {len(raw_tracks)} raw track payloads"
        )

    flattened_tracks = flatten_tracks(raw_tracks, logger)
    metadata_rows = _prepare_track_metadata_rows(flattened_tracks, date_time)
    update_track_metadata(metadata_rows, logger)
    cached_tracks.extend(metadata_rows)
    return cached_tracks, []


def persist_album_batch(
    albums,
    cached_albums,
    logger,
    phase_label,
    update_album_metadata,
    populate_album_genres,
):
    """Persist an album batch, populate genres, and reset the working list."""
    if not albums:
        return cached_albums, albums

    if phase_label == "Database Checkpoint":
        logger.debug(f"{phase_label}: Pushing chunk of {len(albums)} albums to database")
        logger.debug(f"Album IDs in checkpoint: {[album.get('id') for album in albums]}")
    else:
        logger.debug(f"{phase_label}: Saving remaining {len(albums)} albums...")
        logger.debug(f"Album IDs to save: {[album.get('id') for album in albums]}")

    try:
        update_album_metadata(albums, logger)
        populate_album_genres(albums, logger)
        logger.debug(
            f"{phase_label}: update_album_metadata and populate_album_genres completed successfully."
        )
    except Exception as batch_err:
        logger.error(
            f"{phase_label}: update_album_metadata or populate_album_genres raised exception: {batch_err}"
        )
        logger.exception("Stack trace for batch persistence error:")
        raise

    cached_albums.extend(albums)
    return cached_albums, []


def _persist_stats_batch(items, cached_items, logger, phase_label, update_partial_batch, entity_label):
    if not items:
        return cached_items, items

    logger.debug(f"{phase_label}: Pushing chunk of {len(items)} {entity_label} stats to database")
    update_partial_batch(items, logger)
    cached_items.extend(items)
    return cached_items, []


def _flush_pending_database_batches_on_shutdown(
    items,
    logger,
    entity_label,
    should_flush_metadata,
    should_flush_stats,
    update_metadata_batch=None,
    update_stats_batch=None,
):
    """Persist pending metadata or stats payloads when shutdown is acknowledged."""
    if not items:
        return items

    if should_flush_metadata and update_metadata_batch is not None:
        logger.debug(f"Shutdown Flush: Persisting {len(items)} pending {entity_label} metadata rows.")
        update_metadata_batch(items, logger)
        return []

    if should_flush_stats and update_stats_batch is not None:
        logger.debug(f"Shutdown Flush: Persisting {len(items)} pending {entity_label} stats rows.")
        update_stats_batch(items, logger)
        return []

    return items


def _apply_rate_limit_post_fetch(
    logger,
    did_api_fetch,
    start_time,
    api_request_count,
    api_batch_size,
    rate_limit,
    request_label,
    flush_on_interrupt,
    interrupted_message,
    log_no_cooldown=False,
    cooldown_task=None,
):
    if not did_api_fetch:
        return start_time, False

    start_time, cooldown_interrupted = apply_rate_limit_checkpoint(
        logger,
        start_time,
        api_request_count,
        api_batch_size,
        rate_limit,
        request_label,
        log_no_cooldown=log_no_cooldown,
        cooldown_task=cooldown_task,
    )
    if cooldown_interrupted:
        flush_on_interrupt()
        logger.debug(interrupted_message)
        return start_time, True

    return start_time, False


def fetch_track_metadata_batch(client, logger, track_ids):
    """Fetch full track metadata for a list of IDs and persist to DB with rate-limiting protection."""
    from utils.db.blocklist import mark_track_metadata_fetch_failed
    from utils.metadata.tracks import flatten_tracks, update_track_metadata

    tracks = []
    date_time = datetime.now().isoformat()
    chunk_size = get_global_value("chunk_size", 50)
    cached_tracks = []

    total_len = len(track_ids) if hasattr(track_ids, "__len__") else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value("log_interval", 120)
    rate_limit = get_global_value("rate_limit", 60)
    api_batch_size = get_global_value("api_batch_size", 50)
    prefetched_required_keys = ("title", "isrc", "track_token", "artist", "album", "artist_id", "album_id")

    def persist_batch(phase_label):
        nonlocal tracks, cached_tracks
        if not tracks:
            return
        cached_tracks, tracks = persist_track_metadata_raw_batch(
            tracks, cached_tracks, logger, phase_label, flatten_tracks, update_track_metadata, date_time,
        )

    start_time = time.time()
    api_request_count = 0

    for i, track in enumerate(track_ids, 1):
        try:
            if shutdown_event.is_set():
                persist_batch("Shutdown Flush")
                logger.debug("Shutdown acknowledged mid-track enrichment. Returning partial results.")
                return []

            last_log_time = log_enrichment_progress(
                logger, "Database 'tracks'", i, total_len, last_log_time, start_log_time, log_interval,
            )

            d, t_id = _extract_prefetched_payload(track, prefetched_required_keys)
            if not t_id:
                logger.debug(f"Track payload missing id at index {i}. Skipping.")
                continue

            did_api_fetch = False
            if d is None:
                did_api_fetch = True
                api_request_count += 1
                track_obj = fetch_with_retry(
                    client.get_track, t_id, "track", logger, mark_failed_fetch=mark_track_metadata_fetch_failed,
                )
                if not track_obj:
                    continue
                d = track_obj.as_dict()
            else:
                logger.debug(f"Using prefetched track payload for track {t_id}; skipping per-track API fetch.")

            tracks.append(d)
            logger.debug(f"Processed track {track}: {i}/{total_len}")

            if i % chunk_size == 0:
                persist_batch("Database Checkpoint")

            start_time, cooldown_interrupted = _apply_rate_limit_post_fetch(
                logger,
                did_api_fetch,
                start_time,
                api_request_count,
                api_batch_size,
                rate_limit,
                "requests",
                flush_on_interrupt=lambda: persist_batch("Shutdown Flush"),
                interrupted_message="Shutdown acknowledged during track cooldown. Returning partial results.",
                log_no_cooldown=True,
                cooldown_task=lambda: persist_batch("Cooldown Checkpoint"),
            )
            if cooldown_interrupted:
                return []

        except Exception as e:
            logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
            time.sleep(1)
            continue

    if tracks:
        persist_batch("Database Cleanup")

    logger.debug(f"Successfully enriched {len(cached_tracks)} tracks.")
    return cached_tracks


def fetch_album_metadata_batch(client, logger, album_ids, ingest_tracks=False):
    """Fetch full album metadata for a list of IDs and persist to DB.

    When ingest_tracks=True (album/artist sources): shallow-ingests embedded tracks before
    persisting album metadata so genre mapping fires against already-present track rows.
    Returns ingested track dicts with collection field set.

    When ingest_tracks=False (enrichment cycle): skips track ingestion to avoid injecting
    sibling tracks that were never part of a user source. Returns empty list.
    """
    from utils.db.blocklist import mark_album_metadata_fetch_failed
    from utils.metadata.albums import flatten_albums, update_album_metadata
    from utils.metadata.genres import populate_album_genres
    if ingest_tracks:
        from utils.metadata.tracks import ingest_shallow_tracks

    album_dicts = []
    batch_tracks = []
    all_ingested = []
    date_time = datetime.now().isoformat()
    chunk_size = get_global_value("chunk_size", 50)

    if not album_ids:
        logger.warning("No album IDs provided for enrichment.")
        return all_ingested

    rate_limit = get_global_value("rate_limit", 60)
    api_batch_size = get_global_value("api_batch_size", 50)
    total_albums = len(album_ids) if hasattr(album_ids, "__len__") else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value("log_interval", 120)
    api_request_count = 0

    def persist_batch(phase_label):
        nonlocal album_dicts, batch_tracks, all_ingested
        if not album_dicts:
            return
        if phase_label == "Database Checkpoint":
            logger.debug(f"{phase_label}: Persisting chunk of {len(album_dicts)} albums.")
        else:
            logger.debug(f"{phase_label}: Persisting remaining {len(album_dicts)} albums.")
        # Ingest tracks first so populate_album_genres finds them in the DB.
        if ingest_tracks and batch_tracks:
            ingested = ingest_shallow_tracks(batch_tracks, logger, skip_fully_populated=True)
            all_ingested.extend(ingested)
            batch_tracks = []
        # flatten_albums normalizes artist/genres/contributors and inserts stubs for new rows.
        # update_album_metadata force-updates all fields, covering both new rows and stale refreshes
        # where insert_shallow_album_stubs's COALESCE guard would otherwise skip existing records.
        flattened = flatten_albums(album_dicts, logger, skip_fully_populated=True)
        update_album_metadata(flattened, logger)
        populate_album_genres(flattened, logger)
        album_dicts = []

    start_time = time.time()

    for i, album_id in enumerate(album_ids, 1):
        try:
            if shutdown_event.is_set():
                persist_batch("Shutdown Flush")
                logger.debug("Shutdown acknowledged mid-album enrichment. Returning partial results.")
                return all_ingested

            last_log_time = log_enrichment_progress(
                logger, "Album metadata", i, total_albums, last_log_time, start_log_time, log_interval,
            )

            album_obj = fetch_with_retry(
                client.get_album, album_id, "album", logger,
                mark_failed_fetch=mark_album_metadata_fetch_failed,
            )
            if not album_obj:
                continue

            api_request_count += 1
            d = album_obj.as_dict()
            tracks_blob = d.pop("tracks", []) or []
            d["date_cached"] = date_time

            if d.get("id") != album_id:
                logger.debug(
                    f"API redirect: Requested album {album_id}, but API returned {d.get('id')}. Using requested ID."
                )
                d["id"] = album_id

            album_dicts.append(d)

            if ingest_tracks:
                collection = f"album__{album_id}"
                for track in tracks_blob:
                    if isinstance(track, dict):
                        track["collection"] = collection
                batch_tracks.extend(tracks_blob)

            logger.debug(f"Processed album {album_id}: {i}/{total_albums}")

            if i % chunk_size == 0:
                persist_batch("Database Checkpoint")

            start_time, cooldown_interrupted = _apply_rate_limit_post_fetch(
                logger, True, start_time, api_request_count, api_batch_size, rate_limit,
                "album requests",
                flush_on_interrupt=lambda: persist_batch("Shutdown Flush"),
                interrupted_message="Shutdown acknowledged during album cooldown. Returning partial results.",
                cooldown_task=lambda: persist_batch("Cooldown Checkpoint"),
            )
            if cooldown_interrupted:
                return all_ingested

        except Exception as e:
            logger.debug(f"Non-critical loop error at index {i} (Album {album_id}): {e}")
            time.sleep(1)
            continue

    if album_dicts:
        persist_batch("Database Cleanup")

    logger.debug(f"Returning {len(all_ingested)} ingested tracks from {total_albums} albums.")
    return all_ingested
