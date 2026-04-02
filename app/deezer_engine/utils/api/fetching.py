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


def _get_artist(client, entity_id, logger):
    logger.debug(f"Fetching artist with ID {entity_id}")
    return client.get_artist(entity_id)


def get_artist_albums(client, entity_id, logger):
    logger.debug(f"Fetching albums for artist with ID {entity_id}")
    return client.get_artist(entity_id).get_albums()


def _get_album(client, entity_id, logger):
    logger.debug(f"Fetching album with ID {entity_id}")
    return client.get_album(entity_id)


def _get_album_tracks(client, entity_id, logger):
    logger.debug(f"Fetching tracks for album with ID {entity_id}")
    return client.get_album(entity_id).get_tracks()


def _get_artist_albums(client, entity_id, logger):
    logger.debug(f"Fetching artist with ID {entity_id}")
    return client.get_artist(entity_id).get_albums()


def _get_playlist_tracks(client, entity_id, logger):
    logger.debug(f"Fetching playlist with ID {entity_id}")
    playlist = client.get_playlist(entity_id)
    logger.debug(f"Playlist '{playlist.title}' is accessible publicly. Returning tracks.")
    return playlist.get_tracks()


def _get_favorites(client, logger):
    logger.debug("Fetching user's favorite tracks.")
    uid = get_global_value("user_id")
    if not uid:
        logger.error("User ID is not set in global config. Cannot fetch favorites.")
        raise ValueError("User ID is required to fetch favorites.")

    return client.get_user(uid).get_tracks()


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


