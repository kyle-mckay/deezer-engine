import threading
import sys
from datetime import datetime
import pytest

import cli
from scheduler import CronScheduler


pytestmark = [pytest.mark.unit]


def test_default_mode_routes_to_cron_when_schedule_present(monkeypatch):
    """Routes default CLI mode to cron when DEEZER_SCHEDULE is set."""
    calls = []

    monkeypatch.setenv("DEEZER_SCHEDULE", '"0 3 * * *"')
    monkeypatch.setattr(cli, "ensure_runtime_files", lambda mode: 0)
    monkeypatch.setattr(cli, "run_cron_mode", lambda: calls.append("cron") or 0)
    monkeypatch.setattr(cli, "run_once", lambda: calls.append("run") or 0)

    status = cli.main([])

    assert status == 0
    assert calls == ["cron"]


def test_default_mode_routes_to_run_without_schedule(monkeypatch):
    """Routes default CLI mode to one-shot run when no schedule is configured."""
    calls = []

    monkeypatch.delenv("DEEZER_SCHEDULE", raising=False)
    monkeypatch.setattr(cli, "ensure_runtime_files", lambda mode: 0)
    monkeypatch.setattr(cli, "run_cron_mode", lambda: calls.append("cron") or 0)
    monkeypatch.setattr(cli, "run_once", lambda: calls.append("run") or 0)

    status = cli.main([])

    assert status == 0
    assert calls == ["run"]


def test_cron_scheduler_wait_is_interruptible():
    """Confirms scheduler wait exits early when the stop event is already set."""
    event = threading.Event()
    event.set()
    scheduler = CronScheduler(
        "0 3 * * *",
        event=event,
        now_provider=lambda: datetime(2026, 3, 27, 2, 0, 0),
    )

    should_run, wait_seconds = scheduler.wait_for_next_run()

    assert should_run is False
    assert wait_seconds >= 0


def test_normalize_pytest_target_promotes_tests_path_to_app(monkeypatch):
    """Normalizes tests/... targets to app/tests/... when the mapped path exists."""
    monkeypatch.setattr(cli.Path, "exists", lambda self: str(self) == "app/tests/test_main_entrypoint.py")

    normalized = cli._normalize_pytest_target("tests/test_main_entrypoint.py")

    assert normalized == "app/tests/test_main_entrypoint.py"


def test_normalize_pytest_target_preserves_nodeid_suffix(monkeypatch):
    """Preserves pytest node ids (for example, ::test_name) after path normalization."""
    monkeypatch.setattr(
        cli.Path,
        "exists",
        lambda self: str(self) == "app/tests/test_main_entrypoint.py",
    )

    normalized = cli._normalize_pytest_target(
        "tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"
    )

    assert normalized == "app/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"


def test_normalize_pytest_target_keeps_existing_app_path():
    """Leaves already-correct app-relative pytest paths unchanged."""
    normalized = cli._normalize_pytest_target("app/tests/test_main_entrypoint.py")

    assert normalized == "app/tests/test_main_entrypoint.py"


def test_normalize_pytest_target_maps_docker_absolute_path(monkeypatch):
    """Maps /deezer_engine/app/... absolute paths into app-relative paths when available."""
    monkeypatch.setattr(cli.Path, "exists", lambda self: str(self) == "app/tests/test_main_entrypoint.py")

    normalized = cli._normalize_pytest_target(
        "/deezer_engine/app/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"
    )

    assert normalized == "app/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"


def test_normalize_pytest_target_maps_docker_absolute_path_in_app_cwd(monkeypatch):
    """Maps Docker absolute paths to tests/... when running with app as current directory."""
    monkeypatch.setattr(cli.Path, "exists", lambda self: str(self) == "tests/test_main_entrypoint.py")

    normalized = cli._normalize_pytest_target(
        "/deezer_engine/app/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"
    )

    assert normalized == "tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"


def test_normalize_pytest_target_keeps_unmapped_absolute_path():
    """Keeps unrelated absolute paths untouched when no workspace mapping applies."""
    normalized = cli._normalize_pytest_target(
        "/opt/random/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"
    )

    assert normalized == "/opt/random/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors"


def test_normalize_pytest_target_keeps_nonexistent_relative_path(monkeypatch):
    """Keeps relative targets unchanged when neither original nor mapped path exists."""
    monkeypatch.setattr(cli.Path, "exists", lambda self: False)

    normalized = cli._normalize_pytest_target("tests/does_not_exist.py::test_missing")

    assert normalized == "tests/does_not_exist.py::test_missing"


def test_run_pytest_mode_normalizes_complex_arguments(monkeypatch):
    """Verifies run_pytest_mode normalizes only path args while preserving flags and values."""
    captured = {}

    class _FakePytest:
        @staticmethod
        def main(args):
            captured["args"] = args
            return 0

    monkeypatch.setitem(sys.modules, "pytest", _FakePytest)
    monkeypatch.setattr(
        cli.Path,
        "exists",
        lambda self: str(self) in {
            "app/tests/test_main_entrypoint.py",
            "app/tests/test_config_parsing.py",
            "app/tests/test_cli.py",
        },
    )

    status = cli.run_pytest_mode(
        [
            "-v",
            "-s",
            "tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors",
            "-k",
            "banner and errors",
            "/deezer_engine/app/tests/test_cli.py::test_default_mode_routes_to_run_without_schedule",
            "--maxfail=1",
            "tests/test_config_parsing.py",
        ]
    )

    assert status == 0
    assert captured["args"] == [
        "-v",
        "-s",
        "app/tests/test_main_entrypoint.py::test_main_entrypoint_banner_and_errors",
        "-k",
        "banner and errors",
        "app/tests/test_cli.py::test_default_mode_routes_to_run_without_schedule",
        "--maxfail=1",
        "app/tests/test_config_parsing.py",
    ]