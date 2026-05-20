# Plugin module conventions

Sources, modifiers, and destinations are dynamically loaded by `StrategyController` using `importlib`. Each module lives in:

- `app/deezer_engine/strategies/sources/<type>.py`
- `app/deezer_engine/strategies/modifiers/<type>.py`
- `app/deezer_engine/strategies/destinations/<type>.py`

Every module **must** export:

```python
def run(client, config, logger, *args):
    ...
```

Optionally export to control metadata enrichment:

```python
def requires_metadata(config_data: dict) -> bool:
    ...
```

- Return `False` when the module only needs shallow track fields (id, title, artist, etc.) that come directly from collection/API responses without a DB enrichment pass.
- Return `True` (or omit the function — the default is `True`) when the module needs fields populated by the metadata enrichment pipeline (e.g. `bpm`, `gain`, `release_date` from full album metadata).
- For modifiers that filter/sort by a field, `StrategyController.check_requires_metadata` will cross-check the configured `field` against `track_header_available()` and skip enrichment automatically when the field is already in the shallow payload.

The `type` value in `strategies.yml` must exactly match the module filename (e.g. `type: "shuffle"` → `strategies/modifiers/shuffle.py`).

## Registering a new plugin in the validator

Creating the module file is not enough — every new type must also be registered in `utils/config/key_validation.py`, otherwise the strategy loader emits `[WARNING] Unknown key(s)` for every config key the plugin uses.

Add an entry to the appropriate dict:
- `MODIFIER_TYPE_KEYS` — the set of keys the modifier accepts beyond the base set (`type`, `i`, `o`, `validation_mode`)
- `SOURCE_TYPE_KEYS` — keys beyond the source base set
- `DESTINATION_TYPE_KEYS` — keys beyond the destination base set

```python
# example for a new modifier
MODIFIER_TYPE_KEYS = {
    ...
    'my_modifier': {'field_a', 'field_b'},
}
```

If the plugin has a **nested list of structured entries** (like `interleave`'s `inject` list), also define a constant for those entry-level keys (e.g. `INTERLEAVE_INJECT_ENTRY_KEYS`) and add explicit recursion in `_validate_modifiers` inside `utils/config/strategy_validation.py`. See the `interleave` modifier and its handling there as the reference pattern.

If the plugin just has a single nested `source` key (like `exclude`), no extra validator changes are needed — `_validate_modifiers` already recurses into `source` automatically.

## Fetching sources inside a modifier

Modifiers that need to load their own source data (e.g. `exclude`, `interleave`) should follow this cache-first pattern rather than calling the source worker directly:

```python
collection_name = get_collection_name(logger, source_type, source_name, source_id)

if collection_name != "unknown" and is_collection_cached(collection_name, source_data, logger):
    tracks = fetch_collection(collection_name, logger)
else:
    module = importlib.import_module(f"strategies.sources.{source_type}")
    tracks = module.run(client, config, logger, source_data)
    sync_to_collections(tracks, logger)
```

All four helpers (`get_collection_name`, `is_collection_cached`, `fetch_collection`, `sync_to_collections`) are importable from `utils.collections`.
