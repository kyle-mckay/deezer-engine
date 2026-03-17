# Database Migrations

This project uses a baseline-first migration model.

## Source of Truth

The `migrations/` directory is the only source of truth for database schema.

- Do not create or alter business tables in Python runtime code.
- `utils/database.py` only opens connections and runs migrations.

## Baseline Strategy

- `V001__Initial_schema.sql` is the current baseline schema.
- Fresh databases are created by applying baseline + any later incremental migrations.
- Periodically, maintainers may replace the migration chain with a new baseline as a breaking change while in active development.

## Incremental Migrations

After the baseline, each schema change must be a new file:

- Filename format: `V{number}__{description}.sql`
- Example: `V002__Add_playlist_sync_state.sql`
- Keep each migration single-purpose and reviewable.

## Breaking Baseline Resets

This project is currently in active development and may reset migration history.

When a baseline reset occurs:

1. A new baseline `V001__*.sql` replaces previous migration files.
2. Existing local databases from prior migration epochs are intentionally unsupported.
3. Users must delete the old database file and let the app recreate it.

`utils/db_migrations.py` enforces this by rejecting databases whose applied migration versions are unknown to the current code.

## Authoring Rules

- Migration SQL must be deterministic.
- Migration execution is strict: any SQL error fails the migration.
- Do not rely on "ignore duplicate" behavior.
- Prefer explicit preconditions in SQL when needed.

## Release Checklist

1. Apply migrations to an empty test database.
2. Verify startup and core workflows.
3. Confirm `schema_version` includes newly applied versions.
4. Update documentation if schema behavior changed.
