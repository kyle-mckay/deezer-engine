# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""Metadata safeguard helpers."""

from utils.db.blocklist import (
	get_album_ids_for_unavailable_tracks,
	mark_album_metadata_fetch_failed,
)


def blocklist_albums_for_unavailable_tracks(logger=None):
	"""Safeguard album blocklisting based on track availability metadata."""
	marker_error_code = "available_countries_empty"

	try:
		album_ids = get_album_ids_for_unavailable_tracks(logger)
		if not album_ids:
			if logger:
				logger.debug("No albums require safeguard blocklisting for empty available_countries.")
			return

		created_count = 0
		for album_id in album_ids:
			mark_album_metadata_fetch_failed(album_id, marker_error_code, logger)
			created_count += 1

		if logger:
			logger.debug(
				"Safeguard blocklist applied for unavailable tracks: "
				f"albums_blocklisted={created_count}."
			)
	except Exception as exc:
		if logger:
			logger.error(f"Metadata safeguard failed for unavailable tracks: {exc}")
		raise