import sys

import pytest


pytestmark = [pytest.mark.unit]


def test_run_subprocess_combines_stdout_and_stderr_by_default(run_subprocess):
    """Ensures default fixture behavior preserves combined output contract."""
    proc = run_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('from-stdout'); print('from-stderr', file=sys.stderr)",
        ]
    )

    assert proc.returncode == 0
    assert "from-stdout" in proc.stdout
    assert "from-stderr" in proc.stdout
    assert proc.stderr is None


def test_run_subprocess_can_capture_streams_separately(run_subprocess):
    """Verifies optional split capture mode exposes stdout and stderr independently."""
    proc = run_subprocess(
        [
            sys.executable,
            "-c",
            "import sys; print('stdout-only'); print('stderr-only', file=sys.stderr)",
        ],
        combine_output=False,
    )

    assert proc.returncode == 0
    assert "stdout-only" in proc.stdout
    assert "stderr-only" in proc.stderr
