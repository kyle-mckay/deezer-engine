import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = PROJECT_ROOT / "deezer-engine.py"


def _write_minimal_runtime_files(config_path, strategies_path):
	config_path.write_text("config:\n  log_level: 'DEBUG'\n  arl_token: ''\n", encoding="utf-8")
	strategies_path.write_text("playlists:\n", encoding="utf-8")


@pytest.mark.skipif(sys.platform == "win32", reason="Test not supported on Windows")
def test_main_entrypoint_banner_and_errors(monkeypatch, backup_restore_runtime_files):
	"""
	Mimics the fresh project execution: runs deezer-engine.py, checks for banner, config warning, and ARL error in output.
	"""
	_write_minimal_runtime_files(
		backup_restore_runtime_files["config_path"],
		backup_restore_runtime_files["strategies_path"],
	)

	# Use controlled runtime files in project root and force deterministic startup behavior.
	monkeypatch.setenv("DEEZER_PRINT_BANNER", "true")
	monkeypatch.setenv("DEEZER_LOG_LEVEL", "DEBUG")
	monkeypatch.setenv("DEEZER_WRITE_LOGS", "false")
	monkeypatch.chdir(PROJECT_ROOT)

	# Run the entrypoint
	proc = subprocess.run(
		[sys.executable, str(ENGINE_PATH), "run"],
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		text=True,
		cwd=str(PROJECT_ROOT),
		timeout=30,
	)
	output = proc.stdout
	print("=== OUTPUT START ===")
	print(output)
	print("=== OUTPUT END ===")
	
	# 1. Check for the Banner
	assert "Running Deezer-Engine" in output, "Banner NOT detected in output."

	# 2. Check for Config Warning or Strategy file warning
	assert ("Strategies file" in output or "No strategies found" in output or "Processing Strategy" in output), "Strategy/config warning not found."

	# 3. Check for pytest-mode unauthenticated client path
	assert (
		"Config is None, returning unauthenticated Deezer client for testing." in output
		or "Authenticated successfully" in output
	), "Pytest-mode authentication path not detected."
