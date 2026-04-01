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
def _blocklist_where_clause(include_blocklisted):
    from utils.db.blocklist import _blocklist_where_clause as _real_blocklist_where_clause
    return _real_blocklist_where_clause(include_blocklisted)

def release_expired_blocklisted_entities(logger=None):
    """Wrapper for blocklist expiry logic (see utils/db/blocklist.py)."""
    from utils.db.blocklist import release_expired_blocklisted_entities as _real_release_expired
    return _real_release_expired(logger)


def _mark_entity_metadata_fetch_failed(entity_type, entity_table, entity_id, error_code, logger=None):
    from utils.db.blocklist import _mark_entity_metadata_fetch_failed as _real_mark_entity_metadata_fetch_failed
    return _real_mark_entity_metadata_fetch_failed(entity_type, entity_table, entity_id, error_code, logger)

def mark_track_metadata_fetch_failed(track_id, error_code, logger=None):
    from utils.db.blocklist import mark_track_metadata_fetch_failed as _real_mark_track_metadata_fetch_failed
    return _real_mark_track_metadata_fetch_failed(track_id, error_code, logger)

def mark_album_metadata_fetch_failed(album_id, error_code, logger=None):
    from utils.db.blocklist import mark_album_metadata_fetch_failed as _real_mark_album_metadata_fetch_failed
    return _real_mark_album_metadata_fetch_failed(album_id, error_code, logger)

def get_album_ids_for_unavailable_tracks(logger=None):
    from utils.db.blocklist import get_album_ids_for_unavailable_tracks as _real_get_album_ids_for_unavailable_tracks
    return _real_get_album_ids_for_unavailable_tracks(logger)

def blocklist_albums_for_unavailable_tracks(logger=None):
    from utils.db.blocklist import blocklist_albums_for_unavailable_tracks as _real_blocklist_albums_for_unavailable_tracks
    return _real_blocklist_albums_for_unavailable_tracks(logger)

