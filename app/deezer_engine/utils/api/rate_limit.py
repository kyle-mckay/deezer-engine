# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

"""API rate-limit policy and cooldown helpers."""

import time

from utils.infrastructure.signals import shutdown_event


def apply_rate_limit_checkpoint(
    logger,
    batch_start_time,
    iteration_index,
    api_batch_size,
    rate_limit,
    request_label,
    log_no_cooldown=False,
    cooldown_task=None,
):
    """Throttle batched requests to stay within the configured request rate."""
    if iteration_index % api_batch_size != 0:
        return batch_start_time, False

    target_time_per_batch = (api_batch_size / rate_limit) * 60
    elapsed_time = time.time() - batch_start_time
    items_per_second = api_batch_size / elapsed_time if elapsed_time > 0 else 0

    logger.debug(
        f"Time taken for {api_batch_size} {request_label}: {elapsed_time:.2f} seconds ({items_per_second:.2f} items/sec)"
    )

    if elapsed_time < target_time_per_batch:
        sleep_time = target_time_per_batch - elapsed_time
        logger.debug(
            f"Rate limit cooldown: target={target_time_per_batch:.2f}s, sleeping for {sleep_time:.2f}s to maintain {rate_limit} req/min limit"
        )
        interrupted = cooldown_wait_with_tasks(
            logger,
            sleep_time,
            request_label,
            cooldown_task=cooldown_task,
        )
        return time.time(), interrupted
    elif log_no_cooldown:
        logger.debug("No cooldown needed, proceeding to next batch immediately.")

    return time.time(), False


def cooldown_wait_with_tasks(logger, sleep_time, request_label, cooldown_task=None):
    """Wait in interruptible chunks and optionally run one cooldown task during the wait window."""
    max_chunk_seconds = 5.0
    remaining = max(0.0, float(sleep_time))
    task_ran = False

    while remaining > 0:
        if shutdown_event.is_set():
            logger.debug(
                f"Rate limit cooldown interrupted before waiting for {request_label}."
            )
            return True

        if not task_ran and cooldown_task is not None:
            task_start = time.time()
            cooldown_task()
            task_elapsed = max(0.0, time.time() - task_start)
            remaining = max(0.0, remaining - task_elapsed)
            task_ran = True
            if remaining <= 0:
                logger.debug("Cooldown task consumed the full cooldown window.")
                break

        wait_chunk = min(max_chunk_seconds, remaining)
        logger.debug(
            f"Rate limit cooldown progress for {request_label}: waiting {wait_chunk:.2f}s (remaining {remaining:.2f}s)."
        )
        interrupted = shutdown_event.wait(timeout=wait_chunk)
        if interrupted:
            logger.debug(
                f"Rate limit cooldown interrupted while waiting for {request_label}."
            )
            return True
        remaining = max(0.0, remaining - wait_chunk)

    logger.debug(f"Rate limit cooldown complete for {request_label}.")
    return False