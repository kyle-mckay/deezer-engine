import pytest

from tests.input_output_offline_support import COMPONENT_COUNT_CASES, ONLINE_SHARED_CACHE_KEY, preserve_runtime_state, run_input_output_once


pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.slow]


@pytest.mark.parametrize("count_key,label,expected", COMPONENT_COUNT_CASES)
def test_input_output_online_component_counts(monkeypatch, preserve_runtime_state, run_engine_main, count_key, label, expected):
    """Verifies per-component IO pass counts with pull_metadata enabled."""
    del label
    result = run_input_output_once(
        monkeypatch,
        preserve_runtime_state,
        run_engine_main,
        cache_key=ONLINE_SHARED_CACHE_KEY,
        pull_metadata_enabled=True,
    )
    actual = result["counts"][count_key]

    assert actual == expected, (
        f"Component count for '{count_key}' mismatch: expected {expected}, got {actual}"
    )
