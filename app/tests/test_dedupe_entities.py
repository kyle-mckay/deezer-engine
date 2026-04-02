import logging

import pytest

from utils.metadata.artists import _dedupe_entities

def _identity(entity):
    """Coerce function for plain dicts — no transformation needed."""
    return dict(entity)

@pytest.mark.unit
class TestDedupeEntitiesUnique:
    def test_single_entity_returned_unchanged(self):
        entities = [{"id": 1, "name": "A"}]
        result = _dedupe_entities(entities, _identity)
        assert result == [{"id": 1, "name": "A"}]

    def test_distinct_ids_all_returned(self):
        entities = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        result = _dedupe_entities(entities, _identity)
        assert len(result) == 2
        ids = {e["id"] for e in result}
        assert ids == {1, 2}

    def test_empty_list_returns_empty(self):
        assert _dedupe_entities([], _identity) == []

@pytest.mark.unit
class TestDedupeEntitiesMerge:
    def test_duplicate_id_merges_complementary_fields(self):
        """Two dicts with the same id and non-overlapping fields produce one merged dict."""
        entities = [
            {"id": 1, "name": "Album A", "release_date": "2020-01-01", "track_count": 10},
            {"id": 1, "name": "Album A", "genres": "Rock", "track_count": 10},
        ]
        result = _dedupe_entities(entities, _identity)
        assert len(result) == 1
        assert result[0] == {
            "id": 1,
            "name": "Album A",
            "release_date": "2020-01-01",
            "genres": "Rock",
            "track_count": 10,
        }

    def test_later_non_none_value_wins_over_earlier(self):
        """A non-None value from a later occurrence overwrites the earlier value."""
        entities = [
            {"id": 1, "name": "Old Name"},
            {"id": 1, "name": "New Name"},
        ]
        result = _dedupe_entities(entities, _identity)
        assert result[0]["name"] == "New Name"

    def test_none_value_does_not_overwrite_existing(self):
        """A None value in a later occurrence does not blank out an already-populated field."""
        entities = [
            {"id": 1, "name": "Keep Me"},
            {"id": 1, "name": None},
        ]
        result = _dedupe_entities(entities, _identity)
        assert result[0]["name"] == "Keep Me"

    def test_three_duplicates_accumulate_all_fields(self):
        entities = [
            {"id": 5, "a": 1},
            {"id": 5, "b": 2},
            {"id": 5, "c": 3},
        ]
        result = _dedupe_entities(entities, _identity)
        assert len(result) == 1
        assert result[0] == {"id": 5, "a": 1, "b": 2, "c": 3}

    def test_mixed_unique_and_duplicate(self):
        entities = [
            {"id": 1, "release_date": "2020"},
            {"id": 2, "name": "Solo"},
            {"id": 1, "genres": "Pop"},
        ]
        result = _dedupe_entities(entities, _identity)
        assert len(result) == 2
        merged = next(e for e in result if e["id"] == 1)
        assert merged == {"id": 1, "release_date": "2020", "genres": "Pop"}
        assert next(e for e in result if e["id"] == 2) == {"id": 2, "name": "Solo"}


# ---------------------------------------------------------------------------
# No-id passthrough
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDedupeEntitiesNoId:
    def test_entity_without_id_passed_through_unchanged(self):
        entities = [{"name": "No ID Entity"}]
        result = _dedupe_entities(entities, _identity)
        assert result == [{"name": "No ID Entity"}]

    def test_no_id_entities_do_not_merge_with_each_other(self):
        """Two id-less entities are kept as separate entries, not merged."""
        entities = [{"name": "X"}, {"name": "Y"}]
        result = _dedupe_entities(entities, _identity)
        assert len(result) == 2

    def test_no_id_entities_appended_after_id_entities(self):
        entities = [
            {"id": 1, "name": "Has ID"},
            {"name": "No ID"},
        ]
        result = _dedupe_entities(entities, _identity)
        assert result[-1] == {"name": "No ID"}


# ---------------------------------------------------------------------------
# coerce_fn
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDedupeEntitiesCoerceFn:
    def test_coerce_fn_is_applied_to_each_entity(self):
        """coerce_fn normalises each entity before dedup — verify it is called."""
        class Obj:
            def __init__(self, payload):
                self._p = payload
            def as_dict(self):
                return dict(self._p)

        def coerce(entity):
            if hasattr(entity, "as_dict"):
                return entity.as_dict()
            return dict(entity)

        entities = [Obj({"id": 7, "name": "From Object"})]
        result = _dedupe_entities(entities, coerce)
        assert result == [{"id": 7, "name": "From Object"}]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDedupeEntitiesLogging:
    def test_logs_received_and_result_counts(self, caplog):
        entities = [{"id": 1, "a": 1}, {"id": 1, "b": 2}]
        logger = logging.getLogger("test.dedupe")
        with caplog.at_level(logging.DEBUG, logger="test.dedupe"):
            _dedupe_entities(entities, _identity, logger=logger, entity_label="widgets")
        messages = caplog.text
        assert "2 widgets" in messages
        assert "1 out" in messages
        assert "1 merged" in messages

    def test_no_logger_does_not_raise(self):
        entities = [{"id": 1}, {"id": 1}]
        result = _dedupe_entities(entities, _identity, logger=None)
        assert len(result) == 1

    def test_entity_label_appears_in_log(self, caplog):
        logger = logging.getLogger("test.dedupe.label")
        with caplog.at_level(logging.DEBUG, logger="test.dedupe.label"):
            _dedupe_entities([{"id": 1}], _identity, logger=logger, entity_label="albums")
        assert "albums" in caplog.text
