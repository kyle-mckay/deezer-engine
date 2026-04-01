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

## Quick check
If it would still make sense without network/API access, it likely does not belong here.