def get_tracks(client, logger, source_type, identifier, cache_file=None, track_ids=None):
    """Transforms Deezer API objects into a list of dictionaries with rate-limiting protection."""
    from utils.collections import sync_to_collections
    from utils.db.blocklist import mark_track_metadata_fetch_failed
    from utils.metadata.tracks import flatten_tracks, update_track_metadata, update_tracks_partial_batch

    logger.debug(f"Getting tracks for type '{source_type}' with ID '{identifier}'")

    display_name = identifier
    item_id = identifier

    if isinstance(identifier, str) and (identifier.startswith("playlist__") or identifier.startswith("album__")):
        parts = identifier.split("__")
        if len(parts) >= 3:
            item_type = parts[0]
            display_name = parts[1].replace("_", " ")
            item_id = parts[2]
            logger.debug(f"Parsed {item_type} identifier: Name='{display_name}', ID='{item_id}'")

    tracks = []
    iterable = track_ids if track_ids is not None else client

    date_time = datetime.now().isoformat()
    if source_type == "favorites":
        collection = source_type
    elif source_type != "database":
        collection = f"{item_type}__{item_id}"

    chunk_size = get_global_value("chunk_size", 50)
    cached_tracks = []

    total_len = len(iterable) if hasattr(iterable, "__len__") else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value("log_interval", 120)

    rate_limit = get_global_value("rate_limit", 60)
    api_batch_size = get_global_value("api_batch_size", 50)

    def persist_tracks_for_cooldown(phase_label):
        nonlocal tracks, cached_tracks
        if not tracks:
            return

        if source_type == "database":
            if identifier == "tracks":
                cached_tracks, tracks = persist_track_metadata_raw_batch(
                    tracks,
                    cached_tracks,
                    logger,
                    phase_label,
                    flatten_tracks,
                    update_track_metadata,
                    date_time,
                )
            elif identifier == "stats":
                cached_tracks, tracks = _persist_stats_batch(
                    tracks,
                    cached_tracks,
                    logger,
                    phase_label,
                    update_tracks_partial_batch,
                    "track",
                )
            return

        pending_count = len(tracks)
        cached_tracks.extend(tracks)
        tracks = []
        logger.debug(
            f"{phase_label}: Syncing cumulative source snapshot of {len(cached_tracks)} tracks "
            f"({pending_count} newly fetched) for collection '{collection}'."
        )
        sync_to_collections(cached_tracks, logger, collection_name=collection)

    def flush_pending_tracks_on_shutdown():
        nonlocal tracks
        if source_type == "database" and identifier == "tracks":
            persist_tracks_for_cooldown("Shutdown Flush")
            return

        tracks = _flush_pending_database_batches_on_shutdown(
            tracks,
            logger,
            "track",
            should_flush_metadata=False,
            should_flush_stats=(source_type == "database" and identifier == "stats"),
            update_metadata_batch=None,
            update_stats_batch=update_tracks_partial_batch,
        )

    start_time = time.time()
    api_request_count = 0

    for i, track in enumerate(iterable, 1):
        try:
            if shutdown_event.is_set():
                flush_pending_tracks_on_shutdown()
                logger.debug("Shutdown acknowledged mid-track collection. Returning partial results.")
                if source_type == "database":
                    return []
                return cached_tracks + tracks

            log_prefix = f"Database '{identifier}'" if source_type == "database" else f"'{source_type}'"
            last_log_time = log_enrichment_progress(
                logger,
                log_prefix,
                i,
                total_len,
                last_log_time,
                start_log_time,
                log_interval,
            )

            if source_type == "database" and (identifier == "tracks" or identifier == "stats"):
                if identifier == "tracks":
                    prefetched_required_keys = (
                        "title",
                        "isrc",
                        "track_token",
                        "artist",
                        "album",
                        "artist_id",
                        "album_id",
                    )
                else:
                    prefetched_required_keys = (
                        "readable",
                        "unseen",
                        "rank",
                        "bpm",
                        "gain",
                        "available_countries",
                        "contributors",
                    )

                d, t_id = _extract_prefetched_payload(track, prefetched_required_keys)
                used_prefetched_payload = d is not None

                if not t_id:
                    logger.debug(f"Track payload missing id at index {i}. Skipping.")
                    continue

                did_api_fetch = False
                if not used_prefetched_payload:
                    did_api_fetch = True
                    api_request_count += 1

                    track_obj = fetch_with_retry(
                        client.get_track,
                        t_id,
                        "track",
                        logger,
                        mark_failed_fetch=mark_track_metadata_fetch_failed,
                    )
                    if not track_obj:
                        continue

                    d = track_obj.as_dict()
                else:
                    logger.debug(f"Using prefetched track payload for track {t_id}; skipping per-track API fetch.")

                if identifier == "tracks":
                    tracks.append(d)
                else:
                    tracks.append(
                        {
                            "id": str(d.get("id") if d.get("id") is not None else t_id),
                            "readable": d.get("readable"),
                            "unseen": d.get("unseen", False),
                            "rank": d.get("rank", 0),
                            "bpm": d.get("bpm", 0),
                            "gain": d.get("gain", 0),
                            "available_countries": _normalize_json_field(d.get("available_countries", [])),
                            "contributors": _normalize_json_field(d.get("contributors", [])),
                            "date_cached": date_time,
                        }
                    )
            else:
                if isinstance(track, dict):
                    track_id = track.get("id")
                elif hasattr(track, "id"):
                    track_id = track.id
                else:
                    track_id = track.as_dict().get("id")

                if track_id is None:
                    logger.debug(f"Source track payload missing id at index {i}. Skipping.")
                    continue

                tracks.append({"id": str(track_id), "collection": collection, "date_cached": date_time})

            logger.debug(f"Processed track {track}: {i}/{total_len}")

            if source_type == "database" and identifier == "tracks" and i % chunk_size == 0:
                cached_tracks, tracks = persist_track_metadata_raw_batch(
                    tracks,
                    cached_tracks,
                    logger,
                    "Database Checkpoint",
                    flatten_tracks,
                    update_track_metadata,
                    date_time,
                )

            if source_type == "database" and identifier in ("tracks", "stats"):
                start_time, cooldown_interrupted = _apply_rate_limit_post_fetch(
                    logger,
                    did_api_fetch,
                    start_time,
                    api_request_count,
                    api_batch_size,
                    rate_limit,
                    "requests",
                    flush_on_interrupt=flush_pending_tracks_on_shutdown,
                    interrupted_message="Shutdown acknowledged during track cooldown. Returning partial results.",
                    log_no_cooldown=True,
                    cooldown_task=lambda: persist_tracks_for_cooldown("Cooldown Checkpoint"),
                )
                if cooldown_interrupted:
                    if source_type == "database":
                        return []
                    return tracks

        except Exception as e:
            logger.debug(f"Non-critical loop error at index {i} (Track {track}): {e}")
            time.sleep(1)
            continue

    if source_type == "database" and identifier == "tracks" and tracks:
        cached_tracks, tracks = persist_track_metadata_raw_batch(
            tracks,
            cached_tracks,
            logger,
            "Database Cleanup",
            flatten_tracks,
            update_track_metadata,
            date_time,
        )
        tracks = cached_tracks
    elif source_type == "database" and identifier == "tracks":
        tracks = cached_tracks

    if source_type == "database" and identifier == "stats" and cached_tracks:
        tracks = cached_tracks + tracks

    if source_type != "database" and cached_tracks:
        tracks = cached_tracks + tracks

    logger.debug(f"Successfully transformed {len(tracks)} tracks.")
    return tracks


