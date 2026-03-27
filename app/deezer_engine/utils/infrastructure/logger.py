# SPDX-FileCopyrightText: 2026 kylemmkay
# SPDX-License-Identifier: GPL-3.0-or-later
import logging
import os
from datetime import datetime
from .paths import get_logs_dir


DEEZER_LOGGER_NAME = "DeezerEngine"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
INFO_FORMAT = "%(asctime)s - [%(name)s] [%(levelname)s] - %(message)s"
DETAILED_FORMAT = (
    "%(asctime)s - [%(name)s] [%(levelname)s] "
    "[%(module)s.%(funcName)s:%(lineno)d] - %(message)s"
)


def _build_level_formatters(datefmt, color_by_level=None, reset_code=""):
    color_by_level = color_by_level or {}
    format_by_level = {
        logging.DEBUG: DETAILED_FORMAT,
        logging.INFO: INFO_FORMAT,
        logging.WARNING: DETAILED_FORMAT,
        logging.ERROR: DETAILED_FORMAT,
        logging.CRITICAL: DETAILED_FORMAT,
    }

    formatters = {}
    for level, format_string in format_by_level.items():
        color_prefix = color_by_level.get(level, "")
        formatters[level] = logging.Formatter(
            f"{color_prefix}{format_string}{reset_code}",
            datefmt=datefmt,
        )
    return formatters


class LevelAwareFormatter(logging.Formatter):
    def __init__(self, datefmt=DEFAULT_DATE_FORMAT, color_by_level=None, reset_code=""):
        super().__init__(datefmt=datefmt)
        self._formatters = _build_level_formatters(
            datefmt=datefmt,
            color_by_level=color_by_level,
            reset_code=reset_code,
        )
        self._fallback = logging.Formatter(INFO_FORMAT, datefmt=datefmt)

    def format(self, record):
        formatter = self._formatters.get(record.levelno, self._fallback)
        return formatter.format(record)


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

    info_format = INFO_FORMAT
    detailed_format = DETAILED_FORMAT

    def __init__(self, datefmt=DEFAULT_DATE_FORMAT):
        self._delegate = LevelAwareFormatter(
            datefmt=datefmt,
            color_by_level={
                logging.DEBUG: self.GREY,
                logging.INFO: self.DEFAULT,
                logging.WARNING: self.ORANGE,
                logging.ERROR: self.RED,
                logging.CRITICAL: self.BOLD_RED,
            },
            reset_code=self.RESET,
        )

    def format(self, record):
        return self._delegate.format(record)


class PlainTextFormatter(logging.Formatter):
    """
    Formatter that mirrors ColorFormatter output, but without ANSI colors.
    """

    info_format = INFO_FORMAT
    detailed_format = DETAILED_FORMAT

    def __init__(self, datefmt=DEFAULT_DATE_FORMAT):
        self._delegate = LevelAwareFormatter(datefmt=datefmt)

    def format(self, record):
        return self._delegate.format(record)


def _normalize_level(level):
    if isinstance(level, str):
        return getattr(logging, level.upper(), logging.INFO)
    return level


def _build_console_handler():
    handler = _build_stream_handler()
    handler.setFormatter(ColorFormatter())
    return handler


def _build_stream_handler(stream=None):
    return logging.StreamHandler(stream=stream)


def _build_file_handler():
    log_dir = get_logs_dir()
    os.makedirs(log_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join(log_dir, f"{today}.log")
    handler = logging.FileHandler(log_filename, encoding="utf-8", delay=True)
    handler.setFormatter(PlainTextFormatter())
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