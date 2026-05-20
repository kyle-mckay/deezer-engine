# Testing rules

Always run tests via the CLI wrapper, never raw `pytest`:

```bash
./scripts/test.sh                              # full suite
TEST_MARKERS="unit or offline" ./scripts/test.sh   # fast, no network
./scripts/test.sh tests/test_foo.py           # single module
```

The wrapper sets `DEEZER_PYTEST_CLI_WRAPPER=1` and normalizes paths. Raw `pytest` will emit a warning and may miss path normalization.

When writing tests:
- Mark every test with at least one of: `unit`, `offline`, `integration`, `subprocess`, `network`, `slow`.
- Tests that touch the DB or filesystem must use the `backup_restore_runtime_files` fixture — it redirects `DEEZER_DATA_DIR` to a `tmp_path` so tests don't pollute `./data/`.
- Offline integration tests should set `DEEZER_PULL_METADATA=false` to avoid live API calls.
- The `run_engine_main` fixture runs `entrypoint.main()` in-process; use `run_subprocess` for tests that need a real child process.
