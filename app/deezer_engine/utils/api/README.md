# utils/api

Use this folder for functions that talk to Deezer or API-adjacent network concerns.

## Put a module here when
- It performs HTTP/client calls to external services.
- It handles auth/session/token behavior.
- It implements retry/backoff/rate-limit logic for API calls.
- It orchestrates API fetch batches before handing data to metadata/db layers.

## Do not put it here when
- It runs SQL queries or updates local persistence (`utils/db`).
- It transforms/stores entity metadata in SQLite (`utils/metadata`, `utils/db`).
- It is generic app infrastructure (paths/logging/files/signals in `utils/infrastructure`).

## Modules

- **auth.py** — Session bootstrap (`get_authenticated_client`, `get_authenticated_session`), JWT lifecycle (`get_or_refresh_pipe_jwt`).
- **playlist.py** — Shared playlist operations: `fetch_playlist_info`, `fetch_playlist_track_ids` (both work for private playlists via gw-light), and standalone write hooks `set_playlist_privacy`, `rename_playlist`, `set_playlist_description` (use pipe.deezer.com GraphQL with the Bearer JWT).
- **fetching.py** — Batched metadata fetch orchestration for tracks and albums.
- **rate_limit.py** — API rate-limit checkpoint logic.
- **retry.py** — Retry/backoff and error-classification helpers.

## Quick check
If it would still make sense without network/API access, it likely does not belong here.
