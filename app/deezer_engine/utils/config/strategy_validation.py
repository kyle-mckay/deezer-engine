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


def _normalize_for_duplicate_detection(value):
    """Return a stable representation for duplicate comparisons."""
    if isinstance(value, dict):
        normalized = {}
        for key, item in value.items():
            if key == "type" and isinstance(item, str):
                normalized[key] = item.lower()
            else:
                normalized[key] = _normalize_for_duplicate_detection(item)
        return normalized
    if isinstance(value, list):
        return [_normalize_for_duplicate_detection(item) for item in value]
    return value


def _describe_duplicate_entry(entry):
    entry_type = str(entry.get("type", "unknown")).lower()
    details = [f"type='{entry_type}'"]

    if "name" in entry:
        details.append(f"name='{entry.get('name')}'")
    if "id" in entry:
        details.append(f"id='{entry.get('id')}'")

    return ", ".join(details)


def _find_exact_duplicate_entries(entries):
    """Return duplicate groups keyed by a normalized exact-entry signature."""
    duplicate_groups = {}
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue

        normalized = _normalize_for_duplicate_detection(entry)
        signature = yaml.safe_dump(normalized, default_flow_style=True, sort_keys=True).strip()
        duplicate_groups.setdefault(signature, []).append((idx + 1, normalized))

    return [group for group in duplicate_groups.values() if len(group) > 1]


def _is_scalar_id(value):
    """Return True for scalar ID values we can coerce to API-safe strings."""
    return isinstance(value, (str, int))


def _is_scalar_name(value):
    """Return True for scalar name values we can coerce to safe keys."""
    return isinstance(value, (str, int))


def _validate_strategy_name_value(logger, strategy_name, strategy, strategy_index):
    """Validate top-level strategy name shape to avoid runtime naming crashes."""
    if "name" not in strategy:
        return True

    raw_name = strategy.get("name")
    log_prefix = f"[Depth: 1] Strategy #{strategy_index + 1} '{strategy_name}'"

    if _is_scalar_name(raw_name):
        return True

    if isinstance(raw_name, list):
        logger.error(
            f"{log_prefix}: Invalid top-level 'name' type 'list'. "
            "Strategy 'name' must be a scalar string/integer."
        )
        return False

    logger.error(
        f"{log_prefix}: Invalid top-level 'name' type '{type(raw_name).__name__}'. "
        "Strategy 'name' must be a scalar string/integer."
    )
    return False


def _validate_source_id_value(logger, strategy_name, source_type, source, depth, source_index, current_path):
    """Validate source.id shape for ID-based sources while preserving old key contracts."""
    id_based_sources = {"album", "artist", "playlist"}
    if source_type not in id_based_sources:
        return True

    if "id" not in source:
        return True

    source_id = source.get("id")
    log_prefix = f"[Depth: {depth}, Source # {source_index}] Strategy '{strategy_name}' at {current_path}"

    if _is_scalar_id(source_id):
        return True

    if isinstance(source_id, list):
        for item in source_id:
            if item is None:
                continue
            if not _is_scalar_id(item):
                logger.error(
                    f"{log_prefix}: Invalid 'id' list item type '{type(item).__name__}'. "
                    "Allowed item types are string, integer, or null."
                )
                return False
        return True

    logger.error(
        f"{log_prefix}: Invalid 'id' type '{type(source_id).__name__}'. "
        "Use a scalar string/integer or a list of scalar IDs."
    )
    return False


