# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil
import signal
import sys
from pathlib import Path

from entrypoint import main as run_engine
from scheduler import CronScheduler, DEFAULT_SCHEDULE
from utils.config import (
    get_bootstrap_logging_settings,
    get_global_value,
    normalize_runtime_environment,
)
from utils.infrastructure.logger import initialize_deezer_logger
from utils.infrastructure.paths import get_data_dir
from utils.infrastructure.signals import shutdown_event


VALID_MODES = {"default", "run", "cron", "pytest", "shell"}


def _register_shutdown_handlers(logger=None):
    def _handle_signal(sig, _frame):
        if logger:
            logger.warning("Signal %s received. Exiting after current operation.", sig)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def _resolve_mode(mode):
    if mode in (None, "", "default"):
        schedule = os.getenv("DEEZER_SCHEDULE", "")
        return "cron" if schedule else "run"
    return mode


def _bootstrap_logger():
    bootstrap_log_level, bootstrap_write_logs = get_bootstrap_logging_settings()
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    actual_level = bootstrap_log_level if bootstrap_log_level in valid_levels else "INFO"
    return initialize_deezer_logger(actual_level, log_to_file=bootstrap_write_logs)


def _strategies_template_path():
    return Path(__file__).resolve().parents[1] / "strategies.yml.template"


def ensure_runtime_files(mode):
    if mode in {"pytest", "shell"}:
        return 0, True

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    strategies_path = data_dir / "strategies.yml"
    if strategies_path.exists():
        return 0, True

    template_path = _strategies_template_path()
    print("No strategy file detected on startup!")
    if not template_path.exists():
        print(f"Template not found at {template_path}", file=sys.stderr)
        return 1, False

    shutil.copy(template_path, strategies_path)
    print(f"Generated default strategy file at {strategies_path}")
    print("Edit the file to configure your strategies, then rerun the command.")
    return 0, False


def run_once():
    run_engine()
    return 0


def run_cron_mode():
    logger = _bootstrap_logger()
    _register_shutdown_handlers(logger)

    schedule = str(get_global_value("schedule", DEFAULT_SCHEDULE))
    run_before = bool(get_global_value("run_before_cron", True))

    logger.info("Scheduler active. Schedule: %s", schedule)
    logger.info("Run before cron: %s", run_before)

    scheduler = CronScheduler(schedule, logger=logger)
    scheduler.run(run_once, run_before=run_before)
    return 0


def _normalize_pytest_target(arg):
    if not arg or arg.startswith("-"):
        return arg

    target, sep, suffix = arg.partition("::")
    target_path = Path(target)

    # Keep already app-rooted paths unchanged.
    if str(target_path).startswith("app/"):
        return arg

    def _rebuild(candidate):
        rebuilt = str(candidate)
        return f"{rebuilt}{sep}{suffix}" if sep else rebuilt

    def _first_existing(candidates):
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    if target_path.is_absolute():
        docker_app_root = Path("/deezer_engine/app")
        try:
            docker_relative = target_path.relative_to(docker_app_root)
        except ValueError:
            return arg

        matched = _first_existing([Path("app") / docker_relative, docker_relative])
        if matched is not None:
            return _rebuild(matched)
        return arg

    # If path already exists in current working directory, keep as-is.
    if target_path.exists():
        return arg

    matched = _first_existing([Path("app") / target_path])
    if matched is not None:
        return _rebuild(matched)

    return arg


def _normalize_pytest_args(args):
    return [_normalize_pytest_target(arg) for arg in args]


def run_pytest_mode(args):
    import pytest

    normalized_args = _normalize_pytest_args(list(args))

    # Print the full invocation path and arguments for clarity
    print("[pytest] Running with arguments:", " ".join(map(str, normalized_args)), file=sys.stderr)
    return pytest.main(normalized_args)


def run_shell_mode():
    os.execvp("/bin/bash", ["/bin/bash", "-i"])


def main(argv=None):
    shutdown_event.clear()
    normalize_runtime_environment()

    argv = list(sys.argv[1:] if argv is None else argv)
    mode = argv[0] if argv else "default"
    extra_args = argv[1:]

    if mode not in VALID_MODES:
        valid_modes = ", ".join(sorted(VALID_MODES))
        print(f"Unsupported mode '{mode}'. Expected one of: {valid_modes}", file=sys.stderr)
        return 2

    resolved_mode = _resolve_mode(mode)
    preflight_result = ensure_runtime_files(resolved_mode)
    if isinstance(preflight_result, tuple):
        preflight_status, should_continue = preflight_result
    else:
        preflight_status = preflight_result
        should_continue = preflight_status == 0

    if preflight_status != 0 or not should_continue:
        return preflight_status

    if resolved_mode == "run":
        return run_once()
    if resolved_mode == "cron":
        return run_cron_mode()
    if resolved_mode == "pytest":
        return run_pytest_mode(extra_args)
    if resolved_mode == "shell":
        run_shell_mode()
        return 0

    return 0