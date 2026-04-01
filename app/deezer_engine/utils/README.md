# utils module map

Use this page as the first stop when deciding where a new helper or module belongs.

## Folder index

- [api](api/README.md): External API client behavior (auth, fetch, retry, rate-limit).
- [collections](collections/README.md): Collection naming and cache orchestration semantics.
- [config](config/README.md): Config loading, env override handling, and validation.
- [db](db/README.md): SQL persistence, migrations, integrity, and DB lifecycle.
- [infrastructure](infrastructure/README.md): Cross-cutting runtime utilities (logger, paths, files, signals, updates).
- [metadata](metadata/README.md): Entity metadata flattening, enrichment, and metadata-specific safeguards.
- [blocklist](blocklist/README.md): Reserved domain guidance for standalone blocklist policy modules.

## 10-second decision rule

1. Is it primarily SQL/query/write logic? Use [db](db/README.md).
2. Is it primarily external API/network behavior? Use [api](api/README.md).
3. Is it metadata meaning/enrichment flow for tracks/albums/artists/genres? Use [metadata](metadata/README.md).
4. Is it collection semantics or cache orchestration flow? Use [collections](collections/README.md).
5. Is it startup/config parsing/validation? Use [config](config/README.md).
6. Is it generic runtime utility reusable across domains? Use [infrastructure](infrastructure/README.md).

If a function appears to fit multiple folders, choose the folder matching its primary reason to change.
