# utils/infrastructure

Use this folder for cross-cutting runtime utilities shared by many domains.

## Put a module here when
- It provides generic app services: logging, paths, signals, file IO, startup update checks.
- It has no Deezer domain ownership and no entity-specific SQL ownership.
- It could be reused by multiple unrelated layers.

## Do not put it here when
- It is business/domain logic for metadata, collections, or blocklist policy.
- It is API-specific networking/auth behavior (`utils/api`).
- It is table/query persistence logic (`utils/db`).

## Quick check
If the same helper would be useful in almost any Python app with minimal changes, this is likely the right folder.
