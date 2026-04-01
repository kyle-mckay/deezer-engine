# utils/db

Use this folder for SQLite lifecycle, queries, writes, migrations, and DB integrity.

## Put a module here when
- It opens/manages DB connections.
- It executes SQL reads/writes against app tables.
- It handles migration/index/integrity/backup behavior.
- It provides persistence helpers used by higher-level domains.

## Do not put it here when
- It is API networking/auth/retry logic (`utils/api`).
- It is domain orchestration without SQL ownership (`utils/metadata`, `utils/collections`).
- It is generic infra (paths/logger/files/signals in `utils/infrastructure`).

## Quick check
If removing SQL would remove the function's purpose, it belongs in `utils/db`.