def _validate_source_name_value(logger, strategy_name, source_type, source, depth, source_index, current_path):
    """Validate source.name/filename shape for name-based sources."""
    log_prefix = f"[Depth: {depth}, Source # {source_index}] Strategy '{strategy_name}' at {current_path}"

    if source_type == "smarttracklist":
        if "name" not in source:
            return True

        source_name = source.get("name")
        if _is_scalar_name(source_name):
            return True

        if isinstance(source_name, list):
            for item in source_name:
                if item is None:
                    continue
                if not _is_scalar_name(item):
                    logger.error(
                        f"{log_prefix}: Invalid 'name' list item type '{type(item).__name__}'. "
                        "Allowed item types are string, integer, or null."
                    )
                    return False
            return True

        logger.error(
            f"{log_prefix}: Invalid 'name' type '{type(source_name).__name__}'. "
            "Use a scalar string/integer or a list of scalar names."
        )
        return False

    if source_type == "file":
        for field_name in ("filename", "name"):
            if field_name not in source:
                continue

            source_name = source.get(field_name)
            if _is_scalar_name(source_name):
                continue

            if isinstance(source_name, list):
                for item in source_name:
                    if item is None:
                        continue
                    if not _is_scalar_name(item):
                        logger.error(
                            f"{log_prefix}: Invalid '{field_name}' list item type '{type(item).__name__}'. "
                            "Allowed item types are string, integer, or null."
                        )
                        return False
                continue

            logger.error(
                f"{log_prefix}: Invalid '{field_name}' type '{type(source_name).__name__}'. "
                "Use a scalar string/integer or a list of scalar names."
            )
            return False

    return True


def _validate_modifiers(logger, strategy_name, modifiers, depth=1, path="root"):
    """
    Validates modifiers. If a modifier contains a source (like 'exclude'),
    it triggers a recursive call back to _validate_sources.
    """
    if not isinstance(modifiers, list):
        logger.error(f"[Depth: {depth}] Strategy '{strategy_name}' at {path}: Modifiers must be a list.")
        return False

    duplicate_modifiers = _find_exact_duplicate_entries(modifiers)
    if duplicate_modifiers:
        rendered_groups = []
        for group in duplicate_modifiers:
            positions = ", ".join(str(pos) for pos, _ in group)
            rendered_groups.append(
                f"{_describe_duplicate_entry(group[0][1])} at positions [{positions}]"
            )
        logger.warning(
            f"[Depth: {depth}] Strategy '{strategy_name}' at {path}: Exact duplicate modifier(s) "
            f"found: {'; '.join(rendered_groups)}."
        )

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

    duplicate_sources = _find_exact_duplicate_entries(sources)
    if duplicate_sources:
        rendered_groups = []
        for group in duplicate_sources:
            positions = ", ".join(str(pos) for pos, _ in group)
            rendered_groups.append(
                f"{_describe_duplicate_entry(group[0][1])} at positions [{positions}]"
            )
        logger.warning(
            f"[Depth: {depth}] Strategy '{strategy_name}' at {path} > source: Exact duplicate source(s) "
            f"found: {'; '.join(rendered_groups)}."
        )

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
        source_identifier = None
        if source.get("name") is not None:
            source_identifier = f"name={source.get('name')}"
        elif source.get("id") is not None:
            source_identifier = f"id={source.get('id')}"

        if source_identifier:
            current_path = f"{path} > source[{source_type}, {source_identifier}]"
        else:
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

        if not _validate_source_id_value(
            logger,
            strategy_name,
            source_type,
            source,
            depth,
            idx + 1,
            current_path,
        ):
            return False

        if not _validate_source_name_value(
            logger,
            strategy_name,
            source_type,
            source,
            depth,
            idx + 1,
            current_path,
        ):
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

    duplicate_destinations = _find_exact_duplicate_entries(destination)
    if duplicate_destinations:
        rendered_groups = []
        for group in duplicate_destinations:
            positions = ", ".join(str(pos) for pos, _ in group)
            rendered_groups.append(
                f"{_describe_duplicate_entry(group[0][1])} at positions [{positions}]"
            )
        logger.warning(
            f"[Depth: 1] Strategy '{strategy_name}' at {path}: Exact duplicate destination(s) "
            f"found: {'; '.join(rendered_groups)}."
        )

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
        if not _validate_strategy_name_value(logger, name, strategy, idx):
            continue
        logger.debug(f"--- Processing Strategy {idx + 1}/{len(raw_playlists)}: '{name}' ---")

        unknown_strategy_keys = get_unknown_keys(strategy, STRATEGY_TOP_LEVEL_KEYS)
        if unknown_strategy_keys:
            formatted_keys = format_unknown_key_list(unknown_strategy_keys, STRATEGY_TOP_LEVEL_KEYS)
            logger.warning(
                f"[Depth: 1] Strategy '{name}' at strategy: Unknown key(s): {formatted_keys}."
            )

        sources = strategy.get("source", [])

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