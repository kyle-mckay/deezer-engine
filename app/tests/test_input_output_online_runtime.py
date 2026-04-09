import pytest

from tests.input_output_offline_support import ONLINE_SHARED_CACHE_KEY, preserve_runtime_state, run_input_output_once


pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.slow]


def test_input_output_online_runtime_outputs(monkeypatch, preserve_runtime_state, run_engine_main):
    """Confirms runtime side-effects for IO validation with pull_metadata enabled."""
    result = run_input_output_once(
        monkeypatch,
        preserve_runtime_state,
        run_engine_main,
        cache_key=ONLINE_SHARED_CACHE_KEY,
        pull_metadata_enabled=True,
    )

    assert result["log_file_exists"], f"Expected run to write log file: {result['log_file']}"
    assert result["db_exists"], f"Expected test run to create a fresh {result['db_path']}"
