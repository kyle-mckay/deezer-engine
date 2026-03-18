# Copyright (C) 2026 kylemmkay
# Source: https://codeberg.org/kylemmkay/deezer-engine
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
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

    logger.debug(f"Filter Criteria: {field} {operator} {value} (Targeting {len(current_tracks)} tracks)")
    filtered_tracks = []

    for track in current_tracks:
        try:
            track_val = track.get(field)
            
            # If the field doesn't exist on this track, skip it
            if track_val is None:
                logger.debug(f"Track {track.get('id')} excluded: Field '{field}' missing.")
                continue

            # Force type alignment
            compare_value = value
            if isinstance(track_val, (int, float)) and not isinstance(value, (int, float)):
                logger.debug(f"Casting filter value '{value}' to numeric for field '{field}'")
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
    logger.info(f"Action: Filtered '{field} {operator} {value}': Kept {len(filtered_tracks)}/{len(current_tracks)} tracks.")
    return filtered_tracks