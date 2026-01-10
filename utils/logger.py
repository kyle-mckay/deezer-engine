import logging
import sys

def setup_logger(name, log_level="INFO"):
    # Set the logging level based on the provided string.
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create a logger instance with the specified name.
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Ensure no duplicate handlers are added to the logger.
    if not logger.handlers:
        # Set up a console handler to output logs to standard output.
        c_handler = logging.StreamHandler(sys.stdout)
        
        # Define the log message format including timestamp, logger name, level, and message.
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                datefmt='%Y-%m-%d %H:%M:%S')
        c_handler.setFormatter(fmt)
        
        logger.addHandler(c_handler)
        
    return logger