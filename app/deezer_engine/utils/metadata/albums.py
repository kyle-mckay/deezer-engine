# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Album metadata helpers."""

import json

from utils.db.cache import mark_fully_populated_albums_as_cached
from utils.db.connection import get_connection
from utils.metadata.artists import flatten_artists, _dedupe_entities


def insert_shallow_album_stubs(album_list, logger=None, skip_fully_populated=False):
	"""Insert shallow album payloads for shallow metadata-collection."""
	if logger:
		logger.debug(
			f"Received {len(album_list) if album_list else 0} albums for shallow insert "
			f"(skip_fully_populated={skip_fully_populated})."
		)

	if not album_list:
		return

	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()
			cursor.execute("PRAGMA table_info(albums)")
			album_table_columns = [row[1] for row in cursor.fetchall()]

			albums_by_id = {}
			for album in album_list:
				album_payload = _coerce_album(album)
				album_id = album_payload.get('id')
				if album_id is None:
					continue
				existing_album = albums_by_id.get(album_id, {})
				merged_album = {**existing_album, **album_payload}
				albums_by_id[album_id] = merged_album

			if albums_by_id:
				album_usable_columns = [
					column for column in album_table_columns
					if column != 'date_cached' and any(column in payload for payload in albums_by_id.values())
				]
				if 'id' in album_usable_columns:
					album_usable_columns = ['id'] + [c for c in album_usable_columns if c != 'id']

				if album_usable_columns:
					album_placeholders = ", ".join(["?"] * len(album_usable_columns))
					album_updates = ",\n						".join(
						[
							f"{column} = COALESCE(albums.{column}, excluded.{column})"
							for column in album_usable_columns
							if column != 'id'
						]
					)
					album_query = f"""
					INSERT INTO albums ({", ".join(album_usable_columns)})
					VALUES ({album_placeholders})
					ON CONFLICT(id) DO UPDATE SET
						{album_updates}
					WHERE COALESCE(albums.date_cached, '') = '';
					"""
					album_rows = [
						tuple(_normalize_field(payload.get(column)) for column in album_usable_columns)
						for payload in albums_by_id.values()
					]
					cursor.executemany(album_query, album_rows)

			if not skip_fully_populated:
				if logger:
					logger.debug("Marking fully populated albums as cached.")
				mark_fully_populated_albums_as_cached(logger=logger, conn=conn)
			elif logger:
				logger.debug("Skipping album cache finalization (deferred).")

			conn.commit()
			if logger:
				logger.debug(f"Shallow album insert complete: albums={len(albums_by_id)}")
	except Exception as e:
		if logger:
			logger.error(f"DB Error: Shallow album insert failed: {e}")
		raise


def _normalize_field(value):
	if isinstance(value, (list, dict)):
		return json.dumps(value)
	return value


def _coerce_album(album):
	if hasattr(album, "as_dict"):
		return album.as_dict()
	if isinstance(album, dict):
		return dict(album)
	return dict(album)





def flatten_albums(albumlist, logger, skip_fully_populated=False, artistlist=None):
	"""Flatten album payloads into dictionaries suitable for database writes."""
	if albumlist is None:
		logger.debug("Flattening 0 albums.")
		return []

	albums = albumlist if isinstance(albumlist, list) else [albumlist]
	albums = _dedupe_entities(albums, _coerce_album, logger=logger, entity_label="albums")
	logger.debug(f"Flattening {len(albums)} albums (skip_fully_populated={skip_fully_populated}).")

	flattened_albums = []
	if artistlist:
		logger.debug(f"Received {len(artistlist)} artists for passthrough alongside tracks.")
		artists = artistlist if isinstance(artistlist, list) else [artistlist]
	else:
		artists = []

	for album in albums:
		try:
			flattened = dict(album) if isinstance(album, dict) else _coerce_album(album)
			flattened.pop("playlist", None)
			artist = flattened.pop("artist", None)
			if isinstance(artist, dict):
				artists.append(artist)
				flattened["artist_id"] = flattened.get("artist_id", artist.get("id"))
				flattened["artist_name"] = flattened.get("artist_name", artist.get("name"))

			genres = flattened.get("genres")
			if isinstance(genres, dict) and "data" in genres:
				flattened["genres"] = genres["data"]

			contributors = flattened.get("contributors")
			if isinstance(contributors, dict) and "data" in contributors:
				flattened["contributors"] = contributors["data"]

			flattened_albums.append({key: _normalize_field(value) for key, value in flattened.items()})
		except Exception as exc:
			logger.error(f"Error flattening album with data {album}: {exc}")
			raise

	logger.debug(
		f"Flattened albums. Start count: {len(albums)}, end count: {len(flattened_albums)}."
	)

	flatten_artists(artists, logger, skip_fully_populated=skip_fully_populated)
	insert_shallow_album_stubs(
		flattened_albums,
		logger,
		skip_fully_populated=skip_fully_populated,
	)
	return flattened_albums


