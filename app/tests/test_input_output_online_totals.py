import pytest

from tests.input_output_offline_support import EXPECTED_COUNTS, ONLINE_SHARED_CACHE_KEY, TOTAL_COUNT_KEYS, preserve_runtime_state, run_input_output_once


pytestmark = [pytest.mark.integration, pytest.mark.network, pytest.mark.slow]


def test_input_output_online_total_counts(monkeypatch, preserve_runtime_state, run_engine_main):
    """Verifies aggregate IO totals with pull_metadata enabled."""
    result = run_input_output_once(
        monkeypatch,
        preserve_runtime_state,
        run_engine_main,
        cache_key=ONLINE_SHARED_CACHE_KEY,
        pull_metadata_enabled=True,
    )
    counts = result["counts"]

    for key in TOTAL_COUNT_KEYS:
        expected = EXPECTED_COUNTS[key]
        actual = counts[key]
        assert actual == expected, (
            f"Online total count for '{key}' mismatch: expected {expected}, got {actual}"
        )
