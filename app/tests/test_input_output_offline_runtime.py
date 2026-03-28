import pytest

from tests.input_output_offline_support import print_log_once, preserve_runtime_state, run_input_output_once


pytestmark = [pytest.mark.integration, pytest.mark.offline, pytest.mark.slow]

MODULE_CACHE_KEY = "offline-runtime"


def test_input_output_offline_runtime_outputs(monkeypatch, preserve_runtime_state, run_engine_main):
    """Confirms the engine writes a log file and creates a database on an offline run."""
    result = run_input_output_once(
        monkeypatch,
        preserve_runtime_state,
        run_engine_main,
        cache_key=MODULE_CACHE_KEY,
    )

    print_log_once(result)
    assert result["log_file_exists"], f"Expected run to write log file: {result['log_file']}"
    assert result["db_exists"], f"Expected test run to create a fresh {result['db_path']}"
