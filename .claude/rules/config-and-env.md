# Configuration and environment variables

## Reading config at runtime

Use `get_global_value(key, default=None)` from `utils.config` anywhere in the codebase. It checks `DEEZER_<KEY>` environment variables first, then falls back to the value in `data/config.yml`. Never read `os.environ` directly for Deezer settings.

## Environment variable mapping

Every key in the `config:` section of `config.yml` has a corresponding `DEEZER_<KEY>` env var (e.g. `log_level` → `DEEZER_LOG_LEVEL`). Auth can be supplied entirely without a config file via `DEEZER_ARL_TOKEN` + `DEEZER_USER_ID`. Full mapping is in `utils/config/parsing.py` → `ENV_MAPPINGS`.

## Config snapshot

Config is loaded once per process into a thread-safe in-memory snapshot (`_CONFIG_SNAPSHOT`). The snapshot is intentionally frozen — calling `get_global_value` multiple times within a run returns the same value. Tests must call `reset_config_snapshot()` (via the `backup_restore_runtime_files` fixture) between runs to avoid snapshot bleed.

## Data directory

`DEEZER_DATA_DIR` overrides the runtime root (default: `./data/`). The database, logs, cache, and YAML configs all resolve relative to this path via `get_data_dir()` in `utils/infrastructure/paths.py`. Tests use this env var to redirect I/O to a temporary directory.
