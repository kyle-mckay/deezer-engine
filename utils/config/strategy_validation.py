# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import yaml
from utils.infrastructure.paths import get_data_dir
from .key_validation import (
    STRATEGY_TOP_LEVEL_KEYS,
    format_unknown_key_list,
    get_allowed_destination_keys,
    get_allowed_modifier_keys,
    get_allowed_source_keys,
    get_unknown_keys,
)


def _validate_modifiers(logger, strategy_name, modifiers, depth=1, path="root"):
    """
    Validates modifiers. If a modifier contains a source (like 'exclude'),
    it triggers a recursive call back to _validate_sources.
    """
    if not isinstance(modifiers, list):
        logger.error(f"[Depth: {depth}] Strategy '{strategy_name}' at {path}: Modifiers must be a list.")
        return False

    vtype = "Modifier"
    logger.debug(f"[Depth: {depth}] Modifiers found for validation: {len(modifiers)}")
    for idx, mod in enumerate(modifiers):
        if not isinstance(mod, dict):
            logger.error(
                f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] "
                f"Strategy '{strategy_name}' at {path}: Modifier must be an object."
            )
            return False

        mod_type = str(mod.get("type", "unknown")).lower()
        current_path = f"{path} > modifier[{mod_type}]"

        logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Validating {current_path}")

        allowed_keys = get_allowed_modifier_keys(mod_type)
        unknown_keys = get_unknown_keys(mod, allowed_keys)
        if unknown_keys:
            formatted_keys = format_unknown_key_list(unknown_keys, allowed_keys)
            logger.warning(
                f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Strategy '{strategy_name}' "
                f"at {current_path}: Unknown key(s): {formatted_keys}."
            )

        if "type" not in mod:
            logger.error(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Strategy '{strategy_name}' at {current_path}: Missing 'type'.")
            return False

        # Recursion: Modifier contains a nested source
        if "source" in mod:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Found child source in {mod_type}. Recursing...")
            child_source = mod["source"]
            # Normalize single source dict to a list for the validator
            source_to_validate = child_source if isinstance(child_source, list) else [child_source]

            if not _validate_sources(logger, strategy_name, source_to_validate, depth=depth + 1, path=current_path):
                return False
        else:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Found no nested source in {mod_type}.")
    return True


def _validate_sources(logger, strategy_name, sources, depth=1, path="root"):
    """
    Validates sources. If a source contains nested modifiers,
    it triggers a recursive call back to _validate_modifiers.
    """
    if not sources or not isinstance(sources, list):
        logger.error(f"[Depth: {depth}] Strategy '{strategy_name}' at {path}: Missing or invalid 'source' list.")
        return False
    vtype = "Source"
    logger.debug(f"[Depth: {depth}] Sources found for validation: {len(sources)}")
    for idx, source in enumerate(sources):
        if not isinstance(source, dict):
            logger.error(
                f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] "
                f"Strategy '{strategy_name}' at {path}: Source must be an object."
            )
            return False

        source_type = str(source.get("type", "unknown")).lower()
        current_path = f"{path} > source[{source_type}]"

        logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Validating {current_path}")

        allowed_keys = get_allowed_source_keys(source_type)
        unknown_keys = get_unknown_keys(source, allowed_keys)
        if unknown_keys:
            formatted_keys = format_unknown_key_list(unknown_keys, allowed_keys)
            logger.warning(
                f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Strategy '{strategy_name}' "
                f"at {current_path}: Unknown key(s): {formatted_keys}."
            )

        if "type" not in source:
            logger.error(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Strategy '{strategy_name}' at {current_path}: Missing 'type'.")
            return False

        # Recursion: Source contains nested modifiers
        if "modifiers" in source:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Found nested modifiers in {source_type}. Recursing...")
            if not _validate_modifiers(logger, strategy_name, source["modifiers"], depth=depth + 1, path=current_path):
                return False
        else:
            logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Found no nested modifiers in {source_type}.")

    return True


def _validate_destination(logger, strategy_name, destination):
    """Validates the destination block."""
    path = "root > destination"
    if not destination or not isinstance(destination, list):
        logger.error(f"[Depth: 1] Strategy '{strategy_name}' at {path}: Missing or invalid list.")
        return False

    if len(destination) != 1:
        logger.warning(f"[Depth: 1] Strategy '{strategy_name}' at {path}: Expected 1, found {len(destination)}.")

    for idx, dest in enumerate(destination):
        if not isinstance(dest, dict):
            logger.error(
                f"[Depth: 1] Strategy '{strategy_name}' at {path}: Destination #{idx + 1} must be an object."
            )
            return False

        dest_type = str(dest.get("type", "unknown")).lower()
        current_path = f"{path} > destination[{dest_type}]"
        allowed_keys = get_allowed_destination_keys(dest_type)
        unknown_keys = get_unknown_keys(dest, allowed_keys)
        if unknown_keys:
            formatted_keys = format_unknown_key_list(unknown_keys, allowed_keys)
            logger.warning(
                f"[Depth: 1] Strategy '{strategy_name}' at {current_path}: "
                f"Unknown key(s): {formatted_keys}."
            )

    if "type" not in destination[0]:
        logger.error(f"[Depth: 1] Strategy '{strategy_name}' at {path}: Missing 'type'.")
        return False

    logger.debug(f"[Depth: 1] {path} verified.")
    return True


def load_strategies_with_env_overrides(logger):
    """
    Load strategies.yml, verify the schema recursively, and apply overrides.
    """
    data_dir = get_data_dir()
    strategies_path = data_dir / 'strategies.yml'

    logger.debug(f"Attempting to load strategies from {strategies_path}")

    try:
        with open(strategies_path, 'r') as f:
            strategies = yaml.safe_load(f)
            if strategies is None or strategies.get("playlists") is None:
                logger.warning(f"Strategies file at {strategies_path} is empty or missing playlists.")
                return {"playlists": []}
    except Exception as e:
        logger.error(f"Error loading YAML: {e}")
        return {"playlists": []}

    if not isinstance(strategies, dict) or "playlists" not in strategies:
        logger.error("Invalid config format: Root element must be 'playlists' list.")
        logger.error("Should be: 'playlists:' not '- playlists:")
        return {"playlists": []}

    raw_playlists = strategies.get("playlists", [])
    logger.debug(f"Verifying {len(raw_playlists)} strategies...")

    valid_playlists = []
    raw_playlists = strategies.get("playlists", [])

    for idx, strategy in enumerate(raw_playlists):
        if not isinstance(strategy, dict):
            logger.error(f"Strategy index {idx} is not an object and will be skipped.")
            continue

        name = strategy.get("name", f"Unnamed_Strategy_{idx}")
        logger.debug(f"--- Processing Strategy {idx + 1}/{len(raw_playlists)}: '{name}' ---")

        unknown_strategy_keys = get_unknown_keys(strategy, STRATEGY_TOP_LEVEL_KEYS)
        if unknown_strategy_keys:
            formatted_keys = format_unknown_key_list(unknown_strategy_keys, STRATEGY_TOP_LEVEL_KEYS)
            logger.warning(
                f"[Depth: 1] Strategy '{name}' at strategy: Unknown key(s): {formatted_keys}."
            )

        sources = strategy.get("source", [])
        if isinstance(sources, list):
            source_type_counts = {}
            for source in sources:
                if not isinstance(source, dict):
                    continue
                source_type = str(source.get("type", "unknown")).lower()
                source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1

            duplicate_types = sorted([stype for stype, count in source_type_counts.items() if count > 1])
            if duplicate_types:
                logger.warning(
                    f"[Depth: 1] Strategy '{name}' at strategy > source: Duplicate source type(s) "
                    f"found: {', '.join(duplicate_types)}."
                )

        # Start recursion with explicit path tracking
        sources_ok = _validate_sources(logger, name, sources, depth=1, path="strategy")

        # Top-level modifiers
        modifiers_ok = True
        if "modifiers" in strategy:
            modifiers_ok = _validate_modifiers(logger, name, strategy.get("modifiers"), depth=1, path="strategy")

        dest_ok = _validate_destination(logger, name, strategy.get("destination", []))

        if sources_ok and modifiers_ok and dest_ok:
            valid_playlists.append(strategy)
            logger.debug(f"Successfully verified strategy: {name}")
        else:
            logger.error(f"Strategy '{name}' failed validation and will be skipped.")

    invalid_count = len(raw_playlists) - len(valid_playlists)
    logger.debug(
        f"Strategy loading completed. valid={len(valid_playlists)}, invalid={invalid_count}, "
        f"total={len(raw_playlists)}"
    )

    return {"playlists": valid_playlists}