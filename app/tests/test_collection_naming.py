import logging

import pytest

from utils.collections import get_collection_name


pytestmark = [pytest.mark.unit]


def test_get_collection_name_does_not_join_list_ids(caplog):
    """Uses the first valid list id and logs that fan-out should happen before naming."""
    logger = logging.getLogger("tests.collection_naming")

    with caplog.at_level("WARNING", logger=logger.name):
        collection_name = get_collection_name(logger, "track", id=["123", "456"])

    assert collection_name == "track__123", (
        f"Expected list id input to resolve to the first scalar collection name, got: {collection_name}"
    )
    assert "using the first valid value '123'" in caplog.text, (
        f"Expected warning log to explain scalar fallback for list ids, got: {caplog.text}"
    )