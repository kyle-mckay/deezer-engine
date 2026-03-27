import os
import sys
from datetime import datetime
from pathlib import Path

import pytest
from utils.infrastructure.paths import get_data_dir

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT_RUN_RESULT = None


def _write_minimal_runtime_files(config_path, strategies_path):
	config_path.write_text("config:\n  log_level: 'DEBUG'\n  arl_token: ''\n", encoding="utf-8")
	strategies_path.write_text("playlists:\n", encoding="utf-8")


def _runtime_log_file_path():
	data_dir = get_data_dir()
	return data_dir / "logs" / f"{datetime.now().strftime('%Y-%m-%d')}.log"


def _is_containerized_runtime():
	value = os.getenv("CONTAINERIZED")
	if value is None:
		value = os.getenv("DEEZER_CONTAINERIZED", "false")
	return str(value).strip().lower() in ("true", "1", "yes", "on")


def _print_output_once(result):
	if result["output_printed"]:
		return
	print(result["output"])
	result["output_printed"] = True


def _assert_log_file(result):
	_print_output_once(result)
	assert result["log_file_exists"], f"Expected run to write log file: {result['log_file']}"


def _assert_banner(result):
	output = result["output"]
	if _is_containerized_runtime():
		assert "Running Deezer-Engine" not in output, "Engine banner should be suppressed in containerized mode."
	else:
		assert "Running Deezer-Engine" in output, "Banner NOT detected in output."


def _assert_database_migration(result):
	output = result["output"]
	assert result["db_exists"], f"Expected run to create database file: {result['db_path']}"
	assert "Database: Migration run completed (status=ok" in output, "Successful migration completion not detected in output."

def _assert_strategy_message(result):
	output = result["output"]
	assert (
		"Strategies file" in output
		or "No strategies found" in output
	), "Strategy/config warning not found."



def _assert_auth_message(result):
	output = result["output"]
	assert (
		"Config is None, returning unauthenticated Deezer client for testing." in output
		or "Authenticated successfully" in output
	), "Pytest-mode authentication path not detected."


def _run_entrypoint_once(monkeypatch, backup_restore_runtime_files, run_subprocess):
	global ENTRYPOINT_RUN_RESULT

	if ENTRYPOINT_RUN_RESULT is not None:
		return ENTRYPOINT_RUN_RESULT

	_write_minimal_runtime_files(
		backup_restore_runtime_files["config_path"],
		backup_restore_runtime_files["strategies_path"],
	)

	# Use controlled runtime files in project root and force deterministic startup behavior.
	log_file = _runtime_log_file_path()
	monkeypatch.setenv("DEEZER_PRINT_BANNER", "true")
	monkeypatch.setenv("DEEZER_LOG_LEVEL", "DEBUG")
	monkeypatch.setenv("DEEZER_WRITE_LOGS", "true")
	monkeypatch.chdir(PROJECT_ROOT)

	if log_file.exists():
		log_file.unlink()

	# Run the entrypoint
	proc = run_subprocess(
		[sys.executable, "-m", "deezer_engine", "run"],
		cwd=str(PROJECT_ROOT),
		timeout=30,
	)
	output = proc.stdout

	ENTRYPOINT_RUN_RESULT = {
		"output": output,
		"log_file": log_file,
		"log_file_exists": log_file.exists(),
		"db_path": backup_restore_runtime_files["db_path"],
		"db_exists": backup_restore_runtime_files["db_path"].exists(),
		"output_printed": False,
	}
	return ENTRYPOINT_RUN_RESULT


ENTRYPOINT_ASSERTIONS = [
	pytest.param(_assert_log_file, id="log-file"),
	pytest.param(_assert_banner, id="banner"),
	pytest.param(_assert_strategy_message, id="strategy-message"),
	pytest.param(_assert_auth_message, id="auth-message"),
	pytest.param(_assert_database_migration, id="database-migration"),
]


@pytest.mark.skipif(sys.platform == "win32", reason="Test not supported on Windows")
@pytest.mark.parametrize("assertion", ENTRYPOINT_ASSERTIONS)
def test_main_entrypoint_banner_and_errors(monkeypatch, backup_restore_runtime_files, run_subprocess, assertion):
	"""
	Mimics the fresh project execution: checks for banner, config warning, and ARL error in output.
	"""
	result = _run_entrypoint_once(monkeypatch, backup_restore_runtime_files, run_subprocess)
	assertion(result)
