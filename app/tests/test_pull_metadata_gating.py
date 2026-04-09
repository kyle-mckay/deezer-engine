import logging

import pytest

from strategies.base import StrategyController
import strategies.base as strategy_base


pytestmark = [pytest.mark.unit]


def _controller(logger):
    return StrategyController(client=object(), config={"config": {}}, logger=logger, strategy_name="test")


def test_component_enrichment_runs_when_pull_metadata_enabled(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.enabled")
    controller = _controller(logger)
    calls = {"update": 0, "refresh": 0}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: True)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: True if key == "pull_metadata" else default)

    def _fake_update_unprocessed(_client, _logger):
        calls["update"] += 1

    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update_unprocessed)
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

    def _fake_update_unprocessed(_client, _logger):
        calls["update"] += 1

    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update_unprocessed)
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))
    debug_messages = []
    monkeypatch.setattr(logger, "debug", lambda message: debug_messages.append(message))

    controller._ensure_metadata_enriched_for_component("strategies.sources.album", {"type": "album"})

    assert calls["update"] == 0
    assert calls["refresh"] == 0
    assert any("pull_metadata is disabled" in msg for msg in debug_messages)


def test_component_enrichment_skipped_when_component_does_not_require_it(monkeypatch):
    logger = logging.getLogger("tests.pull_metadata.not_required")
    controller = _controller(logger)
    calls = {"update": 0, "refresh": 0}

    monkeypatch.setattr(controller, "check_requires_metadata", lambda _module_path, _config_data: False)
    monkeypatch.setattr(strategy_base, "get_global_value", lambda key, default=None: True if key == "pull_metadata" else default)

    def _fake_update_unprocessed(_client, _logger):
        calls["update"] += 1

    monkeypatch.setattr(strategy_base, "update_unprocessed", _fake_update_unprocessed)
    monkeypatch.setattr(controller, "refresh_pipeline_metadata", lambda: calls.__setitem__("refresh", calls["refresh"] + 1))

    controller._ensure_metadata_enriched_for_component("strategies.sources.album", {"type": "album"})

    assert calls["update"] == 0
    assert calls["refresh"] == 0
