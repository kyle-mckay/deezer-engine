import logging
from pathlib import Path
import random

import pytest
import yaml

from utils.config.strategy_validation import load_strategies_with_env_overrides
import utils.config.strategy_validation as strategy_validation
from utils.config.key_validation import (
    DESTINATION_TYPE_KEYS,
    MODIFIER_TYPE_KEYS,
    SOURCE_TYPE_KEYS,
    STRATEGY_TOP_LEVEL_KEYS,
)


RNG = random.Random(20260327)


pytestmark = [pytest.mark.unit]


def _write_strategies(tmp_path: Path, payload):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    strategies_path = data_dir / "strategies.yml"
    strategies_path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return data_dir


def _make_typo(key_name):
    if len(key_name) < 4:
        return f"{key_name}x"

    idx = len(key_name) // 2
    chars = list(key_name)
    chars[idx - 1], chars[idx] = chars[idx], chars[idx - 1]
    typo = "".join(chars)
    if typo == key_name:
        return f"{key_name}x"
    return typo


def _value_for_key(key_name):
    if key_name in {"id", "count", "limit", "lookback", "retention", "i", "o"}:
        return 1
    if key_name in {"source"}:
        return [{"type": "favorites"}]
    return "value"


@pytest.fixture
def validation_logger():
    logger = logging.getLogger("tests.strategy_validation")
    logger.setLevel(logging.DEBUG)
    return logger


