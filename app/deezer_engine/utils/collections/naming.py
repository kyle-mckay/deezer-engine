# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later


def _normalize_smarttracklist_name(name):
    """Normalize smarttracklist names to the canonical internal-id-like key."""
    if name is None:
        return None

    normalized_name = str(name).strip().lower().replace("-", "_")
    return normalized_name or None


def _normalize_scalar_value(raw_value):
    if raw_value is None:
        return None

    raw_value_str = str(raw_value).strip()
    return raw_value_str or None

def get_collection_name(logger, type, name=None, id=None):
    """Resolve expected collections.source_name for cache matching."""
    logger.debug(f"Resolving collection name for type='{type}', name='{name}', id='{id}'")
    if not type:
        logger.warning("Unable to determine collection name, source type is empty.")
        return "unknown"

    type = type.lower()
    prefix = f"{type}__"

    def _coerce_scalar(raw_value, label):
        if isinstance(raw_value, list):
            for item in raw_value:
                normalized_item = _normalize_scalar_value(item)
                if normalized_item:
                    logger.warning(
                        f"Collection naming received list input for {label}; using the first valid value '{normalized_item}'. "
                        "Callers should expand multi-value sources before resolving a collection name."
                    )
                    return normalized_item
            return None

        return _normalize_scalar_value(raw_value)

    def _has_id():
        """Return True if id is provided and not empty."""
        normalized_id = _coerce_scalar(id, "id")
        if normalized_id:
            logger.debug(f"id '{id}' is provided")
            return True

        logger.debug("id is empty or None")
        return False

    def _has_name():
        """Return True if name is provided and not empty."""
        normalized_name = _coerce_scalar(name, "name")
        if normalized_name:
            logger.debug(f"name '{name}' is provided")
            return True

        logger.debug("name is empty or None")
        return False

    collection = "unknown"
    normalized_id = _coerce_scalar(id, "id")
    normalized_name = _coerce_scalar(name, "name")
    match type:
        case "favorites" | "history":
            collection = f"{type}"
        case "playlist" | "album" | "artist" | "track":
            if _has_id():
                collection = f"{prefix}{normalized_id}"
        case "smarttracklist":
            if _has_name():
                normalized_smart_name = _normalize_smarttracklist_name(normalized_name)
                if normalized_smart_name:
                    collection = f"{prefix}{normalized_smart_name}"
        case "file":
            if _has_name():
                collection = f"{prefix}{normalized_name}"

    logger.debug(f"Collection name identified as: '{collection}'")
    return collection