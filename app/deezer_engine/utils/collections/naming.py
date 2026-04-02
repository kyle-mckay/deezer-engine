# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later


def _normalize_smarttracklist_name(name):
    """Normalize smarttracklist names to the canonical internal-id-like key."""
    if name is None:
        return None

    normalized_name = str(name).strip().lower().replace("-", "_")
    return normalized_name or None

def get_collection_name(logger, type, name=None, id=None):
    """Resolve expected collections.source_name for cache matching."""
    logger.debug(f"Resolving collection name for type='{type}', name='{name}', id='{id}'")
    if not type:
        logger.warning("Unable to determine collection name, source type is empty.")
        return "unknown"

    type = type.lower()
    prefix = f"{type}__"

    def _normalize_scalar_or_list(raw_value):
        if isinstance(raw_value, list):
            normalized_values = []
            for item in raw_value:
                if item is None:
                    continue
                item_str = str(item).strip()
                if item_str:
                    normalized_values.append(item_str)
            return normalized_values

        if raw_value is None:
            return None

        raw_value_str = str(raw_value).strip()
        return raw_value_str or None

    def _has_id():
        """Return True if id is provided and not empty."""
        normalized_id = _normalize_scalar_or_list(id)
        if normalized_id:
            logger.debug(f"id '{id}' is provided")
            return True

        logger.debug("id is empty or None")
        return False

    def _has_name():
        """Return True if name is provided and not empty."""
        normalized_name = _normalize_scalar_or_list(name)
        if normalized_name:
            logger.debug(f"name '{name}' is provided")
            return True

        logger.debug("name is empty or None")
        return False

    collection = "unknown"
    normalized_id = _normalize_scalar_or_list(id)
    normalized_name = _normalize_scalar_or_list(name)
    match type:
        case "favorites" | "history":
            collection = f"{type}"
        case "playlist" | "album" | "artist" | "track":
            if _has_id():
                if isinstance(normalized_id, list):
                    collection = f"{prefix}{'__'.join(normalized_id)}"
                else:
                    collection = f"{prefix}{normalized_id}"
        case "smarttracklist":
            if _has_name():
                if isinstance(normalized_name, list):
                    normalized_parts = []
                    for item in normalized_name:
                        normalized_item = _normalize_smarttracklist_name(item)
                        if normalized_item:
                            normalized_parts.append(normalized_item)
                    if normalized_parts:
                        collection = f"{prefix}{'__'.join(normalized_parts)}"
                else:
                    normalized_smart_name = _normalize_smarttracklist_name(normalized_name)
                    if normalized_smart_name:
                        collection = f"{prefix}{normalized_smart_name}"
        case "file":
            if _has_name():
                if isinstance(normalized_name, list):
                    collection = f"{prefix}{'__'.join(normalized_name)}"
                else:
                    collection = f"{prefix}{normalized_name}"

    logger.debug(f"Collection name identified as: '{collection}'")
    return collection