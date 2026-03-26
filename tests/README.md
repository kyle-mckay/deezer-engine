# Test Suite Reference

This folder contains developer-facing pytest modules for smoke, integration, and behavior checks.

## Run Tests Locally

From the repository root:

```bash
pytest -v
```

Run a focused module:

```bash
pytest tests/test_main_entrypoint.py
pytest tests/test_input_output_offline.py
...
```

## Test Modules

- `test_deezer_client.py`
  - Purpose: performs basic API accessibility checks against publicly available Deezer assets.
  - Notes: validates core entity fetches (`track`, `album`, `artist`, `playlist`) and expected field presence.
  - Environment: network/API-dependent.

- `test_main_entrypoint.py`
  - Purpose: basic bootstrap validation to ensure expected "fresh install" behavior.
  - Notes: executes `deezer-engine.py run` with minimal temp config/strategies and verifies startup banner plus expected missing-auth/config signals.

- `test_input_output_offline.py`
  - Purpose: deterministic integration/contract validation of I/O assertions.
  - Notes: consumes `templates/validation/input_output/strategies.offline.yml` and fixtures in `tests/fixtures/album`.
  - Behavior: validates expected pass/warn/error counts from runtime logs.

- `test_logger_configuration.py`
  - Purpose: logger configuration behavior validation.
  - Notes: verifies logger handler reconciliation when re-initializing logger settings.

## Fixtures

- `tests/fixtures/album/`
  - Static album payloads used by offline validation tests.

## Forgejo Actions That Run Pytest

Pytest is run in Forgejo CI by:

- `.forgejo/workflows/docker-publish.yml`
  - Step: `Run Pytest in Source`
  - Step: `Run Pytest in Container`
