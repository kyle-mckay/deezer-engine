# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import yaml
from utils.infrastructure.paths import get_data_dir


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
        mod_type = mod.get("type", "unknown")
        current_path = f"{path} > modifier[{mod_type}]"

        logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(modifiers)}] Validating {current_path}")

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
        source_type = source.get("type", "unknown")
        current_path = f"{path} > source[{source_type}]"

        logger.debug(f"[Depth: {depth}, {vtype} # {idx + 1}/{len(sources)}] Validating {current_path}")

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
        name = strategy.get("name", f"Unnamed_Strategy_{idx}")
        logger.debug(f"--- Processing Strategy {idx + 1}/{len(raw_playlists)}: '{name}' ---")

        # Start recursion with explicit path tracking
        sources_ok = _validate_sources(logger, name, strategy.get("source", []), depth=1, path="strategy")

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