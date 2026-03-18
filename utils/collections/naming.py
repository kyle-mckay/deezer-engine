# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

def get_collection_name(logger, type, name=None, id=None):
    """Resolve expected collections.source_name for cache matching."""
    logger.debug(f"Resolving collection name for type='{type}', name='{name}', id='{id}'")
    if not type:
        logger.warning("Unable to determine collection name, source type is empty.")
        return "unknown"

    type = type.lower()
    prefix = f"{type}__"

    def _has_id():
        """Return True if id is provided and not empty."""
        if id:
            logger.debug(f"id '{id}' is provided")
            return True

        logger.debug("id is empty or None")
        return False

    def _has_name():
        """Return True if name is provided and not empty."""
        if name:
            logger.debug(f"name '{name}' is provided")
            return True

        logger.debug("name is empty or None")
        return False

    collection = "unknown"
    match type:
        case "favorites" | "history":
            collection = f"{type}"
        case "playlist" | "album" | "artist":
            if _has_id():
                collection = f"{prefix}{id}"
        case "smarttracklist" | "file":
            if _has_name():
                collection = f"{prefix}{name}"

    logger.debug(f"Collection name identified as: '{collection}'")
    return collection