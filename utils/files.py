# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import ast
import csv
from pathlib import Path

def write_to_json(data, final_target, logger):
    """
    Saves a list of song dictionaries to a JSON file.
    """
    try:
        target_path = Path(final_target)
        logger.debug(f"Writing JSON to '{target_path}' with {len(data)} items.")
        
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            # indent=4 makes the JSON human-readable
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        logger.info(f"Successfully saved tracks to: {target_path}")
        logger.debug(f"JSON write completed for '{target_path}'.")
        
    except Exception as e:
        logger.error(f"Failed to save JSON to {final_target}. Error: {e}")
        raise # Re-raise if you want the calling script to handle the failure

def read_from_json(file_path, logger):
    """
    Reads a JSON file and returns the data.
    """
    try:
        source_path = Path(file_path)
        logger.debug(f"Reading JSON from '{source_path}'.")
        
        if not source_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        logger.info(f"Successfully loaded {len(data)} items from JSON.")
        logger.debug(f"JSON read completed from '{source_path}' with {len(data)} items.")
        return data
        
    except Exception as e:
        logger.error(f"Failed to read JSON from {file_path}. Error: {e}")
        raise

def write_to_csv(data, final_target, logger):
    """
    Saves a list of song dictionaries to a CSV file.
    """
    if not data:
        logger.warning("No data provided to save_tracklist_to_csv.")
        return

    try:
        target_path = Path(final_target)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Identify all possible column headers
        headers = data[0].keys()
        logger.debug(f"Writing CSV to '{target_path}' with {len(data)} rows and {len(headers)} columns.")

        with open(target_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for row in data:
                #Pre-process nested fields
                clean_row = {}
                for key, value in row.items():
                    if isinstance(value, (dict, list)):
                        # Converts dicts/lists to string
                        clean_row[key] = str(value)
                    else:
                        clean_row[key] = value
                
                writer.writerow(clean_row)

        logger.info(f"Successfully saved CSV to: {target_path}")
        logger.debug(f"CSV write completed for '{target_path}'.")

    except Exception as e:
        logger.error(f"Failed to save CSV to {final_target}. Error: {e}")
        raise

def read_from_csv(file_path, logger):
    """
    Reads a CSV file and returns a list of dictionaries.
    Attempts to restore basic Python types (dicts, lists, ints).
    """
    data = []
    converted_values = 0
    raw_string_values = 0
    try:
        source_path = Path(file_path)
        logger.debug(f"Reading CSV from '{source_path}'.")
        
        if not source_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        with open(source_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_row = {}
                for key, value in row.items():
                    # Attempt to convert strings back to Python objects
                    try:
                        # literal_eval is safer than eval()
                        processed_row[key] = ast.literal_eval(value)
                        converted_values += 1
                    except (ValueError, SyntaxError):
                        # Normal string
                        processed_row[key] = value
                        raw_string_values += 1
                data.append(processed_row)

        logger.info(f"Successfully loaded {len(data)} rows from CSV.")
        logger.debug(
            f"CSV read completed from '{source_path}' with {len(data)} rows "
            f"(converted_values={converted_values}, raw_string_values={raw_string_values})."
        )
        return data

    except Exception as e:
        logger.error(f"Failed to read CSV from {file_path}. Error: {e}")
        raise