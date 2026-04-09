import logging
from pathlib import Path

import pytest

from strategies.sources import file as file_source
from strategies.sources import history, smarttracklist


pytestmark = [pytest.mark.unit]


def _complete_shallow_track(track_id, **overrides):
    track = {
        "id": str(track_id),
        "readable": True,
        "title": f"Track {track_id}",
        "link": f"https://example.test/tracks/{track_id}",
        "duration": 180,
        "rank": 999,
        "explicit_lyrics": False,
        "explicit_content_lyrics": 0,
        "explicit_content_cover": 0,
        "md5_image": f"img-{track_id}",
        "artist_id": f"artist-{track_id}",
        "artist_name": f"Artist {track_id}",
        "album_id": f"album-{track_id}",
        "album_name": f"Album {track_id}",
    }
    track.update(overrides)
    return track


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
    ingested = []

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

    def fake_ingest_shallow_tracks(tracklist, logger, skip_fully_populated=False):
        del logger, skip_fully_populated
        ingested.append(list(tracklist))
        return list(tracklist)

    monkeypatch.setattr(file_source, "fetch_enriched_tracks", fake_fetch_enriched_tracks)
    monkeypatch.setattr(file_source, "ingest_shallow_tracks", fake_ingest_shallow_tracks)

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
    assert ingested == [[{"id": "401", "collection": "file__merged"}]]


def test_file_passes_complete_rows_through_shallow_ingestion_without_delegation(monkeypatch, tmp_path):
    logger = logging.getLogger("tests.source_delegation.file_complete")
    ingested = []

    monkeypatch.setattr(file_source, "get_collection_name", lambda *_args, **_kwargs: "file__merged")
    monkeypatch.setattr(
        file_source,
        "read_from_json",
        lambda _path, _logger: [
            _complete_shallow_track(
                "501",
                collection="should_not_override",
                date_cached="2026-04-02T00:00:00",
                disk_number=7,
            )
        ],
    )

    def fake_ingest_shallow_tracks(tracklist, logger, skip_fully_populated=False):
        del logger, skip_fully_populated
        ingested.append(list(tracklist))
        return list(tracklist)

    monkeypatch.setattr(
        file_source,
        "fetch_enriched_tracks",
        lambda *_args, **_kwargs: pytest.fail("fetch_enriched_tracks should not run for complete shallow rows"),
    )
    monkeypatch.setattr(file_source, "ingest_shallow_tracks", fake_ingest_shallow_tracks)

    result = file_source.run(
        client=object(),
        config={},
        logger=logger,
        source_data={
            "type": "file",
            "filename": [str(tmp_path / "tracks.json")],
        },
    )

    expected_track = _complete_shallow_track("501", collection="should_not_override")
    assert ingested == [[expected_track]]
    assert result == [expected_track]


def test_file_splits_complete_and_incomplete_rows(monkeypatch, tmp_path):
    logger = logging.getLogger("tests.source_delegation.file_split")
    delegated = {}
    ingested = []

    monkeypatch.setattr(file_source, "get_collection_name", lambda *_args, **_kwargs: "file__merged")
    monkeypatch.setattr(
        file_source,
        "read_from_json",
        lambda _path, _logger: [
            _complete_shallow_track("601", date_cached="2026-04-02T00:00:00", disk_number=3),
            {"id": "602"},
        ],
    )

    def fake_fetch_enriched_tracks(client, config, logger, source_data):
        del client, config, logger
        delegated["source_data"] = source_data
        return [_complete_shallow_track("602", collection=source_data[0]["override_collection"], disk_number=9)]

    def fake_ingest_shallow_tracks(tracklist, logger, skip_fully_populated=False):
        del logger, skip_fully_populated
        ingested.append(list(tracklist))
        return list(tracklist)

    monkeypatch.setattr(file_source, "fetch_enriched_tracks", fake_fetch_enriched_tracks)
    monkeypatch.setattr(file_source, "ingest_shallow_tracks", fake_ingest_shallow_tracks)

    result = file_source.run(
        client=object(),
        config={},
        logger=logger,
        source_data={
            "type": "file",
            "filename": [str(tmp_path / "tracks.json")],
        },
    )

    expected_good_track = _complete_shallow_track("601", collection="file__merged")
    expected_delegated_track = _complete_shallow_track("602", collection="file__merged", disk_number=9)
    assert delegated["source_data"] == [{
        "id": ["602"],
        "override_collection": "file__merged",
    }]
    assert ingested == [
        [expected_good_track],
        [expected_delegated_track],
    ]
    assert result == [expected_good_track, expected_delegated_track]