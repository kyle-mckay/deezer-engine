import logging

def normalize_compariter(logger, operator):
    """Maps various string aliases to a compariter"""
    op = str(operator).lower().strip()
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
            logger.warning(f"Unknown operator: '{operator}'")
            return "unknown"

def run(client, config, logger, mod_data, current_tracks):
    """
    Filters tracks based on a field, operator, and value.
    """
    logger.debug("------ modifiers.filter START ------")
    
    field = mod_data.get('field')
    operator = normalize_compariter(logger, mod_data.get('operator', '=='))
    value = mod_data.get('value')

    if operator == "unknown":
        return current_tracks

    logger.info(f"Filtering tracks where '{field}' {operator} {value}")
    filtered_tracks = []

    for track in current_tracks:
        try:
            track_val = track.get(field)
            
            # If the field doesn't exist on this track, skip it
            if track_val is None:
                continue

            # Force type alignment
            compare_value = value
            if isinstance(track_val, (int, float)) and not isinstance(value, (int, float)):
                compare_value = float(value) if "." in str(value) else int(value)
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
            logger.debug(f"Skipping track {track.get('id')} - comparison error: {e}")
            continue

    logger.info(f"Filter complete. Kept {len(filtered_tracks)} of {len(current_tracks)} tracks.")
    logger.debug("------ modifiers.filter END ------")
    return filtered_tracks