import pytest

from tests.input_output_offline_support import EXPECTED_COUNTS, OFFLINE_SHARED_CACHE_KEY, TOTAL_COUNT_KEYS, preserve_runtime_state, run_input_output_once


pytestmark = [pytest.mark.integration, pytest.mark.offline, pytest.mark.slow]


def test_input_output_offline_total_counts(monkeypatch, preserve_runtime_state, run_engine_main):
    """Verifies total IOPASS/IOWARN/WARN/IOERR/ERR counts match expected values for an offline run."""
    result = run_input_output_once(
        monkeypatch,
        preserve_runtime_state,
        run_engine_main,
        cache_key=OFFLINE_SHARED_CACHE_KEY,
    )
    counts = result["counts"]

    for key in TOTAL_COUNT_KEYS:
        expected = EXPECTED_COUNTS[key]
        actual = counts[key]
        assert actual == expected, (
            f"Offline total count for '{key}' mismatch: expected {expected}, got {actual}"
        )
