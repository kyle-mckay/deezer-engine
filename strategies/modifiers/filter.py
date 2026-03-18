# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

def normalize_compariter(logger, operator):
    """Maps various string aliases to a compariter"""
    op = str(operator).lower().strip()
    logger.debug(f"Normalizing filter operator: '{operator}'")
    match op:
        case "==" | "equals" | "eq" | "is":
            return "=="
        case "!=" | "not" | "ne" | "is_not":
            return "!="
        case ">" | "greater_than" | "gt":
            return ">"
        case "<" | "less_than" | "lt":
            return "<"
        case ">=" | "gte":
            return ">="
        case "<=" | "lte":
            return "<="
        case "contains" | "in" | "like":
            return "contains"
        case "starts_with" | "startswith" | "sw":
            return "starts_with"
        case "ends_with" | "endswith" | "ew":
            return "ends_with"
        case _:
            logger.warning(f"Unknown filter operator: '{operator}'")
            return "unknown"

def run(client, config, logger, mod_data, current_tracks, source_name=None):
    """
    Filters tracks based on a field, operator, and value.
    """
    field = mod_data.get('field')
    operator = normalize_compariter(logger, mod_data.get('operator', '=='))
    value = mod_data.get('value')

    if operator == "unknown":
        logger.debug(f"Skipping filter due to invalid operator.")
        return current_tracks

    logger.debug(
        f"Filter modifier start: field={field}, operator={operator}, value={value}, "
        f"input={len(current_tracks)}"
    )
    logger.debug(f"Filter Criteria: {field} {operator} {value} (Targeting {len(current_tracks)} tracks)")
    filtered_tracks = []
    missing_field_count = 0
    comparison_error_count = 0
    cast_count = 0

    for track in current_tracks:
        try:
            track_val = track.get(field)
            
            # If the field doesn't exist on this track, skip it
            if track_val is None:
                missing_field_count += 1
                continue

            # Force type alignment
            compare_value = value
            if isinstance(track_val, (int, float)) and not isinstance(value, (int, float)):
                compare_value = float(value) if "." in str(value) else int(value)
                cast_count += 1
            elif isinstance(track_val, str):
                track_val = track_val.lower()
                compare_value = str(value).lower()

            match operator:
                case "==":
                    if track_val == compare_value: filtered_tracks.append(track)
                case "!=":
                    if track_val != compare_value: filtered_tracks.append(track)
                case ">":
                    if track_val > compare_value: filtered_tracks.append(track)
                case "<":
                    if track_val < compare_value: filtered_tracks.append(track)
                case ">=":
                    if track_val >= compare_value: filtered_tracks.append(track)
                case "<=":
                    if track_val <= compare_value: filtered_tracks.append(track)
                case "contains":
                    if str(compare_value) in str(track_val):
                        filtered_tracks.append(track)
                case "starts_with":
                    if str(track_val).startswith(str(compare_value)):
                        filtered_tracks.append(track)
                case "ends_with":
                    if str(track_val).endswith(str(compare_value)):
                        filtered_tracks.append(track)

        except (ValueError, TypeError) as e:
            comparison_error_count += 1
            logger.debug(f"Skipping track {track.get('id')} - comparison error: {e}")
            continue

    if cast_count:
        logger.debug(f"Filter coercion count: {cast_count}")
    if missing_field_count:
        logger.debug(f"Filter skipped tracks missing '{field}': {missing_field_count}")
    if comparison_error_count:
        logger.debug(f"Filter comparison errors: {comparison_error_count}")
    logger.info(f"Action: Filtered '{field} {operator} {value}': Kept {len(filtered_tracks)}/{len(current_tracks)} tracks.")
    logger.debug(
        f"Filter modifier end: kept={len(filtered_tracks)}, removed={len(current_tracks) - len(filtered_tracks)}"
    )
    return filtered_tracks