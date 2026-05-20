# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

import pytest

import strategies.modifiers.interleave as interleave_mod

pytestmark = [pytest.mark.unit]

_LOGGER = logging.getLogger("tests.interleave_modifier")


def _tracks(*ids):
    return [{"id": str(i)} for i in ids]


def _mod_data(inject_groups, continue_on_exhaust=None):
    mod = {"type": "interleave", "inject": inject_groups}
    if continue_on_exhaust is not None:
        mod["continue_on_exhaust"] = continue_on_exhaust
    return mod


def _inject_entry(track_ids, every=1, add=1, continue_on_exhaust=None):
    entry = {"source": {"type": "playlist", "id": "fake"}, "every": every, "add": add}
    if continue_on_exhaust is not None:
        entry["continue_on_exhaust"] = continue_on_exhaust
    entry["_resolved_tracks"] = _tracks(*track_ids)
    return entry


def _patch_fetch(monkeypatch, inject_entries):
    """Patch _fetch_inject_tracks to return pre-resolved tracks from each entry in order."""
    calls = iter(inject_entries)

    def fake_fetch(client, config, logger, source_data):
        return next(calls)["_resolved_tracks"]

    monkeypatch.setattr(interleave_mod, "_fetch_inject_tracks", fake_fetch)


# ---------------------------------------------------------------------------
# No-op / guard cases
# ---------------------------------------------------------------------------

class TestInterleaveGuards:
    def test_empty_inject_list_returns_pipeline_unchanged(self, monkeypatch):
        origin = _tracks("o1", "o2")
        result = interleave_mod.run(None, {}, _LOGGER, {"type": "interleave", "inject": []}, origin)
        assert result == origin

    def test_missing_source_in_entry_is_skipped_and_returns_unchanged(self, monkeypatch):
        monkeypatch.setattr(interleave_mod, "_fetch_inject_tracks", lambda *_: pytest.fail("should not be called"))
        origin = _tracks("o1")
        result = interleave_mod.run(
            None, {}, _LOGGER,
            _mod_data([{"every": 1, "add": 1}]),  # no 'source' key
            origin,
        )
        assert result == origin


# ---------------------------------------------------------------------------
# Standalone / append mode (empty origin)
# ---------------------------------------------------------------------------

class TestInterleaveStandaloneMode:
    def test_empty_origin_appends_all_inject_tracks(self, monkeypatch):
        entries = [_inject_entry(["w1", "w2"]), _inject_entry(["f1"])]
        _patch_fetch(monkeypatch, entries)
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), [])
        assert [t["id"] for t in result] == ["w1", "w2", "f1"]

    def test_empty_origin_preserves_inject_group_order(self, monkeypatch):
        entries = [_inject_entry(["a1", "a2"]), _inject_entry(["b1"])]
        _patch_fetch(monkeypatch, entries)
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), [])
        assert result[0]["id"] == "a1"
        assert result[-1]["id"] == "b1"


# ---------------------------------------------------------------------------
# Basic interleave — single inject group
# ---------------------------------------------------------------------------

