# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metadata orchestration helpers."""

from utils.api.fetching import get_albums, get_tracks
from utils.infrastructure.signals import shutdown_event
from utils.metadata.albums import update_album_metadata, update_albums_partial_batch
from utils.metadata.genres import (
    populate_track_genres,
    reset_album_genres_by_track_ids,
)
from utils.metadata.queries import (
    get_albums_missing_genres,
    get_expired_album_ids,
    get_expired_track_ids,
    get_tracks_missing_genres,
    get_unprocessed_album_ids,
    get_unprocessed_track_ids,
)
from utils.metadata.sync import sync_missing_albums_to_table, sync_missing_artists_to_table
from utils.metadata.tracks import update_track_metadata, update_tracks_partial_batch

def add_key_to_dicts(logger, dicts, key, value):
    """Adds or overwrites a key-value pair to a list of dictionaries."""
    if not isinstance(dicts, list):
        logger.error(f"Expected a list of dictionaries, got {type(dicts)}. Skipping addition of key '{key}': {value}.")
        return dicts
    else:
        logger.debug(f"Adding key '{key}': {value} to {len(dicts)} records.")
        
    for d in dicts:
        if isinstance(d, dict):
            d[key] = value
        else:
            logger.warning(f"Expected dictionary in list, got {type(d)}. Skipping entry.")

    return dicts

def update_unprocessed(client, logger):
    """Identify and process tracks/albums that need metadata and genre mapping."""
    unprocessed = get_unprocessed_track_ids(logger)
    if unprocessed:
        logger.info(f"Fetching metadata for {len(unprocessed)} new tracks...")
        unprocessed = get_tracks(client, logger, "database", "tracks", "null", unprocessed)
        logger.debug(f"Metadata fetched, updating database with {len(unprocessed)} records.")
        update_track_metadata(unprocessed, logger)

    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after track enrichment. Deferring album enrichment to next run.")
        return

    unprocessed = get_unprocessed_track_ids(logger)
    if unprocessed:
        logger.warning(
            f"Metadata enrichment finished but tracks are missing metadata. Expecting 0, got {len(unprocessed)}"
        )

    sync_missing_albums_to_table(logger)
    sync_missing_artists_to_table(logger)
    unprocessed_album = get_unprocessed_album_ids(logger)

    if unprocessed_album:
        logger.info(f"Fetching metadata for {len(unprocessed_album)} new albums...")
        unprocessed_album = get_albums(client, logger, identifier="database", album_ids=unprocessed_album)
        logger.debug(f"Metadata fetched, updating database with {len(unprocessed_album)} records.")
        update_album_metadata(unprocessed_album, logger)

    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after album enrichment. Deferring genre mapping to next run.")
        return

    unprocessed_album = get_unprocessed_album_ids(logger)
    if unprocessed_album:
        logger.warning(
            f"Metadata enrichment finished but albums are missing metadata. Expecting 0, got {len(unprocessed_album)}"
        )

    if shutdown_event.is_set():
        if logger:
            logger.debug(
                "Shutdown acknowledged after album-genre mapping. Deferring track-genre mapping to next run."
            )
        return

    logger.debug("Populating track genres from album relationships...")
    try:
        populate_track_genres(logger)
    except Exception as exc:
        logger.error(f"Failed to populate track genres: {exc}")

    if shutdown_event.is_set():
        if logger:
            logger.debug("Shutdown acknowledged after track-genre mapping. Deferring diagnostics to next run.")
        return

    albums_missing_genres = get_albums_missing_genres(logger)
    if albums_missing_genres:
        if logger:
            logger.debug(f"Albums missing genre mappings (IDs: {albums_missing_genres})")
        logger.warning(
            f"Found {len(albums_missing_genres)} albums without genre mapping. "
            "These will be reprocessed on the next cycle."
        )

    tracks_missing_genres = get_tracks_missing_genres(logger)
    if tracks_missing_genres:
        if logger:
            logger.debug(f"Tracks missing genre mappings (IDs: {tracks_missing_genres})")
        logger.warning(
            f"Found {len(tracks_missing_genres)} tracks missing genre mappings. "
            "Associated albums will be reset and reprocessed on the next cycle."
        )
        reset_album_genres_by_track_ids(tracks_missing_genres, logger)


def refresh_stats(client, logger):
    """Refresh stale track/album stats based on configured cache age thresholds."""
    refresh_track_ids = get_expired_track_ids(logger)
    if refresh_track_ids:
        logger.info(f"Refreshing stats for {len(refresh_track_ids)} existing tracks...")
        refresh_tracks = get_tracks(client, logger, "database", "stats", "null", refresh_track_ids)
        logger.debug("Stats fetched, updating database.")
        update_tracks_partial_batch(refresh_tracks)

    expired_albums = get_expired_album_ids(logger)
    if expired_albums:
        logger.info(f"Refreshing stats for {len(expired_albums)} existing albums...")
        album_stats = get_albums(client, logger, identifier="stats", album_ids=expired_albums)
        logger.debug("Album stats fetched, updating database.")
        if album_stats:
            update_albums_partial_batch(album_stats, logger)
