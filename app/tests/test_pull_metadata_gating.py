import logging
import types

import pytest

from strategies.base import StrategyController
import strategies.base as strategy_base


pytestmark = [pytest.mark.unit]

_ENRICHED_TRACK = {"id": 1, "title": "Track A", "date_cached": "2026-01-01"}
_UNENRICHED_TRACK = {"id": 2, "title": "Track B", "date_cached": None}


def _controller(logger):
    return StrategyController(client=object(), config={"config": {}}, logger=logger, strategy_name="test")


def _fake_update(calls):
    def _inner(_client, _logger, track_ids=None):
        calls["update"] += 1
        calls["track_ids"] = track_ids
    return _inner


# ---------------------------------------------------------------------------
# _ensure_metadata_enriched_for_component — enrichment gating
# ---------------------------------------------------------------------------

def test_component_enrichment_runs_when_pull_metadata_enabled(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.enabled")
    controller = _controller(logger)
    controller.pipeline = [_UNENRICHED_TRACK]
    calls = {"update": 0, "refresh": 0, "track_ids": None}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: True)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: True if key == "pull_metadata" else default)
    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update(calls))
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))

    controller._ensure_metadata_enriched_for_component("strategies.sources.album", {"type": "album"})

    assert calls["update"] == 1
    assert calls["refresh"] == 1


def test_component_enrichment_skipped_when_pull_metadata_disabled(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.disabled")
    controller = _controller(logger)
    calls = {"update": 0, "refresh": 0}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: True)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: False if key == "pull_metadata" else default)
    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update(calls))
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))
    debug_messages = []
    monkeypatch.setattr(logger, "debug", lambda message: debug_messages.append(message))

    controller._ensure_metadata_enriched_for_component("strategies.sources.album", {"type": "album"})

    assert calls["update"] == 0
    assert calls["refresh"] == 0
    assert any("pull_metadata is disabled" in msg for msg in debug_messages)


def test_component_enrichment_skipped_when_all_pipeline_tracks_already_enriched(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.already_enriched")
    controller = _controller(logger)
    controller.pipeline = [_ENRICHED_TRACK, {"id": 3, "title": "Track C", "date_cached": "2026-01-02"}]
    calls = {"update": 0, "refresh": 0}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: True)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: True if key == "pull_metadata" else default)
    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update(calls))
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))

    controller._ensure_metadata_enriched_for_component("strategies.modifiers.filter", {"field": "bpm"})

    assert calls["update"] == 0
    assert calls["refresh"] == 0


def test_component_enrichment_scoped_to_unenriched_pipeline_tracks_only(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.partial_enrichment")
    controller = _controller(logger)
    controller.pipeline = [_ENRICHED_TRACK, _UNENRICHED_TRACK]
    calls = {"update": 0, "refresh": 0, "track_ids": None}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: True)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: True if key == "pull_metadata" else default)
    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update(calls))
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))

    controller._ensure_metadata_enriched_for_component("strategies.modifiers.filter", {"field": "bpm"})

    assert calls["update"] == 1
    assert calls["refresh"] == 1
    assert calls["track_ids"] == [2]


def test_component_enrichment_skipped_when_component_does_not_require_it(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.not_required")
    controller = _controller(logger)
    calls = {"update": 0, "refresh": 0}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: False)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: True if key == "pull_metadata" else default)
    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update(calls))
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))

    controller._ensure_metadata_enriched_for_component("strategies.sources.album", {"type": "album"})

    assert calls["update"] == 0
    assert calls["refresh"] == 0


# ---------------------------------------------------------------------------
# check_requires_metadata — field-based auto-detection for modifiers
# ---------------------------------------------------------------------------

def _make_module(requires_metadata_fn=None):
    """Return a minimal fake module, optionally with a requires_metadata hook."""
    mod = types.ModuleType("fake_modifier")
    if requires_metadata_fn is not None:
        mod.requires_metadata = requires_metadata_fn
    return mod


def test_modifier_no_hook_non_shallow_field_requires_enrichment(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.non_shallow")
    controller = _controller(logger)
    mod = _make_module()
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata("strategies.modifiers.sort", {"field": "bpm"})
    assert result is True


def test_modifier_no_hook_shallow_field_skips_enrichment(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.shallow")
    controller = _controller(logger)
    mod = _make_module()
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata("strategies.modifiers.sort", {"field": "artist_name"})
    assert result is False


def test_modifier_no_hook_no_field_skips_enrichment(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.no_field")
    controller = _controller(logger)
    mod = _make_module()
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata("strategies.modifiers.shuffle", {"order": "random"})
    assert result is False


def test_modifier_hook_true_forces_enrichment_regardless_of_field(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.hook_true")
    controller = _controller(logger)
    mod = _make_module(requires_metadata_fn=lambda _data=None: True)
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata("strategies.modifiers.sort", {"field": "artist_name"})
    assert result is True


def test_modifier_hook_false_skips_enrichment_regardless_of_field(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.hook_false")
    controller = _controller(logger)
    mod = _make_module(requires_metadata_fn=lambda _data=None: False)
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata("strategies.modifiers.sort", {"field": "bpm"})
    assert result is False


def test_non_modifier_no_hook_defaults_to_true(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.non_modifier")
    controller = _controller(logger)
    mod = _make_module()
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata("strategies.sources.playlist", {"type": "playlist"})
    assert result is True


def test_modifier_multiple_fields_one_non_shallow_requires_enrichment(monkeypatch):
    logger = logging.getLogger("tests.check_requires_metadata.multi_field")
    controller = _controller(logger)
    mod = _make_module()
    monkeypatch.setattr(strategy_base.importlib, "import_module", lambda _path: mod)

    result = controller.check_requires_metadata(
        "strategies.modifiers.filter", {"fields": ["artist_name", "bpm"]}
    )
    assert result is True
