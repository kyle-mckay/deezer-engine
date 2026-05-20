# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""API utility package exports."""

from .auth import get_authenticated_client, get_authenticated_session
from .fetching import fetch_album_metadata_batch, fetch_track_metadata_batch, get_artist_albums, persist_album_batch, persist_track_batch
from .rate_limit import apply_rate_limit_checkpoint, cooldown_wait_with_tasks
from .retry import (
	NON_BLOCKLIST_ERROR_CODES,
	NON_BLOCKLIST_ERROR_PATTERNS,
	extract_error_code,
	fetch_with_retry,
	log_enrichment_progress,
	should_blocklist_failed_fetch,
)

__all__ = [
	"NON_BLOCKLIST_ERROR_CODES",
	"NON_BLOCKLIST_ERROR_PATTERNS",
	"apply_rate_limit_checkpoint",
	"cooldown_wait_with_tasks",
	"extract_error_code",
	"fetch_album_metadata_batch",
	"fetch_track_metadata_batch",
	"fetch_with_retry",
	"get_artist_albums",
	"get_authenticated_client",
	"get_authenticated_session",
	"log_enrichment_progress",
	"persist_album_batch",
	"persist_track_batch",
	"should_blocklist_failed_fetch",
]