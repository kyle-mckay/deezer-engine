import random

import pytest

from utils.config.key_validation import (
    CONFIG_ROOT_KEYS,
    CONFIG_SECTION_KEYS,
    DESTINATION_BASE_KEYS,
    DESTINATION_TYPE_KEYS,
    MODIFIER_BASE_KEYS,
    MODIFIER_TYPE_KEYS,
    SOURCE_BASE_KEYS,
    SOURCE_TYPE_KEYS,
    STRATEGY_TOP_LEVEL_KEYS,
    format_unknown_key_list,
    get_allowed_destination_keys,
    get_allowed_modifier_keys,
    get_allowed_source_keys,
    get_unknown_keys,
)


RNG = random.Random(20260327)


pytestmark = [pytest.mark.unit]


def _make_typo(key_name):
    if len(key_name) < 4:
        return f"{key_name}x"

    # Swap two middle characters to keep similarity high for suggestion matching.
    idx = len(key_name) // 2
    chars = list(key_name)
    chars[idx - 1], chars[idx] = chars[idx], chars[idx - 1]
    typo = "".join(chars)
    if typo == key_name:
        return f"{key_name}x"
    return typo


@pytest.mark.parametrize("source_type", sorted(SOURCE_TYPE_KEYS.keys()))
def test_allowed_source_keys_match_declared_contract(source_type):
    """Ensures allowed source keys equal base plus source-type-specific contract keys."""
    expected = SOURCE_BASE_KEYS | SOURCE_TYPE_KEYS[source_type]

    assert get_allowed_source_keys(source_type) == expected
    assert get_allowed_source_keys(source_type.upper()) == expected


@pytest.mark.parametrize("modifier_type", sorted(MODIFIER_TYPE_KEYS.keys()))
def test_allowed_modifier_keys_match_declared_contract(modifier_type):
    """Ensures allowed modifier keys equal base plus modifier-type-specific contract keys."""
    expected = MODIFIER_BASE_KEYS | MODIFIER_TYPE_KEYS[modifier_type]

    assert get_allowed_modifier_keys(modifier_type) == expected
    assert get_allowed_modifier_keys(modifier_type.upper()) == expected


@pytest.mark.parametrize("destination_type", sorted(DESTINATION_TYPE_KEYS.keys()))
def test_allowed_destination_keys_match_declared_contract(destination_type):
    """Ensures allowed destination keys equal base plus destination-type-specific keys."""
    expected = DESTINATION_BASE_KEYS | DESTINATION_TYPE_KEYS[destination_type]

    assert get_allowed_destination_keys(destination_type) == expected
    assert get_allowed_destination_keys(destination_type.upper()) == expected


def test_unknown_type_falls_back_to_base_key_sets():
    """Confirms unknown types safely fall back to base key sets only."""
    assert get_allowed_source_keys("no-such-source") == SOURCE_BASE_KEYS
    assert get_allowed_modifier_keys("no-such-modifier") == MODIFIER_BASE_KEYS
    assert get_allowed_destination_keys("no-such-destination") == DESTINATION_BASE_KEYS


@pytest.mark.parametrize(
    "allowed_keys",
    [
        CONFIG_ROOT_KEYS,
        CONFIG_SECTION_KEYS,
        STRATEGY_TOP_LEVEL_KEYS,
        SOURCE_BASE_KEYS,
        MODIFIER_BASE_KEYS,
        DESTINATION_BASE_KEYS,
    ],
)
def test_random_typos_are_detected_as_unknown_keys(allowed_keys):
    """Checks typoed keys are flagged while valid keys in the same payload are accepted."""
    allowed_list = sorted(allowed_keys)
    picked = RNG.choice(allowed_list)
    typo = _make_typo(picked)
    payload = {picked: True, typo: True}

    unknown = get_unknown_keys(payload, allowed_keys)

    assert picked not in unknown
    assert typo in unknown


@pytest.mark.parametrize(
    "allowed_keys",
    [
        SOURCE_BASE_KEYS | SOURCE_TYPE_KEYS["history"],
        MODIFIER_BASE_KEYS | MODIFIER_TYPE_KEYS["filter"],
        DESTINATION_BASE_KEYS | DESTINATION_TYPE_KEYS["playlist"],
        CONFIG_SECTION_KEYS,
    ],
)
def test_unknown_key_formatting_suggests_expected_key(allowed_keys):
    """Verifies unknown-key formatter includes a suggestion for close misspellings."""
    key_candidates = [key for key in sorted(allowed_keys) if len(key) >= 4]
    selected = RNG.choice(key_candidates)
    typo = _make_typo(selected)

    formatted = format_unknown_key_list([typo], allowed_keys)

    assert typo in formatted
    assert "did you mean" in formatted
    assert selected in formatted


@pytest.mark.parametrize("source_type", ["album", "artist", "playlist"])
def test_id_based_source_contract_does_not_add_ids_key(source_type):
    """Confirms multi-ID support stays on the existing id key rather than adding ids."""
    allowed = get_allowed_source_keys(source_type)

    assert "id" in allowed
    assert "ids" not in allowed
