import logging
import sys

def setup_logger(name, log_level="INFO"):
    # Set the logging level based on the provided string.
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create a logger instance with the specified name.
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if the logger is already configured
    if not logger.handlers:
        # Console handler to emit log records to stdout
        c_handler = logging.StreamHandler(sys.stdout)

        # Timestamp, logger name, level, and the message
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                datefmt='%Y-%m-%d %H:%M:%S')
        c_handler.setFormatter(fmt)

        logger.addHandler(c_handler)

    return logger