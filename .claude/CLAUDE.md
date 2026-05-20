# CLAUDE.md

This file provides guidance to AI agents (or developers) when working with code in this repository.

## Commands

### Dev Setup (first time)
```bash
./scripts/setup-dev.sh        # creates .venv, installs deps, seeds data/config.yml and data/strategies.yml
```

### Run the engine
```bash
PYTHONPATH=app python -m deezer_engine          # run once (or cron if DEEZER_SCHEDULE is set)
PYTHONPATH=app python -m deezer_engine run       # explicit single run
PYTHONPATH=app python -m deezer_engine cron      # explicit cron/scheduler mode
```

### Tests
```bash
./scripts/test.sh                                      # full suite
TEST_MARKERS="unit or offline" ./scripts/test.sh       # fast (no network), matches PR CI
TEST_MARKERS="network" ./scripts/test.sh               # network/API tests only

# Run a single module or test (path is normalized by CLI wrapper)
./scripts/test.sh tests/test_cli.py
./scripts/test.sh "tests/test_cli.py::test_default_mode_routes_to_cron_when_schedule_present"
```

**Important:** always use `./scripts/test.sh` (or `python -m deezer_engine pytest ...`) instead of raw `pytest`. The CLI wrapper sets `DEEZER_PYTEST_CLI_WRAPPER=1`, normalizes test paths, and routes through the shared entrypoint contract that both local and CI runs rely on.

### Reset runtime data between runs
```bash
./scripts/reset-data.sh
./scripts/reset-data.sh --run   # reset then run immediately
```

## Architecture

### Pipeline overview

Each strategy in `data/strategies.yml` is executed as a three-phase pipeline:

1. **Sources** — fetch track IDs from Deezer or local files; results are cached in SQLite to avoid redundant API calls
2. **Modifiers** — transform the in-memory track list (filter, sort, dedupe, shuffle, limit, exclude)
3. **Destinations** — push the final list to a Deezer playlist or export to a file

The top-level orchestration lives in `app/deezer_engine/entrypoint.py` (`process_sources`, `process_modifiers`, `process_destinations` → `main()`).

### StrategyController (`strategies/base.py`)

`StrategyController` is the per-strategy runtime object. It:
- Holds the **in-memory pipeline** (`self.pipeline`) — a list of track dicts that modifiers mutate in place
- Dynamically imports source/modifier/destination modules via `importlib.import_module()` using a naming convention (`strategies.sources.<type>`, `strategies.modifiers.<type>`, `strategies.destinations.<type>`)
- Every pluggable module exposes a `run(client, config, logger, *args)` function; sources and modifiers may also expose `requires_metadata(config_data) -> bool` to gate metadata enrichment
- Enforces I/O count validation via `i:` / `o:` keys in the strategy YAML

### Plugin module conventions

To add a new source, modifier, or destination: create a Python file in the corresponding folder and implement `run()`. If full DB metadata is required (not just shallow API fields), implement `requires_metadata(config_data) -> bool`. Returning `False` skips the enrichment pass for that component.

### Configuration & environment

- `data/config.yml` (from `app/config.yml.template`) — authentication and tuning knobs
- `data/strategies.yml` (from `app/strategies.yml.template`) — the pipeline definitions
- All `config.yml` keys can be overridden with `DEEZER_<KEY>` environment variables (e.g. `DEEZER_LOG_LEVEL=DEBUG`). Auth can be supplied entirely via `DEEZER_ARL_TOKEN` + `DEEZER_USER_ID`.
- The config is loaded once per process into a thread-safe snapshot (`utils/config/parsing.py`); use `get_global_value(key)` to read it anywhere.
- `DEEZER_DATA_DIR` overrides the runtime data root (default: `./data/`). The DB, logs, cache, and config files all resolve relative to this directory.

### Database

SQLite at `data/db/deezer_engine.db`. Schema is managed by incremental SQL migrations in `app/migrations/`. The DB layer lives in `utils/db/`; `connection.py` → `get_connection()` is the entry point. Collections (source track lists) are cached in the `collections` table; metadata enrichment is handled via `utils/metadata/orchestration.py`.

### CLI modes

`app/deezer_engine/cli.py` (`__main__.py` delegates here). Valid modes: `run`, `cron`, `pytest`, `shell`, `default`. `default` auto-selects `cron` when `DEEZER_SCHEDULE` is set, otherwise `run`.

### Test markers

| Marker | Meaning |
|---|---|
| `unit` | Mocked, no I/O — fast |
| `offline` | Fixture-based integration tests, deterministic |
| `integration` | Runtime behavior, touches DB/files |
| `subprocess` | Spawns child processes |
| `network` | Requires live Deezer API |
| `slow` | Expected to be slower than unit tests |

Offline I/O tests force `DEEZER_PULL_METADATA=false`; the `backup_restore_runtime_files` fixture in `conftest.py` isolates each test's data dir via `DEEZER_DATA_DIR` + `tmp_path`.
