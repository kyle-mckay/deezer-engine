import logging
import re
from datetime import datetime
from pathlib import Path

from utils.infrastructure.logger import ColorFormatter, initialize_deezer_logger


ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def _clear_handlers(logger):
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass


def test_initialize_deezer_logger_reconciles_handlers():
    logger = logging.getLogger("DeezerEngine")
    original_level = logger.level
    original_propagate = logger.propagate
    original_handlers = list(logger.handlers)

    _clear_handlers(logger)

    try:
        initialize_deezer_logger("INFO", log_to_file=True)
        initialize_deezer_logger("DEBUG", log_to_file=False)

        console_handlers = [
            handler for handler in logger.handlers if type(handler) is logging.StreamHandler
        ]
        file_handlers = [
            handler for handler in logger.handlers if isinstance(handler, logging.FileHandler)
        ]

        assert len(console_handlers) == 1
        assert len(file_handlers) == 0
        assert logger.level == logging.DEBUG
        assert logger.propagate is False
    finally:
        _clear_handlers(logger)
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        for handler in original_handlers:
            logger.addHandler(handler)


def test_file_output_matches_console_output_without_color(tmp_path, monkeypatch):
    monkeypatch.setattr("utils.infrastructure.logger.get_logs_dir", lambda: tmp_path)

    logger = logging.getLogger("DeezerEngine")
    original_level = logger.level
    original_propagate = logger.propagate
    original_handlers = list(logger.handlers)

    _clear_handlers(logger)

    try:
        logger = initialize_deezer_logger(level="DEBUG", log_to_file=True)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(ColorFormatter())
        logger.addHandler(stream_handler)

        captured_lines = []

        def emit_capture(record):
            formatted = stream_handler.format(record)
            captured_lines.append(ANSI_ESCAPE_PATTERN.sub("", formatted))

        stream_handler.emit = emit_capture

        logger.info("info parity check")
        logger.warning("warning parity check")

        today = datetime.now().strftime("%Y-%m-%d")
        log_path = Path(tmp_path) / f"{today}.log"
        file_lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines()]

        assert file_lines[-2:] == captured_lines[-2:]
    finally:
        _clear_handlers(logger)
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        for handler in original_handlers:
            logger.addHandler(handler)