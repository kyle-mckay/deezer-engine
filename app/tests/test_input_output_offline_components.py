import pytest

from tests.input_output_offline_support import COMPONENT_COUNT_CASES, OFFLINE_SHARED_CACHE_KEY, preserve_runtime_state, run_input_output_once


pytestmark = [pytest.mark.integration, pytest.mark.offline, pytest.mark.slow]


@pytest.mark.parametrize("count_key,label,expected", COMPONENT_COUNT_CASES)
def test_input_output_offline_component_counts(monkeypatch, preserve_runtime_state, run_engine_main, count_key, label, expected):
    """Verifies each source/modifier/destination component logs the expected number of I/O validation passes."""
    del label
    result = run_input_output_once(
        monkeypatch,
        preserve_runtime_state,
        run_engine_main,
        cache_key=OFFLINE_SHARED_CACHE_KEY,
    )
    actual = result["counts"][count_key]

    assert actual == expected, (
        f"Offline component count for '{count_key}' mismatch: expected {expected}, got {actual}"
    )
