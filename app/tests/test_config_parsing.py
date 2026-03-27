from pathlib import Path

import yaml

from utils.config.parsing import (
    get_global_value,
    load_config_with_env_overrides,
    normalize_runtime_environment,
    reset_config_snapshot,
)
import utils.config.parsing as parsing


def _write_config(tmp_path: Path, run_before_cron_value):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump({"config": {"run_before_cron": run_before_cron_value}}),
        encoding="utf-8",
    )
    return data_dir


def test_run_before_cron_is_coerced_from_environment(monkeypatch):
    reset_config_snapshot()
    monkeypatch.setenv("DEEZER_RUN_BEFORE_CRON", "no")

    try:
        config = load_config_with_env_overrides(force_reload=True)
        assert config["config"]["run_before_cron"] is False
        assert get_global_value("run_before_cron", True) is False
    finally:
        reset_config_snapshot()


def test_run_before_cron_can_come_from_config_file(monkeypatch, tmp_path):
    reset_config_snapshot()
    monkeypatch.delenv("DEEZER_RUN_BEFORE_CRON", raising=False)
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_config(tmp_path, False))

    try:
        config = load_config_with_env_overrides(force_reload=True)
        assert config["config"]["run_before_cron"] is False
        assert get_global_value("run_before_cron", True) is False
    finally:
        reset_config_snapshot()


def test_run_before_cron_environment_overrides_config(monkeypatch, tmp_path):
    reset_config_snapshot()
    monkeypatch.setenv("DEEZER_RUN_BEFORE_CRON", "true")
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_config(tmp_path, False))

    try:
        config = load_config_with_env_overrides(force_reload=True)
        assert config["config"]["run_before_cron"] is True
        assert get_global_value("run_before_cron", False) is True
    finally:
        reset_config_snapshot()


def test_normalize_runtime_environment_strips_wrapping_quotes(monkeypatch):
    reset_config_snapshot()
    monkeypatch.setenv("DEEZER_SCHEDULE", '"0 3 * * *"')
    monkeypatch.setenv("DEEZER_RUN_BEFORE_CRON", "'false'")

    try:
        normalize_runtime_environment()
        assert parsing.os.environ["DEEZER_SCHEDULE"] == "0 3 * * *"
        assert get_global_value("run_before_cron", True) is False
    finally:
        reset_config_snapshot()


def test_schedule_is_exposed_via_global_value(monkeypatch):
    reset_config_snapshot()
    monkeypatch.setenv("DEEZER_SCHEDULE", '"15 4 * * *"')

    try:
        normalize_runtime_environment()
        assert get_global_value("schedule", "0 3 * * *") == "15 4 * * *"
    finally:
        reset_config_snapshot()
