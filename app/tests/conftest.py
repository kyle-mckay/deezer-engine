from pathlib import Path
import io
import importlib
import shutil
import re
import sys
import subprocess
import os
import warnings
from datetime import datetime
from contextlib import redirect_stdout

import pytest
from utils.config import reset_config_snapshot


# Warn if tests are running without the CLI wrapper.
# This detects whether pytest was invoked via './scripts/test.sh' or 'python -m deezer_engine pytest'
# versus raw 'pytest', which bypasses the shared execution path contract.
if not os.getenv("DEEZER_PYTEST_CLI_WRAPPER"):
    warnings.warn(
        "Tests running without CLI wrapper. "
        "Use './scripts/test.sh' or 'python -m deezer_engine pytest' instead of raw pytest. "
        "This ensures consistent behavior across local, CI source, and container execution.",
        UserWarning,
        stacklevel=2,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

# Keep bare imports (utils.*, strategies.*, __version__) working even when
# pytest is launched from /app and repo-level
ENGINE_PACKAGE_ROOT = REPO_ROOT / "app" / "deezer_engine"
engine_package_root_str = str(ENGINE_PACKAGE_ROOT)
if engine_package_root_str not in sys.path:
    sys.path.insert(0, engine_package_root_str)


class _StdoutTee(io.TextIOBase):
    def __init__(self, *streams):
        self._streams = streams

    def write(self, text):
        for stream in self._streams:
            stream.write(text)
            stream.flush()
        return len(text)

    def flush(self):
        for stream in self._streams:
            stream.flush()

def _sanitize_test_name(test_name):
    sanitized = re.sub(r"[^a-zA-Z0-9._-]+", "_", test_name.strip().lower())
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")
    return sanitized or "unknown_test"


def _build_pytest_log_path(pytest_logs_dir, test_name):
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    safe_test_name = _sanitize_test_name(test_name)
    filename = f"{timestamp}.{safe_test_name}.log"
    candidate = pytest_logs_dir / filename
    suffix = 1

    while candidate.exists():
        candidate = pytest_logs_dir / f"{timestamp}.{safe_test_name}.{suffix}.log"
        suffix += 1

    return candidate


def _runtime_file_paths_for(data_dir):
    return {
        "data_dir": data_dir,
        "config_path": data_dir / "config.yml",
        "strategies_path": data_dir / "strategies.yml",
        "db_path": data_dir / "db" / "deezer_engine.db",
    }


@pytest.fixture
def runtime_file_paths():
    return _runtime_file_paths_for(REPO_ROOT / "data")


@pytest.fixture
def run_engine_main():
    """
    Run deezer_engine entrypoint.main() in-process.

    When capture_stdout=True, stdout is teed to the real terminal and an in-memory
    buffer so tests can assert printed banner text while still showing live output
    under pytest -s.
    """

    def _run(*, capture_stdout=False):
        engine = importlib.import_module("entrypoint")
        if not capture_stdout:
            engine.main()
            return ""

        buffer = io.StringIO()
        tee = _StdoutTee(sys.stdout, buffer)
        with redirect_stdout(tee):
            engine.main()
        return buffer.getvalue()

    return _run


@pytest.fixture
def run_subprocess():
    """
    Universal subprocess wrapper for tests.

    Defaults to capturing combined stdout/stderr as text and returning the
    CompletedProcess so tests can assert output and exit behavior consistently.
    Set combine_output=False to capture stdout and stderr separately.
    """

    def _run(command, *, cwd=None, timeout=300, env=None, check=False, combine_output=True):
        stderr_target = subprocess.STDOUT if combine_output else subprocess.PIPE
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=stderr_target,
            text=True,
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
            env=env,
            check=check,
        )

    return _run


@pytest.fixture
def backup_restore_runtime_files(tmp_path, monkeypatch, request):
    test_name = request.node.name
    runtime_data_dir = tmp_path / "data"
    runtime_paths = _runtime_file_paths_for(runtime_data_dir)
    runtime_logs_dir = runtime_data_dir / "logs"
    pytest_logs_dir = REPO_ROOT / "data" / "logs" / "pytest"
    today_log_stem = datetime.now().strftime('%Y-%m-%d')
    today_log_name = f"{today_log_stem}.log"
    today_log_path = runtime_logs_dir / today_log_name

    runtime_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEEZER_DATA_DIR", str(runtime_data_dir))
    reset_config_snapshot()

    try:
        yield runtime_paths
    finally:
        reset_config_snapshot()

        if today_log_path.exists():
            pytest_logs_dir.mkdir(parents=True, exist_ok=True)
            if today_log_path.stat().st_size == 0:
                today_log_path.unlink()
            else:
                pytest_log_path = _build_pytest_log_path(pytest_logs_dir, test_name)
                shutil.move(str(today_log_path), str(pytest_log_path))