def fetch_collection(source_name, logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.collections.cache_queries.fetch_collection."""
    from utils.collections.cache_queries import fetch_collection as _fetch_collection

    return _fetch_collection(source_name, logger, include_blocklisted)

def validate_sync_integrity(original_tracks, synced_tracks, logger):
    """Compatibility wrapper for utils.collections.sync.validate_sync_integrity."""
    from utils.collections.sync import validate_sync_integrity as _validate_sync_integrity

    return _validate_sync_integrity(original_tracks, synced_tracks, logger)

def sync_to_collections(tracklist, logger, collection_name=None):
    """Compatibility wrapper for utils.collections.sync.sync_to_collections."""
    from utils.collections.sync import sync_to_collections as _sync_to_collections

    return _sync_to_collections(tracklist, logger, collection_name)


def insert_shallow_artist_stubs(artist_list, logger=None):
    """Compatibility wrapper for utils.metadata.artists.insert_shallow_artist_stubs."""
    from utils.metadata.artists import insert_shallow_artist_stubs as _insert_shallow_artist_stubs

    return _insert_shallow_artist_stubs(artist_list, logger)


def insert_shallow_album_stubs(album_list, logger=None):
    """Compatibility wrapper for utils.metadata.albums.insert_shallow_album_stubs."""
    from utils.metadata.albums import insert_shallow_album_stubs as _insert_shallow_album_stubs

    return _insert_shallow_album_stubs(album_list, logger)


def insert_shallow_track_stubs(track_list, logger=None):
    """Compatibility wrapper for utils.metadata.tracks.insert_shallow_track_stubs."""
    from utils.metadata.tracks import insert_shallow_track_stubs as _insert_shallow_track_stubs

    return _insert_shallow_track_stubs(track_list, logger)


def mark_fully_populated_tracks_as_cached(logger=None, cached_at=None):
    """Compatibility wrapper for utils.db.cache.mark_fully_populated_tracks_as_cached."""
    from utils.db.cache import mark_fully_populated_tracks_as_cached as _mark_fully_populated_tracks_as_cached

    return _mark_fully_populated_tracks_as_cached(logger, cached_at)


def mark_fully_populated_albums_as_cached(logger=None, cached_at=None):
    """Compatibility wrapper for utils.db.cache.mark_fully_populated_albums_as_cached."""
    from utils.db.cache import mark_fully_populated_albums_as_cached as _mark_fully_populated_albums_as_cached

    return _mark_fully_populated_albums_as_cached(logger, cached_at)


def mark_fully_populated_artists_as_cached(logger=None, cached_at=None):
    """Compatibility wrapper for utils.db.cache.mark_fully_populated_artists_as_cached."""
    from utils.db.cache import mark_fully_populated_artists_as_cached as _mark_fully_populated_artists_as_cached

    return _mark_fully_populated_artists_as_cached(logger, cached_at)


def is_collection_cached(source_name, config, logger=None):
    """Compatibility wrapper for utils.collections.cache_queries.is_collection_cached."""
    from utils.collections.cache_queries import is_collection_cached as _is_collection_cached

    return _is_collection_cached(source_name, config, logger)


def get_unprocessed_track_ids(logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.metadata.queries.get_unprocessed_track_ids."""
    from utils.metadata.queries import get_unprocessed_track_ids as _get_unprocessed_track_ids

    return _get_unprocessed_track_ids(logger, include_blocklisted)


def get_unprocessed_album_ids(logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.metadata.queries.get_unprocessed_album_ids."""
    from utils.metadata.queries import get_unprocessed_album_ids as _get_unprocessed_album_ids

    return _get_unprocessed_album_ids(logger, include_blocklisted)


def get_expired_track_ids(logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.metadata.queries.get_expired_track_ids."""
    from utils.metadata.queries import get_expired_track_ids as _get_expired_track_ids

    return _get_expired_track_ids(logger, include_blocklisted)


def get_expired_album_ids(logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.metadata.queries.get_expired_album_ids."""
    from utils.metadata.queries import get_expired_album_ids as _get_expired_album_ids

    return _get_expired_album_ids(logger, include_blocklisted)


def get_albums_missing_genres(logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.metadata.queries.get_albums_missing_genres."""
    from utils.metadata.queries import get_albums_missing_genres as _get_albums_missing_genres

    return _get_albums_missing_genres(logger, include_blocklisted)


def get_tracks_missing_genres(logger=None, include_blocklisted=False):
    """Compatibility wrapper for utils.metadata.queries.get_tracks_missing_genres."""
    from utils.metadata.queries import get_tracks_missing_genres as _get_tracks_missing_genres

    return _get_tracks_missing_genres(logger, include_blocklisted)


def get_unique_album_ids_from_tracks(logger=None):
    """Compatibility wrapper for utils.metadata.sync.get_unique_album_ids_from_tracks."""
    from utils.metadata.sync import get_unique_album_ids_from_tracks as _get_unique_album_ids_from_tracks

    return _get_unique_album_ids_from_tracks(logger)


def get_missing_album_ids(logger=None):
    """Compatibility wrapper for utils.metadata.sync.get_missing_album_ids."""
    from utils.metadata.sync import get_missing_album_ids as _get_missing_album_ids

    return _get_missing_album_ids(logger)


def get_missing_artist_ids(logger=None):
    """Compatibility wrapper for utils.metadata.sync.get_missing_artist_ids."""
    from utils.metadata.sync import get_missing_artist_ids as _get_missing_artist_ids

    return _get_missing_artist_ids(logger)


def sync_missing_albums_to_table(logger=None):
    """Compatibility wrapper for utils.metadata.sync.sync_missing_albums_to_table."""
    from utils.metadata.sync import sync_missing_albums_to_table as _sync_missing_albums_to_table

    return _sync_missing_albums_to_table(logger)


def sync_missing_artists_to_table(logger=None):
    """Compatibility wrapper for utils.metadata.sync.sync_missing_artists_to_table."""
    from utils.metadata.sync import sync_missing_artists_to_table as _sync_missing_artists_to_table

    return _sync_missing_artists_to_table(logger)


def reset_album_genres_by_track_ids(track_ids, logger=None):
    """Compatibility wrapper for utils.metadata.genres.reset_album_genres_by_track_ids."""
    from utils.metadata.genres import reset_album_genres_by_track_ids as _reset_album_genres_by_track_ids

    return _reset_album_genres_by_track_ids(track_ids, logger)


def update_track_metadata(track_list, logger=None):
    """Compatibility wrapper for utils.metadata.tracks.update_track_metadata."""
    from utils.metadata.tracks import update_track_metadata as _update_track_metadata

    return _update_track_metadata(track_list, logger)


def update_tracks_partial_batch(track_list, logger=None):
    """Compatibility wrapper for utils.metadata.tracks.update_tracks_partial_batch."""
    from utils.metadata.tracks import update_tracks_partial_batch as _update_tracks_partial_batch

    return _update_tracks_partial_batch(track_list, logger)


def update_album_metadata(album_list, logger=None):
    """Compatibility wrapper for utils.metadata.albums.update_album_metadata."""
    from utils.metadata.albums import update_album_metadata as _update_album_metadata

    return _update_album_metadata(album_list, logger)


def update_albums_partial_batch(album_list, logger=None):
    """Compatibility wrapper for utils.metadata.albums.update_albums_partial_batch."""
    from utils.metadata.albums import update_albums_partial_batch as _update_albums_partial_batch

    return _update_albums_partial_batch(album_list, logger)


def populate_album_genres(album_list, logger=None):
    """Compatibility wrapper for utils.metadata.genres.populate_album_genres."""
    from utils.metadata.genres import populate_album_genres as _populate_album_genres

    return _populate_album_genres(album_list, logger)


def populate_track_genres(logger=None):
    """Compatibility wrapper for utils.metadata.genres.populate_track_genres."""
    from utils.metadata.genres import populate_track_genres as _populate_track_genres

    return _populate_track_genres(logger)


def populate_track_genres_for_album(album_id, logger=None, album_position=None, album_total=None):
    """Compatibility wrapper for utils.metadata.genres.populate_track_genres_for_album."""
    from utils.metadata.genres import populate_track_genres_for_album as _populate_track_genres_for_album

    return _populate_track_genres_for_album(album_id, logger, album_position, album_total)


def update_unprocessed(client, logger):
    """Compatibility wrapper for utils.metadata.orchestration.update_unprocessed."""
    from utils.metadata.orchestration import update_unprocessed as _update_unprocessed

    return _update_unprocessed(client, logger)


def refresh_stats(client, logger):
    """Compatibility wrapper for utils.metadata.orchestration.refresh_stats."""
    from utils.metadata.orchestration import refresh_stats as _refresh_stats

    return _refresh_stats(client, logger)

def fetch_entities_by(table_name, column_name, operator, values, return_ids_only=False, logger=None):
    """Compatibility wrapper for utils.db.fetch.fetch_entities_by."""
    from utils.db.fetch import fetch_entities_by as _fetch_entities_by

    return _fetch_entities_by(table_name, column_name, operator, values, return_ids_only, logger)