from pathlib import Path
import shutil
import re
from datetime import datetime

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


@pytest.fixture
def runtime_file_paths():
    return {
        "config_path": PROJECT_ROOT / "config.yml",
        "strategies_path": PROJECT_ROOT / "strategies.yml",
        "db_path": PROJECT_ROOT / "db" / "deezer_engine.db",
    }


@pytest.fixture
def backup_restore_runtime_files(runtime_file_paths, request):
    config_path = runtime_file_paths["config_path"]
    strategies_path = runtime_file_paths["strategies_path"]
    db_path = runtime_file_paths["db_path"]
    test_name = request.node.name
    logs_dir = PROJECT_ROOT / "logs"
    pytest_logs_dir = logs_dir / "pytest"
    today_log_stem = datetime.now().strftime('%Y-%m-%d')
    today_log_name = f"{today_log_stem}.log"
    today_log_path = logs_dir / today_log_name
    prod_log_backup = logs_dir / f"{today_log_name}.pytest-backup"

    config_backup = config_path.with_suffix(".yml.pytest-backup")
    strategies_backup = strategies_path.with_suffix(".yml.pytest-backup")
    db_backup = db_path.with_suffix(".db.pytest-backup")

    try:
        if config_path.exists():
            shutil.copy2(config_path, config_backup)
            config_path.unlink()

        if strategies_path.exists():
            shutil.copy2(strategies_path, strategies_backup)
            strategies_path.unlink()

        if db_path.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_path, db_backup)
            db_path.unlink()

        logs_dir.mkdir(parents=True, exist_ok=True)
        pytest_logs_dir.mkdir(parents=True, exist_ok=True)
        if today_log_path.exists():
            if prod_log_backup.exists():
                prod_log_backup.unlink()
            shutil.move(str(today_log_path), str(prod_log_backup))

        yield runtime_file_paths
    finally:
        if today_log_path.exists():
            if today_log_path.stat().st_size == 0:
                today_log_path.unlink()
            else:
                pytest_log_path = _build_pytest_log_path(pytest_logs_dir, test_name)
                shutil.move(str(today_log_path), str(pytest_log_path))

        if prod_log_backup.exists():
            if today_log_path.exists():
                today_log_path.unlink()
            shutil.move(str(prod_log_backup), str(today_log_path))

        if config_path.exists():
            config_path.unlink()
        if config_backup.exists():
            shutil.copy2(config_backup, config_path)
            config_backup.unlink()

        if strategies_path.exists():
            strategies_path.unlink()
        if strategies_backup.exists():
            shutil.copy2(strategies_backup, strategies_path)
            strategies_backup.unlink()

        if db_path.exists():
            db_path.unlink()
        if db_backup.exists():
            shutil.copy2(db_backup, db_path)
            db_backup.unlink()
