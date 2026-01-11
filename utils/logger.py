import logging
import sys

def setup_logger(name, log_level="INFO"):
    # Set the logging level based on the provided string.
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create a logger instance with the specified name.
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate logs if called multiple times
    if not logger.handlers:
        # Console Handler
        c_handler = logging.StreamHandler(sys.stdout)
        
        # Format: Time - Name - Level - Message
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                datefmt='%Y-%m-%d %H:%M:%S')
        c_handler.setFormatter(fmt)
        
        logger.addHandler(c_handler)
        
    return logger