def update_album_metadata(album_list, logger=None):
	"""
	Update albums with full metadata payload fetched from Deezer.
	"""
	if logger:
		logger.debug(f"Received {len(album_list) if album_list else 0} albums for metadata update")

	if not album_list:
		if logger:
			logger.debug("Album list is empty, returning early.")
		return

	query = """
	UPDATE albums SET
		title = ?, upc = ?, link = ?, share = ?, cover = ?, cover_small = ?,
		cover_medium = ?, cover_big = ?, cover_xl = ?, md5_image = ?,
		label = ?, nb_tracks = ?, duration = ?, fans = ?, release_date = ?,
		record_type = ?, available = ?, tracklist = ?, explicit_lyrics = ?,
		explicit_content_lyrics = ?, explicit_content_cover = ?, genres = ?, contributors = ?,
		artist_id = ?, artist_name = ?, date_cached = ?
	WHERE id = ?;
	"""

	data_tuples = [
		(
			album.get("title"),
			album.get("upc"),
			album.get("link"),
			album.get("share"),
			album.get("cover"),
			album.get("cover_small"),
			album.get("cover_medium"),
			album.get("cover_big"),
			album.get("cover_xl"),
			album.get("md5_image"),
			album.get("label"),
			album.get("nb_tracks"),
			album.get("duration"),
			album.get("fans"),
			album.get("release_date"),
			album.get("record_type"),
			album.get("available"),
			album.get("tracklist"),
			album.get("explicit_lyrics"),
			album.get("explicit_content_lyrics"),
			album.get("explicit_content_cover"),
			album.get("genres"),
			album.get("contributors"),
			album.get("artist_id"),
			album.get("artist_name"),
			album.get("date_cached"),
			album.get("id"),
		)
		for album in album_list
	]

	if logger and data_tuples:
		sample_album = album_list[0]
		logger.debug(
			f"Sample album data structure: id={sample_album.get('id')} "
			f"(type: {type(sample_album.get('id')).__name__}), title={sample_album.get('title')}, "
			f"date_cached={sample_album.get('date_cached')}"
		)
		logger.debug(
			f"Sample data tuple (last 3 fields): artist_name={data_tuples[0][-3]}, "
			f"date_cached={data_tuples[0][-2]}, id={data_tuples[0][-1]}"
		)

	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()

			artist_ids = sorted({album.get("artist_id") for album in album_list if album.get("artist_id") is not None})
			if artist_ids:
				cursor.executemany(
					"INSERT OR IGNORE INTO artists (id) VALUES (?)",
					[(artist_id,) for artist_id in artist_ids],
				)
				if logger:
					logger.debug(f"Upserted {len(artist_ids)} artist stubs from album metadata payload.")

			if logger:
				logger.debug(f"Executing UPDATE query for {len(data_tuples)} albums...")
			cursor.executemany(query, data_tuples)
			rows_affected = cursor.rowcount
			if logger:
				logger.debug(f"UPDATE query affected {rows_affected} rows.")
			conn.commit()
			if logger:
				logger.debug(f"Metadata enrichment complete for {len(album_list)} albums.")
	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Album metadata update failed: {exc}")
			logger.exception("Stack trace for album metadata update error:")
		raise


def update_albums_partial_batch(album_list, logger=None):
	"""
	Update albums with refreshable fields only (fans, available, date_cached).
	"""
	if not album_list:
		return

	if logger:
		logger.debug(f"Refreshing partial album stats for album_count={len(album_list)}.")

	query = """
	UPDATE albums SET
		fans = ?, available = ?, date_cached = ?
	WHERE id = ?
	"""

	data_tuples = [
		(
			album.get("fans"),
			album.get("available"),
			album.get("date_cached"),
			album.get("id"),
		)
		for album in album_list
	]

	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()
			cursor.executemany(query, data_tuples)
			conn.commit()
			if logger:
				logger.info(f"Refreshed stats (fans/available) for {len(album_list)} albums.")
	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Partial album batch update failed: {exc}")
		raise