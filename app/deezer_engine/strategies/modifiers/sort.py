# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib
import logging

def normalize_sort(logger, sort_order):
    "Normalizes the sort order to the expected format"

    logger.debug(f"Normalizing sort order: '{sort_order}'")
    match sort_order:
        case "asc" | "ascending" :
            sort_order="ascending"
        case "desc" | "descending" :
            sort_order="descending"
        case _:
            logger.warning(f"Unknown sort order: '{sort_order}'")
            sort_order="unknown"
    logger.debug(f"Normalized sort order: '{sort_order}'")
    return sort_order

def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Sorts the tracks by a defined field and order before returing them to the next stage in the pipeline
    """
    sort_order=normalize_sort(logger,mod_data.get('order').lower())
    sort_field=mod_data.get('field').lower()

    logger.info(f"Action: Sorting by {sort_field} ({sort_order})")

    try:
        if not current_tracks:
            logger.debug("No tracks provided to sort modifier. Skipping.")
            return current_tracks

        def sort_key(x):
            val = x.get(sort_field)
            # Log the type of the first value found for debugging
            return val.lower() if isinstance(val, str) else val

        logger.debug(f"Executing sort on field '{sort_field}' for {len(current_tracks)} tracks.")
        
        match sort_order:
            case "ascending":
                sorted_tracks = sorted(current_tracks, key=sort_key)
            case "descending":
                sorted_tracks = sorted(current_tracks, key=sort_key, reverse=True)
            case _:
                logger.warning(f"Cannot sort: undefined order '{sort_order}'")
                return current_tracks

    except Exception as e:
        logger.error(f"Failed to sort tracks: {e}")
        logger.warning(f"Verify field '{sort_field}' exists in track metadata. Returning tracks unmodified.")
        sorted_tracks = current_tracks

    if logger.isEnabledFor(logging.DEBUG):
        sample_ids = [str(t.get('id')) for t in sorted_tracks[:5]]
        logger.debug(f"Sort complete. Top 5 track IDs: {', '.join(sample_ids)}...")

    return sorted_tracks