def test_strategy_missing_source_type_is_rejected(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects strategies when a source item omits the required type field."""
    payload = {
        "playlists": [
            {
                "name": "missing-source-type",
                "source": [{"id": "12345"}],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Missing 'type'" in caplog.text


def test_strategy_invalid_destination_shape_is_rejected(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects strategies when destination is not a list of destination objects."""
    payload = {
        "playlists": [
            {
                "name": "bad-destination",
                "source": [{"type": "favorites"}],
                "destination": {"type": "playlist", "id": "999"},
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Missing or invalid list" in caplog.text


def test_duplicate_sources_warn_but_strategy_still_loads(monkeypatch, tmp_path, validation_logger, caplog):
    """Warns on exact duplicate sources but keeps the strategy loadable."""
    source_entry = {"type": "favorites"}
    payload = {
        "playlists": [
            {
                "name": "duplicate-source",
                "source": [source_entry, source_entry],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("WARNING", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Exact duplicate source(s)" in caplog.text


def test_unknown_key_warning_includes_suggestion(monkeypatch, tmp_path, validation_logger, caplog):
    """Confirms unknown modifier keys include nearest-key suggestions in warnings."""
    payload = {
        "playlists": [
            {
                "name": "unknown-key-with-suggestion",
                "source": [{"type": "favorites"}],
                "modifiers": [{"type": "limit", "orde": "top", "count": 10}],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("WARNING", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Unknown key(s)" in caplog.text
    assert "did you mean 'order'" in caplog.text


def test_nested_modifier_source_missing_type_fails(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects nested modifier sources that miss type, not just top-level sources."""
    payload = {
        "playlists": [
            {
                "name": "nested-source-missing-type",
                "source": [{"type": "favorites"}],
                "modifiers": [
                    {
                        "type": "exclude",
                        "source": [{"id": "123"}],
                    }
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Missing 'type'" in caplog.text


def test_all_known_types_can_load_without_unknown_key_warnings(monkeypatch, tmp_path, validation_logger, caplog):
    """Ensures all declared source/modifier/destination types pass key validation cleanly."""
    sources = [{"type": source_type} for source_type in sorted(SOURCE_TYPE_KEYS.keys())]
    modifiers = [{"type": modifier_type} for modifier_type in sorted(MODIFIER_TYPE_KEYS.keys())]
    destinations = [{"type": destination_type} for destination_type in sorted(DESTINATION_TYPE_KEYS.keys())]

    payload = {
        "playlists": [
            {
                "name": "all-known-types",
                "source": sources,
                "modifiers": modifiers,
                "destination": destinations,
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("WARNING", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Unknown key(s)" not in caplog.text


@pytest.mark.parametrize("source_type", ["album", "artist", "playlist", "track"])
def test_id_based_source_accepts_scalar_or_list_id(monkeypatch, tmp_path, validation_logger, caplog, source_type):
    """Allows id-based sources to use a single id or a list of ids in the same id field."""
    payload = {
        "playlists": [
            {
                "name": f"{source_type}-id-list",
                "source": [
                    {"type": source_type, "id": "123"},
                    {"type": source_type, "id": ["123", "456", 789, None]},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Invalid 'id'" not in caplog.text


@pytest.mark.parametrize("source_type", ["album", "artist", "playlist", "track"])
def test_id_based_source_rejects_invalid_id_shape(monkeypatch, tmp_path, validation_logger, caplog, source_type):
    """Rejects id-based sources when id uses unsupported shapes like nested objects/lists."""
    payload = {
        "playlists": [
            {
                "name": f"{source_type}-invalid-id-shape",
                "source": [
                    {"type": source_type, "id": {"bad": "shape"}},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Invalid 'id' type" in caplog.text


def test_smarttracklist_source_accepts_scalar_or_list_name(monkeypatch, tmp_path, validation_logger, caplog):
    """Allows smarttracklist source to use a single name or a list of names."""
    payload = {
        "playlists": [
            {
                "name": "smarttracklist-name-list",
                "source": [
                    {"type": "smarttracklist", "name": "discovery"},
                    {"type": "smarttracklist", "name": ["new-releases", "inspired-by-1", None]},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Invalid 'name'" not in caplog.text


def test_source_override_collection_accepts_scalar(monkeypatch, tmp_path, validation_logger, caplog):
    """Allows source override_collection to be a scalar value."""
    payload = {
        "playlists": [
            {
                "name": "override-collection-scalar",
                "source": [
                    {"type": "track", "id": ["123", "456"], "override_collection": "smarttracklist__discovery"},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Invalid 'override_collection'" not in caplog.text


def test_source_override_collection_rejects_invalid_shape(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects source override_collection when provided as a non-scalar shape."""
    payload = {
        "playlists": [
            {
                "name": "override-collection-invalid",
                "source": [
                    {"type": "track", "id": "123", "override_collection": {"bad": "shape"}},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Invalid 'override_collection' type" in caplog.text


def test_file_source_accepts_scalar_or_list_name_keys(monkeypatch, tmp_path, validation_logger, caplog):
    """Allows file source to use name/filename as scalar or list."""
    payload = {
        "playlists": [
            {
                "name": "file-name-list",
                "source": [
                    {"type": "file", "filename": "backup.json"},
                    {"type": "file", "name": ["backup_a.csv", "backup_b.csv", None]},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Invalid 'filename'" not in caplog.text
    assert "Invalid 'name'" not in caplog.text


def test_name_based_source_rejects_invalid_name_shape(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects invalid name field shapes for smarttracklist/file sources."""
    payload = {
        "playlists": [
            {
                "name": "invalid-name-shape",
                "source": [
                    {"type": "smarttracklist", "name": {"bad": "shape"}},
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Invalid 'name' type" in caplog.text


def test_top_level_strategy_name_rejects_invalid_shape(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects malformed top-level strategy names so runtime sanitization is a fallback only."""
    payload = {
        "playlists": [
            {
                "name": {"bad": "shape"},
                "source": [{"type": "favorites"}],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Invalid top-level 'name' type" in caplog.text


def test_top_level_strategy_name_rejects_list(monkeypatch, tmp_path, validation_logger, caplog):
    """Rejects list-valued top-level strategy names to catch indentation mistakes early."""
    payload = {
        "playlists": [
            {
                "name": ["discovery", "new-releases"],
                "source": [{"type": "favorites"}],
                "destination": [{"type": "playlist", "id": "999"}],
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("ERROR", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert loaded == {"playlists": []}
    assert "Invalid top-level 'name' type 'list'" in caplog.text


def test_random_top_level_strategy_typo_warns(monkeypatch, tmp_path, validation_logger, caplog):
    """Checks random top-level key typos are reported as unknown strategy keys."""
    key_candidates = [key for key in sorted(STRATEGY_TOP_LEVEL_KEYS) if len(key) >= 4 and key != "name"]
    selected = RNG.choice(key_candidates)
    typo = _make_typo(selected)

    payload = {
        "playlists": [
            {
                "name": "strategy-typo",
                "source": [{"type": "favorites"}],
                "destination": [{"type": "playlist", "id": "999"}],
                typo: "value",
            }
        ]
    }
    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("WARNING", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Unknown key(s)" in caplog.text
    assert typo in caplog.text


@pytest.mark.parametrize(
    ("depth_name", "key_pool", "inject"),
    [
        (
            "source-depth-1",
            SOURCE_TYPE_KEYS["history"],
            lambda typo, value: {
                "source": [{"type": "history", typo: value}],
                "destination": [{"type": "playlist", "id": "999"}],
            },
        ),
        (
            "modifier-depth-2",
            MODIFIER_TYPE_KEYS["filter"],
            lambda typo, value: {
                "source": [
                    {
                        "type": "favorites",
                        "modifiers": [{"type": "filter", typo: value}],
                    }
                ],
                "destination": [{"type": "playlist", "id": "999"}],
            },
        ),
        (
            "destination-depth-1",
            DESTINATION_TYPE_KEYS["playlist"],
            lambda typo, value: {
                "source": [{"type": "favorites"}],
                "destination": [{"type": "playlist", "id": "999", typo: value}],
            },
        ),
    ],
)
def test_random_typos_warn_at_expected_key_depth(
    monkeypatch,
    tmp_path,
    validation_logger,
    caplog,
    depth_name,
    key_pool,
    inject,
):
    """Validates typo warnings at source, modifier, and destination nesting depths."""
    del depth_name  # Used by parametrization id for readability.
    key_candidates = [key for key in sorted(key_pool) if len(key) >= 4]
    selected = RNG.choice(key_candidates)
    typo = _make_typo(selected)
    payload = {"playlists": [{"name": "depth-typo", **inject(typo, _value_for_key(selected))}]}

    monkeypatch.setattr(strategy_validation, "get_data_dir", lambda: _write_strategies(tmp_path, payload))

    with caplog.at_level("WARNING", logger="tests.strategy_validation"):
        loaded = load_strategies_with_env_overrides(validation_logger)

    assert len(loaded["playlists"]) == 1
    assert "Unknown key(s)" in caplog.text
    assert typo in caplog.text
    assert selected in caplog.text
