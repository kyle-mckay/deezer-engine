# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from datetime import datetime
from .paths import get_logs_dir


DEEZER_LOGGER_NAME = "DeezerEngine"


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


def _normalize_level(level):
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.INFO)
    return level


def _build_console_handler():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter())
    return handler


def _build_file_handler():
    log_dir = get_logs_dir()
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    today = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join(log_dir, f"{today}.log")
    handler = logging.FileHandler(log_filename, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - [%(name)s] [%(levelname)s] "
            "[%(module)s.%(funcName)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def _close_handlers(logger):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def initialize_deezer_logger(level=logging.INFO, log_to_file=True):
    """
    Configure the DeezerEngine logger for the current runtime invocation.

    This always rebuilds handlers so repeated startup in the same process uses
    the current capture streams and file logging settings.
    """
    logger = logging.getLogger(DEEZER_LOGGER_NAME)
    logger.setLevel(_normalize_level(level))
    logger.propagate = False

    _close_handlers(logger)
    logger.addHandler(_build_console_handler())

    if log_to_file:
        logger.addHandler(_build_file_handler())

    return logger


def setup_logger(name="DeezerEngine", level=logging.INFO, log_to_file=True):
    """
    Returns a configured logger with:
    - Colored Console Output
    - Date-based, Clean (Plain Text) File Output
    """
    if name == DEEZER_LOGGER_NAME:
        return initialize_deezer_logger(level, log_to_file)

    logger = logging.getLogger(name)
    logger.setLevel(_normalize_level(level))

    if not logger.handlers:
        # 1. Console Handler (Colored)
        logger.addHandler(_build_console_handler())

        # 2. File Handler (Date-based, No Colors)
        if log_to_file:
            logger.addHandler(_build_file_handler())

    return logger