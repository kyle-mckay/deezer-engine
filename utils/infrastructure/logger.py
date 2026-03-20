# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from datetime import datetime
from .paths import get_logs_dir


class ColorFormatter(logging.Formatter):
    """
    Custom log formatter that applies ANSI color codes based on the log level.
    """

    GREY = "\033[90m"          # Debug
    DEFAULT = "\033[0m"       # Info
    ORANGE = "\033[38;5;208m" # Warning
    RED = "\033[31m"           # Error
    BOLD_RED = "\033[1;31m"    # Critical
    RESET = "\033[0m"

    info_format = "%(asctime)s - [%(name)s] [%(levelname)s] - %(message)s"
    detailed_format = (
        "%(asctime)s - [%(name)s] [%(levelname)s] "
        "[%(module)s.%(funcName)s:%(lineno)d] - %(message)s"
    )

    def __init__(self, datefmt="%Y-%m-%d %H:%M:%S"):
        super().__init__(datefmt=datefmt)
        # Cache formatter instances to avoid rebuilding on every log
        self._formatters = {
            logging.DEBUG: logging.Formatter(
                self.GREY + self.detailed_format + self.RESET,
                datefmt=datefmt,
            ),
            logging.INFO: logging.Formatter(
                self.DEFAULT + self.info_format + self.RESET,
                datefmt=datefmt,
            ),
            logging.WARNING: logging.Formatter(
                self.ORANGE + self.detailed_format + self.RESET,
                datefmt=datefmt,
            ),
            logging.ERROR: logging.Formatter(
                self.RED + self.detailed_format + self.RESET,
                datefmt=datefmt,
            ),
            logging.CRITICAL: logging.Formatter(
                self.BOLD_RED + self.detailed_format + self.RESET,
                datefmt=datefmt,
            ),
        }
        self._fallback = logging.Formatter(self.info_format, datefmt=datefmt)

    def format(self, record):
        formatter = self._formatters.get(record.levelno, self._fallback)
        return formatter.format(record)


def setup_logger(name="DeezerEngine", level=logging.INFO, log_to_file=True):
    """
    Returns a configured logger with:
    - Colored Console Output
    - Date-based, Clean (Plain Text) File Output
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(level)

        # 1. Console Handler (Colored)
        ch = logging.StreamHandler()
        ch.setFormatter(ColorFormatter())
        logger.addHandler(ch)

        # 2. File Handler (Date-based, No Colors)
        if log_to_file:
            log_dir = get_logs_dir()
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)

            today = datetime.now().strftime("%Y-%m-%d")
            log_filename = os.path.join(log_dir, f"{today}.log")

            fh = logging.FileHandler(log_filename, encoding='utf-8')
            # Consistent format for file logs (without ANSI codes)
            clean_format = logging.Formatter(
                "%(asctime)s - [%(name)s] [%(levelname)s] "
                "[%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            fh.setFormatter(clean_format)
            logger.addHandler(fh)

    return logger