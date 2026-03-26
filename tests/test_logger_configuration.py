import logging

from utils.infrastructure.logger import initialize_deezer_logger


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