def get_albums(client, logger, identifier, album_ids=None):
    """Fetches album metadata from Deezer API with rate-limiting protection."""
    from utils.db.blocklist import mark_album_metadata_fetch_failed
    from utils.metadata.albums import update_album_metadata, update_albums_partial_batch
    from utils.metadata.genres import populate_album_genres

    albums = []
    cached_albums = []
    date_time = datetime.now().isoformat()
    chunk_size = get_global_value("chunk_size", 50)

    if not album_ids:
        logger.warning("No album IDs provided for enrichment.")
        return albums

    rate_limit = get_global_value("rate_limit", 60)
    api_batch_size = get_global_value("api_batch_size", 50)

    total_albums = len(album_ids) if hasattr(album_ids, "__len__") else "unknown"
    start_log_time = time.time()
    last_log_time = start_log_time
    log_interval = get_global_value("log_interval", 120)

    def persist_albums_for_cooldown(phase_label):
        nonlocal albums, cached_albums
        if not albums:
            return

        if identifier == "database":
            cached_albums, albums = persist_album_batch(
                albums,
                cached_albums,
                logger,
                phase_label,
                update_album_metadata,
                populate_album_genres,
            )
            return

        if identifier == "stats":
            cached_albums, albums = _persist_stats_batch(
                albums,
                cached_albums,
                logger,
                phase_label,
                update_albums_partial_batch,
                "album",
            )

    def flush_pending_albums_on_shutdown():
        nonlocal albums
        albums = _flush_pending_database_batches_on_shutdown(
            albums,
            logger,
            "album",
            should_flush_metadata=(identifier == "database"),
            should_flush_stats=(identifier == "stats"),
            update_metadata_batch=update_album_metadata,
            update_stats_batch=update_albums_partial_batch,
        )

    start_time = time.time()
    api_request_count = 0

    try:
        for i, album_ref in enumerate(album_ids, 1):
            try:
                if shutdown_event.is_set():
                    flush_pending_albums_on_shutdown()
                    logger.debug("Shutdown acknowledged mid-album collection. Returning partial results.")
                    if identifier in ("database", "stats"):
                        return []
                    return cached_albums + albums

                last_log_time = log_enrichment_progress(
                    logger,
                    f"Album '{identifier}'",
                    i,
                    total_albums,
                    last_log_time,
                    start_log_time,
                    log_interval,
                )

                if identifier == "database":
                    prefetched_required_keys = (
                        "title",
                        "upc",
                        "cover",
                        "genres",
                        "artist",
                        "artist_id",
                    )
                else:
                    prefetched_required_keys = ("fans", "available")

                d, requested_album_id = _extract_prefetched_payload(album_ref, prefetched_required_keys)
                used_prefetched_payload = d is not None

                if not requested_album_id:
                    logger.debug(f"Album payload missing id at index {i}. Skipping.")
                    continue

                did_api_fetch = False
                if not used_prefetched_payload:
                    did_api_fetch = True
                    api_request_count += 1

                    album_obj = fetch_with_retry(
                        client.get_album,
                        requested_album_id,
                        "album",
                        logger,
                        mark_failed_fetch=mark_album_metadata_fetch_failed,
                    )
                    if not album_obj:
                        continue

                    d = album_obj.as_dict()
                else:
                    logger.debug(
                        f"Using prefetched album payload for album {requested_album_id}; skipping per-album API fetch."
                    )

                if not used_prefetched_payload and d.get("id") != requested_album_id:
                    logger.debug(
                        f"API redirect: Requested album {requested_album_id}, but API returned {d.get('id')}. Using requested ID to match database stub."
                    )

                artist_blob = d.get("artist") if isinstance(d.get("artist"), dict) else {}
                artist_id = d.get("artist_id") if d.get("artist_id") is not None else artist_blob.get("id")
                artist_name = d.get("artist_name") if d.get("artist_name") is not None else artist_blob.get("name")

                if identifier == "database":
                    albums.append(
                        {
                            "id": requested_album_id,
                            "title": d.get("title"),
                            "upc": d.get("upc"),
                            "link": d.get("link"),
                            "share": d.get("share"),
                            "cover": d.get("cover"),
                            "cover_small": d.get("cover_small"),
                            "cover_medium": d.get("cover_medium"),
                            "cover_big": d.get("cover_big"),
                            "cover_xl": d.get("cover_xl"),
                            "md5_image": d.get("md5_image"),
                            "label": d.get("label"),
                            "nb_tracks": d.get("nb_tracks"),
                            "duration": d.get("duration", 0),
                            "fans": d.get("fans", 0),
                            "release_date": d.get("release_date"),
                            "record_type": d.get("record_type"),
                            "available": d.get("available", True),
                            "tracklist": d.get("tracklist"),
                            "explicit_lyrics": d.get("explicit_lyrics", False),
                            "explicit_content_lyrics": d.get("explicit_content_lyrics", 0),
                            "explicit_content_cover": d.get("explicit_content_cover", 0),
                            "contributors": _normalize_json_field(d.get("contributors", [])),
                            "genres": _normalize_json_field(d.get("genres", [])),
                            "artist_id": artist_id,
                            "artist_name": artist_name,
                            "date_cached": date_time,
                        }
                    )
                else:
                    albums.append(
                        {
                            "id": requested_album_id,
                            "fans": d.get("fans", 0),
                            "available": d.get("available", True),
                            "date_cached": date_time,
                        }
                    )

                logger.debug(f"Processed album {requested_album_id}: {i}/{total_albums}")

                if identifier == "database" and i % chunk_size == 0:
                    cached_albums, albums = persist_album_batch(
                        albums,
                        cached_albums,
                        logger,
                        "Database Checkpoint",
                        update_album_metadata,
                        populate_album_genres,
                    )
                    if shutdown_event.is_set():
                        flush_pending_albums_on_shutdown()
                        return []

                start_time, cooldown_interrupted = _apply_rate_limit_post_fetch(
                    logger,
                    did_api_fetch,
                    start_time,
                    api_request_count,
                    api_batch_size,
                    rate_limit,
                    "album requests",
                    flush_on_interrupt=flush_pending_albums_on_shutdown,
                    interrupted_message="Shutdown acknowledged during album cooldown. Returning partial results.",
                    cooldown_task=lambda: persist_albums_for_cooldown("Cooldown Checkpoint"),
                )
                if cooldown_interrupted:
                    if identifier in ("database", "stats"):
                        return []
                    return albums

            except Exception as e:
                logger.debug(f"Non-critical loop error at index {i} (Album {album_ref}): {e}")
                time.sleep(1)
                continue

        if identifier == "database" and albums:
            cached_albums, albums = persist_album_batch(
                albums,
                cached_albums,
                logger,
                "Database Cleanup",
                update_album_metadata,
                populate_album_genres,
            )
            albums = cached_albums
        elif identifier == "database":
            albums = cached_albums

        if identifier == "stats" and cached_albums:
            albums = cached_albums + albums

        logger.debug(f"Successfully transformed {len(albums)} albums.")

    except Exception as e:
        logger.error(f"Critical error in get_albums: {e}")
        raise

    return albums
