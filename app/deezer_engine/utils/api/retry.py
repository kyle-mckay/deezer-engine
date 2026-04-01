# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""API retry, backoff, and error classification helpers."""

import random
import time
from datetime import timedelta

import requests

from utils.config import get_global_value
from utils.infrastructure.signals import shutdown_event


# Error codes/types that should NOT trigger blocklisting on fetch cancellation.
NON_BLOCKLIST_ERROR_CODES = {
    "429",
    "ConnectionError",
    "ReadTimeout",
    "ConnectTimeout",
    "Timeout",
}

# Transient/network-like patterns that should not trigger blocklisting.
NON_BLOCKLIST_ERROR_PATTERNS = (
    "timed out",
    "timeout",
    "connection",
    "temporarily unavailable",
    "service unavailable",
    "network",
    "quota",
)


def extract_error_code(err):
    """Extract a compact error code/type from Deezer or network exceptions."""
    if err is None:
        return "unknown"

    if isinstance(err, (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout, requests.exceptions.Timeout)):
        return type(err).__name__

    err_str = str(err)
    err_str_lower = err_str.lower()

    if "429" in err_str_lower or "quota" in err_str_lower:
        return "429"

    marker = "'code':"
    marker_index = err_str_lower.find(marker)
    if marker_index != -1:
        remainder = err_str[marker_index + len(marker):].strip()
        code_chars = []
        for ch in remainder:
            if ch.isdigit():
                code_chars.append(ch)
            elif code_chars:
                break
        if code_chars:
            return "".join(code_chars)

    return type(err).__name__


def should_blocklist_failed_fetch(error_code, error_detail):
    """Returns True when a cancelled fetch should be blocklisted."""
    configured_days = get_global_value("blocklist_expiry_days", default=7)
    try:
        expiry_days = int(configured_days)
        if expiry_days == 0:
            return False
    except (TypeError, ValueError):
        pass

    if error_code in NON_BLOCKLIST_ERROR_CODES:
        return False

    detail = str(error_detail).lower() if error_detail is not None else ""
    return not any(pattern in detail for pattern in NON_BLOCKLIST_ERROR_PATTERNS)


def log_enrichment_progress(logger, log_prefix, i, total_items, last_log_time, start_log_time, log_interval):
    """
    Log enrichment progress at configured intervals. Called for every loop iteration.
    Returns updated last_log_time if logging occurred, otherwise returns original last_log_time.
    """
    current_time = time.time()
    if current_time - last_log_time >= log_interval:
        elapsed_time = current_time - start_log_time

        if isinstance(total_items, int):
            items_remaining = total_items - i
            time_per_item = elapsed_time / i
            eta_seconds = items_remaining * time_per_item
            eta_str = str(timedelta(seconds=int(eta_seconds)))
            percent = f"{i/total_items:.1%}"
            suffix = f"{percent} ({i}/{total_items}) complete (ETA: {eta_str})..."
        else:
            suffix = f"{i} items processed..."

        logger.info(f"{log_prefix} enrichment: {suffix}")
        return current_time

    return last_log_time


def fetch_with_retry(fetch_func, entity_id, entity_label, logger, mark_failed_fetch=None, max_retries=None):
    """Fetch an entity with retry, backoff, and optional failed-fetch persistence."""
    max_retries_value = max_retries if max_retries is not None else get_global_value('max_retries', 4)
    attempts = max_retries_value + 1  # Convert "number of retries" to "total attempts"
    last_error_code = "unknown"
    last_error_detail = None
    entity_name = entity_label.capitalize()

    for attempt in range(attempts):
        if shutdown_event.is_set():
            logger.debug(f"fetch_with_retry interrupted while fetching {entity_label} {entity_id}. Returning partial results.")
            return None

        try:
            if attempt == 0:
                time.sleep(random.uniform(0.1, 0.3))
            return fetch_func(entity_id)

        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as net_err:
            last_error_code = extract_error_code(net_err)
            last_error_detail = str(net_err)
            wait_time = 5 * (attempt + 1)
            if attempt < attempts - 1:
                logger.debug(
                    f"Network retry ({entity_name} {entity_id}): {net_err}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)

        except Exception as err:
            err_str = str(err).lower()
            if "429" in err_str or "quota" in err_str:
                last_error_code = "429"
                last_error_detail = str(err)
                wait_time = (2 ** attempt) + random.uniform(1, 3)
                if attempt < attempts - 1:
                    logger.warning(
                        f"Rate limited ({entity_name} {entity_id})! Retrying in {wait_time:.2f}s..."
                    )
                else:
                    logger.warning(
                        f"Rate limited ({entity_name} {entity_id}) on final attempt. Cooling down for {wait_time:.2f}s before cancellation."
                    )
                time.sleep(wait_time)
            else:
                last_error_code = extract_error_code(err)
                last_error_detail = str(err)
                logger.debug(
                    f"Unexpected API error for {entity_label} {entity_id}: {err} (Attempt {attempt + 1}/{attempts})"
                )
                if attempt < attempts - 1:
                    time.sleep(3)

    logger.error(f"CANCELLED: Failed to retrieve {entity_label} {entity_id} after {attempts} total attempts ({max_retries_value} retries).")
    if should_blocklist_failed_fetch(last_error_code, last_error_detail):
        logger.warning(
            f"Blocklisting {entity_label} {entity_id} after repeated fetch failures. "
            f"code={last_error_code}, deezer_response={last_error_detail}"
        )
        if mark_failed_fetch is not None:
            try:
                mark_failed_fetch(entity_id, last_error_code, logger)
            except Exception as db_err:
                logger.debug(f"Failed to persist {entity_label} failure state for {entity_id}: {db_err}")
    else:
        logger.debug(
            f"Skipped blocklisting {entity_label} {entity_id} due to transient/non-blocking error ({last_error_code})."
        )

    return None