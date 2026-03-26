import importlib.util
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from utils.db.connection import get_db_path
from utils.config import reset_config_snapshot
from utils.infrastructure.paths import get_data_dir


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OFFLINE_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "album"
BACKUP_ALBUM_DIR = PROJECT_ROOT / "backups" / "album"
OFFLINE_STRATEGY_PATH = PROJECT_ROOT / "templates" / "validation" / "input_output" / "strategies.offline.yml"


EXPECTED_COUNTS = {
    "IOPASS": 71,
    "IOWARN": 1,
    "WARN": 1,
    "IOERR": 1,
    "ERR": 2,
    "IOPASS_SF": 29, # Source File
    "IOPASS_MF": 10, # Modifier Filter
    "IOPASS_ML": 12, # Modifier Limit
    "IOPASS_MS": 4, # Modifier Sort
    "IOPASS_ME": 2, # Modifier Exclude
    "IOPASS_MD": 2, # Modifier Dedupe
    "IOPASS_DF": 12, # Destination File
}


def _load_engine_module():
    module_path = PROJECT_ROOT / "deezer-engine.py"
    spec = importlib.util.spec_from_file_location("deezer_engine_entry", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _strip_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _parse_counts(log_text):
    lines = [_strip_ansi(line) for line in log_text.splitlines()]

    def count(pred):
        return sum(1 for line in lines if pred(line))

    return {
        "IOPASS": count(lambda line: "[I/O Validation] PASSED" in line),
        "IOWARN": count(lambda line: "[WARNING] [base._validate_io" in line and "[I/O Validation] FAILED" in line),
        "WARN": count(lambda line: "[WARNING]" in line),
        "IOERR": count(lambda line: "[ERROR] [base._validate_io" in line and "[I/O Validation] FAILED" in line),
        "ERR": count(lambda line: "[ERROR]" in line),
        "IOPASS_SF": count(lambda line: "[I/O Validation] PASSED Source 'file'" in line),
        "IOPASS_MF": count(lambda line: "[I/O Validation] PASSED Modifier 'filter'" in line),
        "IOPASS_ML": count(lambda line: "[I/O Validation] PASSED Modifier 'limit'" in line),
        "IOPASS_MS": count(lambda line: "[I/O Validation] PASSED Modifier 'sort'" in line),
        "IOPASS_ME": count(lambda line: "[I/O Validation] PASSED Modifier 'exclude'" in line),
        "IOPASS_MD": count(lambda line: "[I/O Validation] PASSED Modifier 'dedupe'" in line),
        "IOPASS_DF": count(lambda line: "[I/O Validation] PASSED Destination 'file'" in line),
    }


def _get_runtime_paths():
    data_dir = get_data_dir()
    return {
        "data_dir": data_dir,
        "db_path": get_db_path(),
        "strategy_path": data_dir / "strategies.yml",
        "log_file": data_dir / "logs" / f"{datetime.now().strftime('%Y-%m-%d')}.log",
    }


def _clear_deezer_logger_handlers():
    logger = logging.getLogger("DeezerEngine")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


@pytest.fixture(scope="module", autouse=True)
def check_offline_album_fixtures():
    OFFLINE_FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    required = [
        "102809.json",
        "384514987.json",
        "536294.json",
        "76585.json",
        "84698.json",
        "91258.json",
    ]
    for name in required:
        dst = OFFLINE_FIXTURE_DIR / name
        if not dst.exists():
            raise FileNotFoundError(f"Missing required offline album fixture: {dst}")


@pytest.fixture
def preserve_runtime_state(monkeypatch, backup_restore_runtime_files):
    monkeypatch.chdir(PROJECT_ROOT)
    reset_config_snapshot()
    _clear_deezer_logger_handlers()

    runtime_paths = _get_runtime_paths()
    strategy_path = runtime_paths["strategy_path"]
    strategy_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(OFFLINE_STRATEGY_PATH, strategy_path)

    try:
        yield runtime_paths
    finally:
        reset_config_snapshot()
        _clear_deezer_logger_handlers()


def test_input_output_offline(monkeypatch, preserve_runtime_state):
    runtime_paths = preserve_runtime_state
    log_file = runtime_paths["log_file"]
    db_path = runtime_paths["db_path"]

    monkeypatch.chdir(PROJECT_ROOT)
    monkeypatch.setenv("DEEZER_LOG_LEVEL", "INFO")
    monkeypatch.setenv("DEEZER_WRITE_LOGS", "true")
    monkeypatch.setenv("DEEZER_PRINT_BANNER", "false")

    if log_file.exists():
        log_file.unlink()

    engine = _load_engine_module()
    engine.main()

    assert log_file.exists(), f"Expected run to write log file: {log_file}"
    log_text = log_file.read_text(encoding="utf-8")
    counts = _parse_counts(log_text)

    for key, expected in EXPECTED_COUNTS.items():
        actual = counts[key]
        assert actual == expected, f"{key} expected {expected}, got {actual}"

    assert db_path.exists(), f"Expected test run to create a fresh {db_path}"
