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
            logger.warn(f"Unknown sort order: '{sort_order}")
            sort_order="unknown"
    logger.debug(f"Normalized: '{sort_order}")
    return sort_order

def run(client, config, logger, mod_data, current_tracks):
    """
    Sorts the tracks by a defined field and order before returing them to the next stage in the pipeline
    """
    logger.debug("------ modifiers.sort START------")
    sort_order=normalize_sort(logger,mod_data.get('order').lower())
    sort_field=mod_data.get('field').lower()

    logger.info(f"Sorting tracks by '{sort_field}' in '{sort_order}' order")

    try:
        match sort_order:
            case "ascending":
                sorted_tracks = sorted(current_tracks, key=lambda x: x[sort_field].lower())
            case "descending":
                sorted_tracks = sorted(current_tracks, key=lambda x: x[sort_field].lower(),reverse=True)
            case _:
                logger.warn(f"Unable to sort by undefined sort order: '{sort_order}")
                logger.warn("Skipping sort")
                return current_tracks

    except Exception as e:
        logger.error(f"Failed to sort order exclusion: {e}")
        logger.warn("Check your 'by' field is supported. Tracks will be returned without modification.")
        sorted_tracks = current_tracks

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Sorted tracks: {sorted_tracks}")

    logger.debug("------ modifiers.sort END------")
    return sorted_tracks