# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metadata utility package scaffold for incremental refactors."""

from utils.metadata.albums import update_album_metadata, update_albums_partial_batch
from utils.metadata.genres import (
	populate_album_genres,
	populate_track_genres,
	populate_track_genres_for_album,
	reset_album_genres_by_track_ids,
)
from utils.metadata.orchestration import refresh_stats, update_unprocessed
from utils.metadata.queries import (
	get_albums_missing_genres,
	get_expired_album_ids,
	get_expired_track_ids,
	get_tracks_missing_genres,
	get_unprocessed_album_ids,
	get_unprocessed_track_ids,
)
from utils.metadata.sync import (
	get_missing_album_ids,
	get_missing_artist_ids,
	get_unique_album_ids_from_tracks,
	sync_missing_albums_to_table,
	sync_missing_artists_to_table,
)
from utils.metadata.tracks import update_track_metadata, update_tracks_partial_batch

__all__ = [
	"get_albums_missing_genres",
	"get_expired_album_ids",
	"get_expired_track_ids",
	"get_missing_album_ids",
	"get_missing_artist_ids",
	"get_tracks_missing_genres",
	"get_unique_album_ids_from_tracks",
	"get_unprocessed_album_ids",
	"get_unprocessed_track_ids",
	"populate_album_genres",
	"populate_track_genres",
	"populate_track_genres_for_album",
	"refresh_stats",
	"reset_album_genres_by_track_ids",
	"sync_missing_albums_to_table",
	"sync_missing_artists_to_table",
	"update_album_metadata",
	"update_albums_partial_batch",
	"update_track_metadata",
	"update_tracks_partial_batch",
	"update_unprocessed",
]