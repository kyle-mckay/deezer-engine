# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Genre metadata helpers."""

import json

from utils.db.connection import get_connection
from utils.infrastructure.signals import shutdown_event


def populate_album_genres(album_list, logger=None):
	"""
	Populate genres and album_genres junction entries from album payloads.
	"""
	if logger:
		logger.debug(f"Processing {len(album_list) if album_list else 0} albums for genre population")

	if not album_list:
		if logger:
			logger.debug("Album list is empty, returning early.")
		return

	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()
			processed_album_ids = []
			all_genres = {}
			album_genre_relationships = []

			for album in album_list:
				album_id = album.get("id")
				genres_json = album.get("genres", "[]")

				if not album_id:
					continue

				processed_album_ids.append(album_id)

				try:
					if isinstance(genres_json, str):
						genres = json.loads(genres_json)
					else:
						genres = genres_json if isinstance(genres_json, list) else []
				except json.JSONDecodeError:
					if logger:
						logger.debug(f"Failed to parse genres JSON for album {album_id}: {genres_json}")
					genres = []

				if not genres:
					continue

				for genre_obj in genres:
					if not isinstance(genre_obj, dict):
						continue

					genre_name = genre_obj.get("name")
					deezer_genre_id = genre_obj.get("id")

					if not genre_name or deezer_genre_id is None:
						continue

					try:
						deezer_genre_id = int(deezer_genre_id)
					except (TypeError, ValueError):
						if logger:
							logger.debug(f"Skipping invalid genre id for album {album_id}: {deezer_genre_id}")
						continue

					if genre_name not in all_genres:
						all_genres[genre_name] = deezer_genre_id

					album_genre_relationships.append((album_id, deezer_genre_id))

			if all_genres:
				for genre_name, deezer_genre_id in all_genres.items():
					cursor.execute("SELECT id FROM genres WHERE name = ?", (genre_name,))
					existing_row = cursor.fetchone()

					if existing_row and existing_row[0] != deezer_genre_id:
						old_genre_id = existing_row[0]

						cursor.execute("SELECT name FROM genres WHERE id = ?", (deezer_genre_id,))
						conflicting_target = cursor.fetchone()
						if conflicting_target and conflicting_target[0] != genre_name:
							if logger:
								logger.warning(
									f"Genre ID conflict detected for Deezer genre {deezer_genre_id}: "
									f"existing name '{conflicting_target[0]}', incoming '{genre_name}'. Skipping remap."
								)
							continue

						temp_name = f"{genre_name}__legacy_{old_genre_id}"
						cursor.execute(
							"UPDATE genres SET name = ? WHERE id = ?",
							(temp_name, old_genre_id),
						)
						cursor.execute(
							"INSERT OR IGNORE INTO genres (id, name) VALUES (?, ?)",
							(deezer_genre_id, genre_name),
						)

						cursor.execute(
							"UPDATE OR IGNORE album_genres SET genre_id = ? WHERE genre_id = ?",
							(deezer_genre_id, old_genre_id),
						)
						cursor.execute("DELETE FROM album_genres WHERE genre_id = ?", (old_genre_id,))

						cursor.execute(
							"UPDATE OR IGNORE track_genres SET genre_id = ? WHERE genre_id = ?",
							(deezer_genre_id, old_genre_id),
						)
						cursor.execute("DELETE FROM track_genres WHERE genre_id = ?", (old_genre_id,))

						cursor.execute("DELETE FROM genres WHERE id = ?", (old_genre_id,))

				genre_insert_tuples = [(genre_id, name) for name, genre_id in all_genres.items()]
				if logger:
					logger.debug(f"Inserting {len(genre_insert_tuples)} unique genres into database")

				cursor.executemany(
					"INSERT OR IGNORE INTO genres (id, name) VALUES (?, ?)",
					genre_insert_tuples,
				)

				album_genres_tuples = [(album_id, genre_id) for album_id, genre_id in album_genre_relationships]

				if logger:
					logger.debug(f"Creating {len(album_genres_tuples)} album-genre relationships")

				cursor.executemany(
					"INSERT OR REPLACE INTO album_genres (album_id, genre_id) VALUES (?, ?)",
					album_genres_tuples,
				)
			else:
				if logger:
					logger.debug("No genres found in album data.")
				album_genres_tuples = []

			if processed_album_ids:
				cursor.executemany(
					"UPDATE albums SET genre_mapped = 1 WHERE id = ?",
					[(album_id,) for album_id in set(processed_album_ids)],
				)
				if logger:
					logger.debug(f"Marked {len(set(processed_album_ids))} albums as genre_mapped=1")

			conn.commit()
			if logger:
				logger.debug(
					f"Genre population complete: {len(all_genres)} genres, {len(album_genres_tuples)} relationships"
				)

			enriched_album_ids = set(album_id for album_id, _ in album_genre_relationships)
			if logger:
				logger.debug(f"Retroactively populating track genres for {len(enriched_album_ids)} enriched albums")

			total_enriched_albums = len(enriched_album_ids)
			for album_position, album_id in enumerate(enriched_album_ids, start=1):
				if shutdown_event.is_set():
					if logger:
						logger.debug(
							"Shutdown acknowledged during per-album track-genre backfill. Remaining albums deferred to next run."
						)
					break
				try:
					populate_track_genres_for_album(
						album_id,
						logger,
						album_position=album_position,
						album_total=total_enriched_albums,
					)
				except Exception as album_err:
					if logger:
						logger.warning(f"Failed to populate track genres for album {album_id}: {album_err}")
					continue

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Genre population failed: {exc}")
			logger.exception("Stack trace for genre population error:")
		raise


