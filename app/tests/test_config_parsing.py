from pathlib import Path

import pytest
import yaml

from utils.config.parsing import (
    get_global_value,
    load_config_with_env_overrides,
    normalize_runtime_environment,
    reset_config_snapshot,
)
import utils.config.parsing as parsing


pytestmark = [pytest.mark.unit]


def _warning_output(caplog, capsys):
    captured = capsys.readouterr()
    return f"{caplog.text}\n{captured.err}\n{captured.out}"


def _write_config(tmp_path: Path, run_before_cron_value):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "config.yml"
    config_path.write_text(
        yaml.safe_dump({"config": {"run_before_cron": run_before_cron_value}}),
        encoding="utf-8",
    )
    return data_dir


def _write_raw_config(tmp_path: Path, payload):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_path = data_dir / "config.yml"
    config_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return data_dir


@pytest.fixture(autouse=True)
def _reset_snapshots():
    reset_config_snapshot()
    try:
        yield
    finally:
        reset_config_snapshot()


def test_run_before_cron_is_coerced_from_environment(monkeypatch):
    """Verifies env bool coercion for run_before_cron (for example, no -> False)."""
    monkeypatch.setenv("DEEZER_RUN_BEFORE_CRON", "no")
    config = load_config_with_env_overrides(force_reload=True)

    assert config["config"]["run_before_cron"] is False
    assert get_global_value("run_before_cron", True) is False


def test_run_before_cron_can_come_from_config_file(monkeypatch, tmp_path):
    """Ensures file config values are used when the related env var is absent."""
    monkeypatch.delenv("DEEZER_RUN_BEFORE_CRON", raising=False)
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_config(tmp_path, False))
    config = load_config_with_env_overrides(force_reload=True)

    assert config["config"]["run_before_cron"] is False
    assert get_global_value("run_before_cron", True) is False


def test_run_before_cron_environment_overrides_config(monkeypatch, tmp_path):
    """Confirms env values take precedence over config.yml values for the same key."""
    monkeypatch.setenv("DEEZER_RUN_BEFORE_CRON", "true")
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_config(tmp_path, False))

    config = load_config_with_env_overrides(force_reload=True)

    assert config["config"]["run_before_cron"] is True
    assert get_global_value("run_before_cron", False) is True


def test_int_config_key_is_coerced_from_environment(monkeypatch, tmp_path):
    """Verifies numeric env strings are coerced to ints (for example, 42 -> 42)."""
    monkeypatch.setenv("DEEZER_CHUNK_SIZE", "42")
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, {"config": {}}))

    config = load_config_with_env_overrides(force_reload=True)

    assert config["config"]["chunk_size"] == 42
    assert isinstance(config["config"]["chunk_size"], int)
    assert get_global_value("chunk_size", 0) == 42


def test_invalid_int_env_value_falls_back_to_string(monkeypatch, tmp_path):
    """Ensures invalid numeric env input is preserved as a raw string."""
    monkeypatch.setenv("DEEZER_CHUNK_SIZE", "forty-two")
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, {"config": {}}))

    config = load_config_with_env_overrides(force_reload=True)

    assert config["config"]["chunk_size"] == "forty-two"
    assert get_global_value("chunk_size", 0) == "forty-two"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("yes", True),
        ("on", True),
        ("1", True),
        ("0", False),
        ("no", False),
        ("off", False),
    ],
)
def test_bool_env_coercion_variants(monkeypatch, tmp_path, raw_value, expected):
    """Checks supported truthy/falsy env aliases (for example, on/off, 1/0)."""
    monkeypatch.setenv("DEEZER_RUN_BEFORE_CRON", raw_value)
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, {"config": {}}))

    config = load_config_with_env_overrides(force_reload=True)

    assert config["config"]["run_before_cron"] is expected


def test_missing_config_file_returns_empty_config(monkeypatch, tmp_path):
    """Confirms missing config.yml is handled gracefully with an empty config section."""
    monkeypatch.delenv("CONTAINERIZED", raising=False)
    empty_data_dir = tmp_path / "data"
    empty_data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(parsing, "get_data_dir", lambda: empty_data_dir)

    config = load_config_with_env_overrides(force_reload=True)

    assert config == {"config": {}}


def test_non_mapping_root_structure_is_ignored(monkeypatch, tmp_path, caplog, capsys):
    """Ensures non-object YAML roots are ignored and produce a warning."""
    monkeypatch.delenv("CONTAINERIZED", raising=False)
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, ["invalid-root"]))
    try:
        with caplog.at_level("WARNING", logger="DeezerEngine"):
            config = load_config_with_env_overrides(force_reload=True)
            warning_output = _warning_output(caplog, capsys)
            assert config == {"config": {}}
            assert get_global_value("run_before_cron", False) is False
            assert "Top-level config.yml content must be an object" in warning_output
    finally:
        reset_config_snapshot()

def test_normalize_runtime_environment_strips_wrapping_quotes(monkeypatch):
    """Verifies normalization strips outer quotes from env values before parsing."""
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
    """Confirms normalized DEEZER_SCHEDULE is available through global config lookup."""
    reset_config_snapshot()
    monkeypatch.setenv("DEEZER_SCHEDULE", '"15 4 * * *"')

    try:
        normalize_runtime_environment()
        assert get_global_value("schedule", "0 3 * * *") == "15 4 * * *"
    finally:
        reset_config_snapshot()

def test_non_mapping_config_section_is_ignored(monkeypatch, tmp_path, caplog, capsys):
    """Ensures a non-object 'config' section is ignored with a validation warning."""
    monkeypatch.delenv("CONTAINERIZED", raising=False)
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, {"config": "invalid"}))

    with caplog.at_level("WARNING", logger="DeezerEngine"):
        config = load_config_with_env_overrides(force_reload=True)

    warning_output = _warning_output(caplog, capsys)
    assert config == {"config": {}}
    assert "The 'config' section must be an object" in warning_output


def test_unknown_keys_trigger_warning_with_suggestion(monkeypatch, tmp_path, caplog):
    """Checks typo suggestions for unknown keys (for example, log_levle -> log_level)."""
    payload = {
        "cnfig": True,
        "config": {
            "log_levle": "DEBUG",
            "run_before_cron": True,
        },
    }
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, payload))

    with caplog.at_level("WARNING", logger="DeezerEngine"):
        load_config_with_env_overrides(force_reload=True)

    assert "Unknown top-level config key(s)" in caplog.text
    assert "did you mean 'config'" in caplog.text
    assert "Unknown config key(s)" in caplog.text
    assert "did you mean 'log_level'" in caplog.text


def test_get_global_value_returns_default_when_key_missing(monkeypatch, tmp_path):
    """Verifies missing keys return the caller-provided fallback value."""
    monkeypatch.setattr(parsing, "get_data_dir", lambda: _write_raw_config(tmp_path, {"config": {}}))

    assert get_global_value("nonexistent_key", "fallback") == "fallback"


def test_get_global_value_returns_default_when_snapshot_init_fails(monkeypatch):
    """Ensures global lookups fail safe to defaults when snapshot init raises."""
    monkeypatch.setattr(parsing, "initialize_config_snapshot", lambda: (_ for _ in ()).throw(RuntimeError("boom")))

    assert get_global_value("run_before_cron", True) is True
