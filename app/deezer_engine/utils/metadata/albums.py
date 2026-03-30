# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Album metadata helpers."""

import json

from utils.db_manager import insert_shallow_album_stubs
from utils.metadata.artists import flatten_artists


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


def _dedupe_albums(albumlist):
	deduped_albums = []
	seen_album_ids = set()

	for album in albumlist:
		album_payload = _coerce_album(album)
		album_id = album_payload.get("id")
		if album_id is None:
			deduped_albums.append(album_payload)
			continue
		if album_id in seen_album_ids:
			continue
		seen_album_ids.add(album_id)
		deduped_albums.append(album_payload)

	return deduped_albums


def flatten_albums(albumlist, logger):
	"""Flatten album payloads into dictionaries suitable for database writes."""
	if albumlist is None:
		logger.debug("Flattening 0 albums.")
		return []

	albums = albumlist if isinstance(albumlist, list) else [albumlist]
	albums = _dedupe_albums(albums)
	logger.debug(f"Flattening {len(albums)} albums.")

	flattened_albums = []
	artists = []
	for album in albums:
		try:
			flattened = dict(album) if isinstance(album, dict) else _coerce_album(album)
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

	flatten_artists(artists, logger)
	insert_shallow_album_stubs(flattened_albums, logger)
	return flattened_albums