def populate_track_genres(logger=None):
	"""
	Populate track_genres by inheriting mapped album genres.
	"""
	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()

			cursor.execute(
				"""
				SELECT COUNT(*) FROM tracks
				WHERE COALESCE(genre_mapped, 0) = 0
				  AND album_id IS NOT NULL
				  AND album_id IN (
					  SELECT id FROM albums
					  WHERE COALESCE(genre_mapped, 0) = 1
				  )
				"""
			)
			unmapped_tracks_count = cursor.fetchone()[0]

			if unmapped_tracks_count == 0:
				if logger:
					logger.debug("No unmapped tracks found. Skipping track-genre population.")
				return

			if logger:
				logger.debug(f"Found {unmapped_tracks_count} unmapped tracks to process.")

			insert_query = """
			INSERT OR REPLACE INTO track_genres (track_id, genre_id)
			SELECT DISTINCT t.id, ag.genre_id
			FROM tracks t
			JOIN albums a ON t.album_id = a.id
			JOIN album_genres ag ON a.id = ag.album_id
			WHERE t.album_id IS NOT NULL
			  AND COALESCE(t.genre_mapped, 0) = 0
			  AND COALESCE(a.genre_mapped, 0) = 1
			"""

			if logger:
				logger.debug("Executing track-genre population from album-genre relationships")

			cursor.execute(insert_query)
			rows_affected = cursor.rowcount

			cursor.execute(
				"""
				UPDATE tracks
				SET genre_mapped = 1
				WHERE COALESCE(genre_mapped, 0) = 0
				  AND album_id IS NOT NULL
				  AND album_id IN (
					  SELECT id
					  FROM albums
					  WHERE COALESCE(genre_mapped, 0) = 1
				  )
				"""
			)
			tracks_marked = cursor.rowcount

			conn.commit()

			if logger:
				logger.debug(
					f"Track-genre population complete: {rows_affected} track-genre relationships created, "
					f"{tracks_marked} tracks marked genre_mapped=1"
				)

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Track genre population failed: {exc}")
			logger.exception("Stack trace for track genre population error:")
		raise


def populate_track_genres_for_album(album_id, logger=None, album_position=None, album_total=None):
	"""
	Populate track_genres for a specific album.
	"""
	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()
			progress_suffix = ""
			if album_position is not None and album_total is not None:
				progress_suffix = f" ({album_position}/{album_total})"

			cursor.execute("SELECT COUNT(*) FROM album_genres WHERE album_id = ?", (album_id,))
			genre_count = cursor.fetchone()[0]

			if genre_count == 0:
				cursor.execute("UPDATE tracks SET genre_mapped = 1 WHERE album_id = ?", (album_id,))
				conn.commit()
				if logger:
					logger.debug(
						f"Album {album_id}{progress_suffix} has no genres to populate. "
						"Marked tracks as genre_mapped=1."
					)
				return 0

			insert_query = """
			INSERT OR REPLACE INTO track_genres (track_id, genre_id)
			SELECT DISTINCT t.id, ag.genre_id
			FROM tracks t
			JOIN album_genres ag ON ag.album_id = ?
			WHERE t.album_id = ?
			"""

			cursor.execute(insert_query, (album_id, album_id))
			rows_affected = cursor.rowcount

			cursor.execute("UPDATE tracks SET genre_mapped = 1 WHERE album_id = ?", (album_id,))
			tracks_marked = cursor.rowcount

			conn.commit()

			if logger:
				logger.debug(
					f"Populated {rows_affected} track-genre relationships for album {album_id}{progress_suffix}, "
					f"marked {tracks_marked} tracks as genre_mapped=1"
				)

			return rows_affected

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Failed to populate track genres for album {album_id}: {exc}")
		raise


def reset_album_genres_by_track_ids(track_ids, logger=None):
	"""
	Reset albums.genre_mapped=0 for albums tied to tracks missing genre mappings.
	"""
	if not track_ids:
		if logger:
			logger.debug("No track IDs provided. Skipping album genre reset.")
		return 0

	if logger:
		logger.debug(f"Resetting album genre mappings for tracks_missing_genres_count={len(track_ids)}.")

	try:
		with get_connection(logger) as conn:
			cursor = conn.cursor()

			placeholders = ",".join("?" * len(track_ids))
			query = f"""
			SELECT DISTINCT album_id FROM tracks
			WHERE id IN ({placeholders}) AND album_id IS NOT NULL
			"""
			cursor.execute(query, track_ids)
			album_ids = [row[0] for row in cursor.fetchall()]

			if not album_ids:
				if logger:
					logger.debug("No albums found for tracks missing genres.")
				return 0

			reset_placeholders = ",".join("?" * len(album_ids))
			reset_query = f"UPDATE albums SET genre_mapped = 0 WHERE id IN ({reset_placeholders})"
			cursor.execute(reset_query, album_ids)
			rows_affected = cursor.rowcount

			conn.commit()

			if logger:
				logger.debug(
					f"Reset genre_mapped=0 for {rows_affected} albums associated with {len(track_ids)} tracks missing genres."
				)

			return rows_affected

	except Exception as exc:
		if logger:
			logger.error(f"DB Error: Failed to reset album genres by track IDs: {exc}")
		raise