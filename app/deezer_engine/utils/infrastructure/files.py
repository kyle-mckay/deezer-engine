# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import ast
import csv
import json
from pathlib import Path


def write_to_json(data, final_target, logger):
	"""Save a list of dictionaries to JSON."""
	try:
		target_path = Path(final_target)
		logger.debug(f"Writing JSON to '{target_path}' with {len(data)} items.")

		target_path.parent.mkdir(parents=True, exist_ok=True)

		with open(target_path, "w", encoding="utf-8") as file_handle:
			json.dump(data, file_handle, indent=4, ensure_ascii=False)

		logger.info(f"Successfully saved tracks to: {target_path}")
		logger.debug(f"JSON write completed for '{target_path}'.")
	except Exception as exc:
		logger.error(f"Failed to save JSON to {final_target}. Error: {exc}")
		raise


def read_from_json(file_path, logger):
	"""Read and deserialize a JSON file."""
	try:
		source_path = Path(file_path)
		logger.debug(f"Reading JSON from '{source_path}'.")

		if not source_path.exists():
			logger.error(f"File not found: {file_path}")
			return None

		with open(source_path, "r", encoding="utf-8") as file_handle:
			data = json.load(file_handle)

		logger.info(f"Successfully loaded {len(data)} items from JSON.")
		logger.debug(f"JSON read completed from '{source_path}' with {len(data)} items.")
		return data
	except Exception as exc:
		logger.error(f"Failed to read JSON from {file_path}. Error: {exc}")
		raise


def write_to_csv(data, final_target, logger):
	"""Save a list of dictionaries to CSV."""
	if not data:
		logger.warning("No data provided to save_tracklist_to_csv.")
		return

	try:
		target_path = Path(final_target)
		target_path.parent.mkdir(parents=True, exist_ok=True)

		headers = data[0].keys()
		logger.debug(f"Writing CSV to '{target_path}' with {len(data)} rows and {len(headers)} columns.")

		with open(target_path, "w", newline="", encoding="utf-8-sig") as file_handle:
			writer = csv.DictWriter(file_handle, fieldnames=headers)
			writer.writeheader()

			for row in data:
				clean_row = {}
				for key, value in row.items():
					if isinstance(value, (dict, list)):
						clean_row[key] = str(value)
					else:
						clean_row[key] = value

				writer.writerow(clean_row)

		logger.info(f"Successfully saved CSV to: {target_path}")
		logger.debug(f"CSV write completed for '{target_path}'.")
	except Exception as exc:
		logger.error(f"Failed to save CSV to {final_target}. Error: {exc}")
		raise


def read_from_csv(file_path, logger):
	"""Read CSV rows and restore basic Python types where possible."""
	data = []
	converted_values = 0
	raw_string_values = 0
	try:
		source_path = Path(file_path)
		logger.debug(f"Reading CSV from '{source_path}'.")

		if not source_path.exists():
			logger.error(f"File not found: {file_path}")
			return None

		with open(source_path, "r", encoding="utf-8-sig") as file_handle:
			reader = csv.DictReader(file_handle)
			for row in reader:
				processed_row = {}
				for key, value in row.items():
					try:
						processed_row[key] = ast.literal_eval(value)
						converted_values += 1
					except (ValueError, SyntaxError):
						processed_row[key] = value
						raw_string_values += 1
				data.append(processed_row)

		logger.info(f"Successfully loaded {len(data)} rows from CSV.")
		logger.debug(
			f"CSV read completed from '{source_path}' with {len(data)} rows "
			f"(converted_values={converted_values}, raw_string_values={raw_string_values})."
		)
		return data
	except Exception as exc:
		logger.error(f"Failed to read CSV from {file_path}. Error: {exc}")
		raise