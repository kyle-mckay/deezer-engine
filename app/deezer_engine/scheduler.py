# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from datetime import datetime, timedelta

from croniter import croniter

from utils.infrastructure.signals import shutdown_event


DEFAULT_SCHEDULE = "0 3 * * *"


class CronScheduler:
    def __init__(self, schedule, logger=None, event=None, now_provider=None):
        self.schedule = schedule or DEFAULT_SCHEDULE
        self.logger = logger
        self.event = event or shutdown_event
        self.now_provider = now_provider or datetime.now

    def seconds_until_next_run(self):
        base = self.now_provider()
        next_run = croniter(self.schedule, base).get_next(datetime)
        return max(int((next_run - base).total_seconds()), 0)

    def wait_for_next_run(self):
        wait_seconds = self.seconds_until_next_run()

        if self.logger and self.logger.isEnabledFor(logging.DEBUG):
            next_run = self.now_provider() + timedelta(seconds=wait_seconds)
            self.logger.debug(
                "Next scheduled execution: %s (in %s seconds)",
                next_run.strftime("%Y-%m-%d %H:%M:%S %z"),
                wait_seconds,
            )

        interrupted = self.event.wait(timeout=wait_seconds)
        return not interrupted, wait_seconds

    def run(self, callback, *, run_before=False):
        if run_before and not self.event.is_set():
            if self.logger:
                self.logger.info("Run-before-cron enabled. Starting immediate execution.")
            callback()

        while not self.event.is_set():
            should_run, wait_seconds = self.wait_for_next_run()
            if not should_run:
                break

            if self.logger:
                self.logger.info("Triggering scheduled run after %s seconds.", wait_seconds)
            callback()
