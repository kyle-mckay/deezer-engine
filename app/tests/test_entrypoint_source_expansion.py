import logging

import pytest

import entrypoint


pytestmark = [pytest.mark.unit]


def test_process_sources_expands_multi_id_sources(monkeypatch):
    """Expands list-based source shorthand into one grouped source block."""
    logger = logging.getLogger("tests.entrypoint.source_expansion")
    handled_sources = []

    class Controller:
        def handle_source(self, source_data, source_name=None):
            handled_sources.append((dict(source_data), source_name))
            return [{"id": source_data["id"], "collection": source_name}]

    monkeypatch.setattr(
        entrypoint,
        "shutdown_event",
        type("ShutdownEvent", (), {"is_set": staticmethod(lambda: False)})(),
    )
    monkeypatch.setattr(
        entrypoint,
        "get_collection_name",
        lambda _logger, source_type, name=None, id=None: f"{source_type}__{id or name}",
    )

    source_metadata = entrypoint.process_sources(
        {
            "source": [
                {
                    "type": "track",
                    "id": ["123", "456"],
                    "retention": 6,
                    "modifiers": [{"type": "dedupe"}],
                }
            ]
        },
        Controller(),
        config={},
        client=object(),
        logger=logger,
        strategy_name="expansion-test",
    )

    assert source_metadata == [
        {
            "source": {
                "type": "track",
                "id": ["123", "456"],
                "retention": 6,
                "modifiers": [{"type": "dedupe"}],
            },
            "expanded_sources": [
                {
                    "type": "track",
                    "id": "123",
                    "retention": 6,
                    "modifiers": [{"type": "dedupe"}],
                },
                {
                    "type": "track",
                    "id": "456",
                    "retention": 6,
                    "modifiers": [{"type": "dedupe"}],
                },
            ],
            "collection_names": ["track__123", "track__456"],
            "group_name": "track__grouped__0",
            "modifiers": [{"type": "dedupe"}],
            "tracks": [
                {"id": "123", "collection": "track__123"},
                {"id": "456", "collection": "track__456"},
            ],
        }
    ], f"Expected one grouped source block, got: {source_metadata}"
    assert handled_sources == [
        (
            {
                "type": "track",
                "id": "123",
                "retention": 6,
                "modifiers": [{"type": "dedupe"}],
            },
            "track__123",
        ),
        (
            {
                "type": "track",
                "id": "456",
                "retention": 6,
                "modifiers": [{"type": "dedupe"}],
            },
            "track__456",
        ),
    ], f"Expected handle_source to receive one scalarized source per id, got: {handled_sources}"


def test_process_sources_aggregates_mixed_controller_results(monkeypatch):
    logger = logging.getLogger("tests.entrypoint.source_expansion.cache")
    handled_sources = []

    class Controller:
        def handle_source(self, source_data, source_name=None):
            handled_sources.append((dict(source_data), source_name))
            if source_name == "track__123":
                return [{"id": f"cached-{source_name}", "collection": source_name}]
            return [{"id": f"live-{source_data['id']}", "collection": source_name}]

    monkeypatch.setattr(
        entrypoint,
        "shutdown_event",
        type("ShutdownEvent", (), {"is_set": staticmethod(lambda: False)})(),
    )
    monkeypatch.setattr(
        entrypoint,
        "get_collection_name",
        lambda _logger, source_type, name=None, id=None: f"{source_type}__{id or name}",
    )

    source_metadata = entrypoint.process_sources(
        {
            "source": [
                {
                    "type": "track",
                    "id": ["123", "456"],
                    "retention": 6,
                }
            ]
        },
        Controller(),
        config={},
        client=object(),
        logger=logger,
        strategy_name="cache-mix-test",
    )

    assert source_metadata[0]["tracks"] == [
        {"id": "cached-track__123", "collection": "track__123"},
        {"id": "live-456", "collection": "track__456"},
    ]
    assert handled_sources == [
        ({"type": "track", "id": "123", "retention": 6}, "track__123"),
        ({"type": "track", "id": "456", "retention": 6}, "track__456")
    ]


