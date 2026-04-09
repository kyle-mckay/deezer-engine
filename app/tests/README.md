# Test Suite Reference

This folder contains developer-facing pytest modules grouped by scope markers.

## Run Tests Locally

From the repository root:

```bash
# Use the shared source runner (CLI-based pytest wrapper)
./scripts/test.sh

# Fast local profile
TEST_MARKERS="unit or offline" ./scripts/test.sh

# Source-only network tests
TEST_MARKERS="network" ./scripts/test.sh

# Container-safe profile (matches PR container run)
TEST_MARKERS="unit or offline" ./scripts/test.sh
```

**Note:** All local, source-CI, and container test runs use `python -m deezer_engine pytest ...` as the unified execution path. This ensures consistent argument handling and path normalization across all environments. Marker filtering is intentionally different between PR (fast: `unit or offline`), release/manual (broader: `not network`), and source (full suite: no filter).

Run a focused module:

```bash
# From repo root, invoke the test runner with a specific target:
./scripts/test.sh tests/test_cli.py
./scripts/test.sh tests/test_config_parsing.py
./scripts/test.sh tests/test_main_entrypoint.py
./scripts/test.sh tests/test_input_output_offline_runtime.py
./scripts/test.sh tests/test_input_output_offline_totals.py
./scripts/test.sh tests/test_input_output_offline_components.py

# Pytest node IDs also work (normalized by CLI wrapper):
./scripts/test.sh "tests/test_cli.py::test_default_mode_routes_to_cron_when_schedule_present"
```

## Scope Markers

- `unit`: fast tests with no external dependencies.
- `offline`: deterministic fixture-based integration tests.
- `integration`: runtime behavior tests.
- `subprocess`: integration tests that spawn child processes.
- `network`: tests that require external API/network.
- `slow`: long-running tests.

## Test Modules

- `test_deezer_client.py` (`integration`, `network`, `slow`)
  - Purpose: performs basic API accessibility checks against publicly available Deezer assets.
  - Notes: validates core entity fetches (`track`, `album`, `artist`, `playlist`) and expected field presence.
  - Environment: network/API-dependent.

- `test_main_entrypoint.py` (`integration`, `subprocess`, `slow`)
  - Purpose: basic bootstrap validation to ensure expected "fresh install" behavior.
  - Notes: executes `python -m deezer_engine run` (with `PYTHONPATH=app`) using minimal temp config/strategies and verifies startup banner plus expected missing-auth/config signals.

- `test_cli.py` (`unit`)
  - Purpose: validate CLI mode routing and pytest argument normalization behavior.
  - Notes: verifies default mode resolution (`run` vs `cron`), interruptible cron wait behavior, and path normalization for relative, Docker-style absolute, and node-id pytest targets.

- `test_config_parsing.py` (`unit`)
  - Purpose: verify config/env parsing behavior for startup-related overrides.
  - Notes: covers coercion/precedence for `run_before_cron`, runtime quote normalization, and `DEEZER_SCHEDULE` exposure through global config lookup.

- `test_input_output_offline_runtime.py` (`integration`, `offline`, `slow`)
  - Purpose: validates runtime side effects for the offline fixture pipeline.
  - Notes: checks log file creation and database creation from a deterministic run.

- `test_input_output_offline_totals.py` (`integration`, `offline`, `slow`)
  - Purpose: validates aggregate I/O pass/warn/error totals.

- `test_input_output_offline_components.py` (`integration`, `offline`, `slow`)
  - Purpose: validates per-component I/O counts (source/modifier/destination/save).

## Offline Metadata Pull Toggle

- Offline I/O tests force `DEEZER_PULL_METADATA=false` so they only pull full tracks with sources that do not return the same as the current minimum shallow headers. This is limited to history, smarttracklist and file imports (if the import is not already complete).
- Runtime default remains enabled (`pull_metadata=true`) unless overridden by config/env.

- `test_logger_configuration.py` (`unit`)
  - Purpose: logger configuration behavior validation.
  - Notes: verifies logger handler reconciliation when re-initializing logger settings.

- `test_strategy_validation.py` (`unit`)
  - Purpose: strategy key/shape validation behavior.

- `test_key_validation_contract.py` (`unit`)
  - Purpose: contract checks for allowed keys by type.

- `test_schema_templates.py` (`unit`)
  - Purpose: validation template warning contracts.

## Fixtures

- `app/tests/fixtures/album/`
  - Static album payloads used by offline validation tests.
- `run_subprocess` fixture in `app/tests/conftest.py`
  - Default captures combined stdout/stderr (`proc.stdout`) for backward compatibility.
  - Use `combine_output=False` to assert stdout and stderr separately when warning/error channel checks are required.

## Forgejo Actions That Run Pytest

Pytest is run in Forgejo CI by:

- `.forgejo/workflows/docker-publish.yml`
  - Step: `Run Pytest in Source`: calls `./scripts/test.sh` (full suite, no markers)
  - Step: `Run Pytest in Container`: `docker run ... pytest -v --tb=short -m "unit or offline" app/tests` (PR), or `-m "not network"` (release/manual)
