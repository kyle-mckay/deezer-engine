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

"""Backward-compatible re-exports for legacy utils.deezer_auth imports."""

from utils.api.auth import get_authenticated_client, get_authenticated_session
from utils.api.retry import (
    NON_BLOCKLIST_ERROR_CODES,
    NON_BLOCKLIST_ERROR_PATTERNS,
    extract_error_code,
    should_blocklist_failed_fetch,
    log_enrichment_progress,
    fetch_with_retry,
)
from utils.api.rate_limit import apply_rate_limit_checkpoint, cooldown_wait_with_tasks
from utils.api.fetching import get_tracks, get_albums, persist_track_batch, persist_album_batch
