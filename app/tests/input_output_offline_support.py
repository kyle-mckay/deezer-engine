import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from utils.config import reset_config_snapshot
from utils.db.connection import get_db_path
from utils.infrastructure.paths import get_data_dir


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
OFFLINE_FIXTURE_DIR = REPO_ROOT / "app" / "tests" / "fixtures" / "album"
OFFLINE_STRATEGY_PATH = REPO_ROOT / "templates" / "validation" / "input_output" / "strategies.offline.yml"

EXPECTED_COUNTS = {
    "IOPASS": 73,
    "IOWARN": 1,
    "WARN": 1,
    "IOERR": 1,
    "ERR": 2,
    "IOPASS_SF": 30,
    "IOPASS_MF": 10,
    "IOPASS_ML": 12,
    "IOPASS_MS": 4,
    "IOPASS_ME": 2,
    "IOPASS_MD": 2,
    "IOPASS_DF": 13,
    "SAVE_DF": 13,
}

TOTAL_COUNT_KEYS = ("IOPASS", "IOWARN", "WARN", "IOERR", "ERR")

COMPONENT_COUNT_CASES = [
    pytest.param("IOPASS_SF", "source-file", EXPECTED_COUNTS["IOPASS_SF"], id="source-file-30"),
    pytest.param("IOPASS_MF", "modifier-filter", EXPECTED_COUNTS["IOPASS_MF"], id="modifier-filter-10"),
    pytest.param("IOPASS_ML", "modifier-limit", EXPECTED_COUNTS["IOPASS_ML"], id="modifier-limit-12"),
    pytest.param("IOPASS_MS", "modifier-sort", EXPECTED_COUNTS["IOPASS_MS"], id="modifier-sort-4"),
    pytest.param("IOPASS_ME", "modifier-exclude", EXPECTED_COUNTS["IOPASS_ME"], id="modifier-exclude-2"),
    pytest.param("IOPASS_MD", "modifier-dedupe", EXPECTED_COUNTS["IOPASS_MD"], id="modifier-dedupe-2"),
    pytest.param("IOPASS_DF", "destination-file", EXPECTED_COUNTS["IOPASS_DF"], id="destination-file-13"),
    pytest.param("SAVE_DF", "destination-file-save", EXPECTED_COUNTS["SAVE_DF"], id="destination-file-save-13"),
]

OFFLINE_SHARED_CACHE_KEY = "offline-shared"
ONLINE_SHARED_CACHE_KEY = "online-shared"

_OFFLINE_RUN_RESULTS = {}


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
        "SAVE_DF": count(lambda line: "Successfully saved tracks to:" in line),
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
    """Asserts all required album fixture JSON files are present before any offline test runs."""
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
    """Backs up runtime state, copies the offline strategy file into place, and restores on teardown."""
    monkeypatch.chdir(REPO_ROOT)
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


def run_input_output_once(monkeypatch, preserve_runtime_state, run_engine_main, cache_key, pull_metadata_enabled=False):
    """Runs the engine once for a given cache key and returns a dict of log/db/count results; caches per key."""
    if cache_key in _OFFLINE_RUN_RESULTS:
        return _OFFLINE_RUN_RESULTS[cache_key]

    runtime_paths = preserve_runtime_state
    log_file = runtime_paths["log_file"]
    db_path = runtime_paths["db_path"]

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setenv("DEEZER_LOG_LEVEL", "INFO")
    monkeypatch.setenv("DEEZER_WRITE_LOGS", "true")
    monkeypatch.setenv("DEEZER_PULL_METADATA", "true" if pull_metadata_enabled else "false")

    if log_file.exists():
        log_file.unlink()

    run_engine_main()

    log_text = log_file.read_text(encoding="utf-8") if log_file.exists() else ""

    _OFFLINE_RUN_RESULTS[cache_key] = {
        "log_file": log_file,
        "log_file_exists": log_file.exists(),
        "log_text": log_text,
        "counts": _parse_counts(log_text),
        "db_path": db_path,
        "db_exists": db_path.exists(),
        "log_printed": False,
    }
    return _OFFLINE_RUN_RESULTS[cache_key]


def print_log_once(result):
    """Prints the captured log text to stdout; subsequent calls for the same result are no-ops."""
    if result["log_printed"]:
        return
    print(result["log_text"])
    result["log_printed"] = True
