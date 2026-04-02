import logging
from pathlib import Path

import pytest

from strategies.sources import file as file_source
from strategies.sources import history, smarttracklist
from strategies.sources import artist, album
from utils.infrastructure.signals import shutdown_event


pytestmark = [pytest.mark.unit]


def test_smarttracklist_delegates_to_track_worker(monkeypatch):
    logger = logging.getLogger("tests.source_delegation.smarttracklist")
    delegated = {}

    monkeypatch.setattr(smarttracklist, "get_cache_dir", lambda: Path("/tmp"))
    monkeypatch.setattr(
        smarttracklist,
        "get_collection_name",
        lambda _logger, _source_type, name=None, **_kwargs: (
            "smarttracklist__merged"
            if isinstance(name, list)
            else f"smarttracklist__{name}"
        ),
    )
    monkeypatch.setattr(
        smarttracklist,
        "handle_cached_data",
        lambda _cache_file, _retention, _logger, _fetch_fn, _cache_type, collection_name=None: [
            {"id": "101", "collection": collection_name},
            {"id": "102", "collection": collection_name},
            {"id": "101", "collection": collection_name},
        ],
    )

    def fake_fetch_enriched_tracks(client, config, logger, source_data):
        delegated["client"] = client
        delegated["config"] = config
        delegated["source_data"] = source_data
        return [{"id": "101", "collection": source_data[0]["override_collection"]}]

    monkeypatch.setattr(smarttracklist, "fetch_enriched_tracks", fake_fetch_enriched_tracks)

    result = smarttracklist.run(
        client=object(),
        config={"config": {"arl_token": "secret-token"}},
        logger=logger,
        source_data={"type": "smarttracklist", "name": ["discovery", "new-releases"], "retention": 6},
    )

    assert result == [{"id": "101", "collection": "smarttracklist__merged"}]
    assert delegated["source_data"] == [{
        "id": ["101", "102"],
        "override_collection": "smarttracklist__merged",
        "retention": 6,
    }]


def test_history_delegates_to_track_worker(monkeypatch):
    logger = logging.getLogger("tests.source_delegation.history")
    delegated = {}

    monkeypatch.setattr(history, "get_collection_name", lambda *_args, **_kwargs: "history__default")
    monkeypatch.setattr(history, "time", type("HistoryTime", (), {"time": staticmethod(lambda: 1_700_000_000)}))
    monkeypatch.setattr(
        history,
        "get_deezer_history",
        lambda _limit, _logger: [
            {"SNG_ID": "301", "TS": 1_700_000_000},
            {"SNG_ID": "302", "TS": 1_699_999_000},
            {"SNG_ID": "301", "TS": 1_700_000_000},
            {"SNG_ID": "303", "TS": 1},
        ],
    )

    def fake_fetch_enriched_tracks(client, config, logger, source_data):
        delegated["source_data"] = source_data
        return [{"id": "301", "collection": source_data[0]["override_collection"]}]

    monkeypatch.setattr(history, "fetch_enriched_tracks", fake_fetch_enriched_tracks)

    result = history.run(
        client=object(),
        config={},
        logger=logger,
        source_data={"type": "history", "lookback": 1, "limit": 10, "retention": 12},
    )

    assert result == [{"id": "301", "collection": "history__default"}]
    assert delegated["source_data"] == [{
        "id": ["301", "302"],
        "override_collection": "history__default",
        "retention": 12,
    }]


def test_file_delegates_to_track_worker(monkeypatch, tmp_path):
    logger = logging.getLogger("tests.source_delegation.file")
    delegated = {}

    monkeypatch.setattr(file_source, "get_collection_name", lambda *_args, **_kwargs: "file__merged")
    monkeypatch.setattr(
        file_source,
        "read_from_json",
        lambda _path, _logger: [{"id": "401"}, {"id": "402"}],
    )
    monkeypatch.setattr(
        file_source,
        "read_from_csv",
        lambda _path, _logger: [{"id": "402"}, {"id": "403"}],
    )

    def fake_fetch_enriched_tracks(client, config, logger, source_data):
        delegated["source_data"] = source_data
        return [{"id": "401", "collection": source_data[0]["override_collection"]}]

    monkeypatch.setattr(file_source, "fetch_enriched_tracks", fake_fetch_enriched_tracks)

    result = file_source.run(
        client=object(),
        config={},
        logger=logger,
        source_data={
            "type": "file",
            "filename": [str(tmp_path / "tracks.json"), str(tmp_path / "tracks.csv")],
        },
    )

    assert result == [{"id": "401", "collection": "file__merged"}]
    assert delegated["source_data"] == [{
        "id": ["401", "402", "403"],
        "override_collection": "file__merged",
    }]


def test_album_source_honors_shutdown_before_fetch(monkeypatch):
    logger = logging.getLogger("tests.source_delegation.album_shutdown")

    calls = {"get_album": 0}

    class DummyClient:
        def get_album(self, _album_id):
            calls["get_album"] += 1
            raise AssertionError("get_album should not be called when shutdown is active")

    shutdown_event.set()
    try:
        result = album.run(
            client=DummyClient(),
            config={},
            logger=logger,
            source_data={"type": "album", "id": ["111", "222"]},
        )
    finally:
        shutdown_event.clear()

    assert result == []
    assert calls["get_album"] == 0


def test_artist_source_honors_shutdown_before_artist_lookup(monkeypatch):
    logger = logging.getLogger("tests.source_delegation.artist_shutdown")

    calls = {"get_artist": 0}

    class DummyClient:
        def get_artist(self, _artist_id):
            calls["get_artist"] += 1
            raise AssertionError("get_artist should not be called when shutdown is active")

    shutdown_event.set()
    try:
        result = artist.run(
            client=DummyClient(),
            config={},
            logger=logger,
            source_data={"type": "artist", "id": ["333", "444"]},
        )
    finally:
        shutdown_event.clear()

    assert result == []
    assert calls["get_artist"] == 0