class TestInterleaveBasic:
    def test_every_2_add_1_interleaves_correctly(self, monkeypatch):
        entries = [_inject_entry(["w1", "w2"], every=2, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        assert [t["id"] for t in result] == ["o1", "o2", "w1", "o3", "o4", "w2"]

    def test_every_1_add_1_inserts_after_each_origin_track(self, monkeypatch):
        entries = [_inject_entry(["w1", "w2", "w3"], every=1, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        assert [t["id"] for t in result] == ["o1", "w1", "o2", "w2", "o3", "w3"]

    def test_every_1_add_2_inserts_two_after_each_origin(self, monkeypatch):
        entries = [_inject_entry(["w1", "w2", "w3", "w4"], every=1, add=2)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        assert [t["id"] for t in result] == ["o1", "w1", "w2", "o2", "w3", "w4"]

    def test_origin_count_is_not_inflated_by_injected_tracks(self, monkeypatch):
        # every=2 must count origin tracks only, not injected ones
        entries = [_inject_entry(["w1", "w2", "w3"], every=2, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4", "o5", "o6")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        assert [t["id"] for t in result] == ["o1", "o2", "w1", "o3", "o4", "w2", "o5", "o6", "w3"]


# ---------------------------------------------------------------------------
# Multiple inject groups
# ---------------------------------------------------------------------------

class TestInterleaveMultipleGroups:
    def test_two_groups_inject_at_different_intervals(self, monkeypatch):
        entries = [
            _inject_entry(["w1", "w2", "w3"], every=2, add=1),
            _inject_entry(["f1", "f2", "f3"], every=3, add=1),
        ]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4", "o5", "o6")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        ids = [t["id"] for t in result]
        # After o2: w1 injected; after o3: f1 injected; after o4: w2; after o6: w3 + f2
        assert "w1" in ids and "f1" in ids
        assert ids.index("o2") < ids.index("w1") < ids.index("o3")
        assert ids.index("o3") < ids.index("f1") < ids.index("o4")

    def test_two_groups_same_interval_both_inject_in_definition_order(self, monkeypatch):
        entries = [
            _inject_entry(["w1"], every=2, add=1),
            _inject_entry(["f1"], every=2, add=1),
        ]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries, continue_on_exhaust=True), origin)
        ids = [t["id"] for t in result]
        # After o2: w1 then f1 (group A before group B)
        assert ids.index("w1") < ids.index("f1")
        assert ids.index("o2") < ids.index("w1")
        assert ids.index("f1") < ids.index("o3")


# ---------------------------------------------------------------------------
# Inject source exhaustion (per-item continue_on_exhaust)
# ---------------------------------------------------------------------------

class TestInjectExhaustion:
    def test_partial_batch_injected_when_continue_on_exhaust_true(self, monkeypatch):
        # Source has 3 tracks; every=2 add=2 means 3rd cycle gets only 1 track
        entries = [_inject_entry(["w1", "w2", "w3"], every=2, add=2, continue_on_exhaust=True)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4", "o5", "o6")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        ids = [t["id"] for t in result]
        # Cycle 1 (after o2): w1, w2 injected; cycle 2 (after o4): w3 (partial) injected
        assert "w1" in ids and "w2" in ids and "w3" in ids

    def test_partial_batch_discarded_when_continue_on_exhaust_false(self, monkeypatch):
        # Source has 3 tracks; every=2 add=2 → 3rd cycle can't fill, discard
        entries = [_inject_entry(["w1", "w2", "w3"], every=2, add=2, continue_on_exhaust=False)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4", "o5", "o6")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        ids = [t["id"] for t in result]
        assert "w1" in ids and "w2" in ids
        assert "w3" not in ids

    def test_exhausted_group_stops_injecting_on_subsequent_cycles(self, monkeypatch):
        entries = [_inject_entry(["w1"], every=1, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        ids = [t["id"] for t in result]
        # Only one w1 — group stops after first injection
        assert ids.count("w1") == 1


# ---------------------------------------------------------------------------
# Origin exhaustion (top-level continue_on_exhaust)
# ---------------------------------------------------------------------------

class TestOriginExhaustion:
    def test_remaining_inject_tracks_appended_when_top_continue_true(self, monkeypatch):
        # Origin has 2 tracks, inject has 5 — leftover after interleave should be appended
        entries = [_inject_entry(["w1", "w2", "w3", "w4", "w5"], every=1, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries, continue_on_exhaust=True), origin)
        ids = [t["id"] for t in result]
        assert "w3" in ids and "w4" in ids and "w5" in ids

    def test_remaining_inject_tracks_discarded_when_top_continue_false(self, monkeypatch):
        entries = [_inject_entry(["w1", "w2", "w3", "w4", "w5"], every=1, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries, continue_on_exhaust=False), origin)
        ids = [t["id"] for t in result]
        assert "w3" not in ids and "w4" not in ids and "w5" not in ids

    def test_origin_stops_when_inject_exhausts_and_top_continue_false(self, monkeypatch):
        # inject has 2 tracks (every=1), origin has 5 — with continue_on_exhaust=False
        # origin must stop as soon as inject is exhausted (after o2)
        entries = [_inject_entry(["w1", "w2"], every=1, add=1)]
        _patch_fetch(monkeypatch, entries)
        origin = _tracks("o1", "o2", "o3", "o4", "o5")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries, continue_on_exhaust=False), origin)
        ids = [t["id"] for t in result]
        assert ids == ["o1", "w1", "o2", "w2"]
        assert "o3" not in ids and "o4" not in ids and "o5" not in ids

    def test_top_continue_false_is_default(self, monkeypatch):
        entries = [_inject_entry(["w1"], every=2, add=1)]
        _patch_fetch(monkeypatch, entries)
        monkeypatch.setattr(interleave_mod, "get_global_value", lambda _key, default=None: default)
        origin = _tracks("o1", "o2", "o3", "o4")
        result = interleave_mod.run(None, {}, _LOGGER, _mod_data(entries), origin)
        ids = [t["id"] for t in result]
        # inject exhausts after o2+w1; with default false, origin stops there
        assert ids == ["o1", "o2", "w1"]


# ---------------------------------------------------------------------------
# Source fetching delegation
# ---------------------------------------------------------------------------

class TestInjectSourceFetching:
    def test_cached_source_is_used_when_available(self, monkeypatch):
        fetched_live = []

        monkeypatch.setattr(
            interleave_mod,
            "get_collection_name",
            lambda *_args, **_kwargs: "playlist__123",
        )
        monkeypatch.setattr(
            interleave_mod,
            "is_collection_cached",
            lambda *_args, **_kwargs: True,
        )
        monkeypatch.setattr(
            interleave_mod,
            "fetch_collection",
            lambda _name, _logger: _tracks("cached1", "cached2"),
        )
        monkeypatch.setattr(
            interleave_mod,
            "sync_to_collections",
            lambda *_: fetched_live.append("synced"),
        )

        result = interleave_mod._fetch_inject_tracks(
            None, {}, _LOGGER, {"type": "playlist", "id": "123"}
        )
        assert [t["id"] for t in result] == ["cached1", "cached2"]
        assert not fetched_live

    def test_live_source_fetched_and_synced_when_not_cached(self, monkeypatch):
        synced = []
        fake_source_module = type("FakeSource", (), {
            "run": staticmethod(lambda *_args, **_kwargs: _tracks("live1", "live2")),
        })

        monkeypatch.setattr(
            interleave_mod,
            "get_collection_name",
            lambda *_args, **_kwargs: "playlist__456",
        )
        monkeypatch.setattr(
            interleave_mod,
            "is_collection_cached",
            lambda *_args, **_kwargs: False,
        )
        monkeypatch.setattr(
            interleave_mod,
            "importlib",
            type("FakeImportlib", (), {
                "import_module": staticmethod(lambda _path: fake_source_module),
            }),
        )
        monkeypatch.setattr(
            interleave_mod,
            "sync_to_collections",
            lambda tracks, logger: synced.extend(tracks),
        )

        result = interleave_mod._fetch_inject_tracks(
            None, {}, _LOGGER, {"type": "playlist", "id": "456"}
        )
        assert [t["id"] for t in result] == ["live1", "live2"]
        assert len(synced) == 2


# ---------------------------------------------------------------------------
# requires_metadata
# ---------------------------------------------------------------------------

class TestRequiresMetadata:
    def test_returns_false_unconditionally(self):
        assert interleave_mod.requires_metadata() is False
        assert interleave_mod.requires_metadata({"inject": []}) is False