def test_process_sources_validates_grouped_output_total_once(monkeypatch):
    logger = logging.getLogger("tests.entrypoint.source_expansion.grouped_validation")
    handled_sources = []
    validation_calls = []

    class Controller:
        def handle_source(self, source_data, source_name=None):
            handled_sources.append((dict(source_data), source_name))
            if source_name == "album__123":
                return [{"id": "a1", "collection": source_name}, {"id": "a2", "collection": source_name}]
            return [{"id": "b1", "collection": source_name}]

        def _validate_io(self, stage, expected, actual, mode, label):
            validation_calls.append((stage, expected, actual, mode, label))

    monkeypatch.setattr(
        entrypoint,
        "shutdown_event",
        type("ShutdownEvent", (), {"is_set": staticmethod(lambda: False)})(),
    )
    monkeypatch.setattr(
        entrypoint,
        "get_collection_name",
        lambda _logger, source_type, name=None, id=None: f"{source_type}__{id or name}",
    )

    source_metadata = entrypoint.process_sources(
        {
            "source": [
                {
                    "type": "album",
                    "id": ["123", "456"],
                    "o": 3,
                    "validation_mode": "warn",
                }
            ]
        },
        Controller(),
        config={},
        client=object(),
        logger=logger,
        strategy_name="grouped-output-validation",
    )

    assert source_metadata[0]["tracks"] == [
        {"id": "a1", "collection": "album__123"},
        {"id": "a2", "collection": "album__123"},
        {"id": "b1", "collection": "album__456"},
    ]
    assert handled_sources == [
        ({"type": "album", "id": "123", "o": 3, "validation_mode": "warn"}, "album__123"),
        ({"type": "album", "id": "456", "o": 3, "validation_mode": "warn"}, "album__456"),
    ]
    assert validation_calls == [
        ('o', 3, 3, 'warn', "Source 'album'"),
    ]


def test_process_modifiers_uses_grouped_in_memory_tracks(monkeypatch):
    logger = logging.getLogger("tests.entrypoint.source_expansion.modifiers")
    modifier_calls = []

    class Controller:
        def __init__(self):
            self.pipeline = []

        def handle_modifier(self, mod_data, tracks_override=None, source_name=None):
            modifier_calls.append((dict(mod_data), list(tracks_override) if tracks_override is not None else None, source_name))
            if tracks_override is None:
                self.pipeline = list(reversed(self.pipeline))
                return self.pipeline
            return tracks_override[:2]

    monkeypatch.setattr(
        entrypoint,
        "shutdown_event",
        type("ShutdownEvent", (), {"is_set": staticmethod(lambda: False)})(),
    )

    controller = Controller()
    entrypoint.process_modifiers(
        {
            "modifiers": [{"type": "reverse"}],
        },
        controller,
        [
            {
                "group_name": "playlist__grouped__0",
                "modifiers": [{"type": "limit", "count": 2}],
                "tracks": [
                    {"id": "1", "collection": "playlist__111"},
                    {"id": "2", "collection": "playlist__222"},
                    {"id": "3", "collection": "playlist__222"},
                ],
            }
        ],
        logger,
        "modifier-group-test",
    )

    assert modifier_calls == [
        (
            {"type": "limit", "count": 2},
            [
                {"id": "1", "collection": "playlist__111"},
                {"id": "2", "collection": "playlist__222"},
                {"id": "3", "collection": "playlist__222"},
            ],
            "playlist__grouped__0",
        ),
        ({"type": "reverse"}, None, "playlist__grouped__0"),
    ]
    assert controller.pipeline == [
        {"id": "2", "collection": "playlist__222"},
        {"id": "1", "collection": "playlist__111"},
    ]