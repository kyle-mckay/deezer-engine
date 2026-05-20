import logging
from pathlib import Path
import pytest

from utils.config.parsing import load_config_with_env_overrides, reset_config_snapshot
from utils.config.strategy_validation import load_strategies_with_env_overrides
import utils.config.parsing as parsing
import utils.config.strategy_validation as strategy_validation


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_SCHEMA_DIR = REPO_ROOT / "templates" / "validation" / "schema"


pytestmark = [pytest.mark.unit]


def _copy_template_to_runtime(tmp_path: Path, template_name: str, runtime_name: str):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    template_path = TEMPLATE_SCHEMA_DIR / template_name
    destination = data_dir / runtime_name
    destination.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
    return data_dir


def test_schema_config_template_emits_expected_unknown_key_warnings(monkeypatch, tmp_path, caplog, capsys):
    """Verifies schema config template intentionally emits key-warning examples."""
    reset_config_snapshot()
    monkeypatch.setattr(
        parsing,
        "get_data_dir",
        lambda: _copy_template_to_runtime(tmp_path, "config.yml", "config.yml"),
    )

    try:
        with caplog.at_level("WARNING", logger="DeezerEngine"):
            loaded = load_config_with_env_overrides(force_reload=True)

        captured = capsys.readouterr()
        warning_output = f"{caplog.text}\n{captured.err}\n{captured.out}"

        assert "config" in loaded
        assert "Unknown top-level config key(s)" in warning_output
        assert "warn_test_root_key" in warning_output
        assert "Unknown config key(s)" in warning_output
        assert "log_levle" in warning_output
        assert "retaention" in warning_output
    finally:
        reset_config_snapshot()


def test_schema_strategies_template_loads_with_intentional_warnings(monkeypatch, tmp_path, caplog):
    """Ensures schema strategies template still loads while surfacing intentional typo warnings."""
    logger = logging.getLogger("tests.schema_templates")
    logger.setLevel(logging.DEBUG)
    monkeypatch.setattr(
        strategy_validation,
        "get_data_dir",
        lambda: _copy_template_to_runtime(tmp_path, "strategies.yml", "strategies.yml"),
    )

    with caplog.at_level("WARNING", logger="tests.schema_templates"):
        loaded = load_strategies_with_env_overrides(logger)

    assert "playlists" in loaded
    assert len(loaded["playlists"]) >= 9, (
        f"Expected at least 9 strategies to load from schema template, got {len(loaded['playlists'])}"
    )
    assert "Unknown key(s)" in caplog.text
    assert "modify" in caplog.text
    assert "retaention" in caplog.text
    assert "counts" in caplog.text
    assert "ordr" in caplog.text
    # Interleave-specific keys must never appear as unknown-key warnings
    assert "'inject'" not in caplog.text or "Unknown key(s)" not in caplog.text.split("'inject'")[0].split("\n")[-1], (
        "'inject' must not be flagged as an unknown key"
    )


def test_schema_strategies_interleave_loads_without_unknown_key_warnings(monkeypatch, tmp_path, caplog):
    """Verifies the interleave strategy in the schema template loads with no unknown-key warnings."""
    logger = logging.getLogger("tests.schema_templates.interleave")
    logger.setLevel(logging.DEBUG)
    monkeypatch.setattr(
        strategy_validation,
        "get_data_dir",
        lambda: _copy_template_to_runtime(tmp_path, "strategies.yml", "strategies.yml"),
    )

    with caplog.at_level("WARNING", logger="tests.schema_templates.interleave"):
        loaded = load_strategies_with_env_overrides(logger)

    interleave_strategies = [
        s for s in loaded.get("playlists", [])
        if "interleave" in s.get("name", "").lower()
    ]
    assert len(interleave_strategies) >= 1, (
        f"Expected at least one interleave strategy to load, got: {[s.get('name') for s in loaded.get('playlists', [])]}"
    )

    interleave_key_warnings = [
        line for line in caplog.text.splitlines()
        if "Unknown key(s)" in line and any(
            k in line for k in ("inject", "continue_on_exhaust", "every", "add")
        )
    ]
    assert not interleave_key_warnings, (
        f"Interleave-specific keys produced unexpected unknown-key warnings:\n" +
        "\n".join(interleave_key_warnings)
    )
