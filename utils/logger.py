import logging
import os
from datetime import datetime

class ColorFormatter(logging.Formatter):
    """
    Custom log formatter that applies ANSI color codes based on the log level.
    """
    GREY = "\033[90m"         # Debug
    DEFAULT = "\033[0m"      # Info
    ORANGE = "\033[38;5;208m" # Warning
    RED = "\033[31m"          # Error
    BOLD_RED = "\033[1;31m"   # Critical
    RESET = "\033[0m"

    # Format: <date> - [name] [LogLevel] - message
    log_format = "%(asctime)s - [%(name)s] [%(levelname)s] - %(message)s"

    FORMATS = {
        logging.DEBUG: GREY + log_format + RESET,
        logging.INFO: DEFAULT + log_format + RESET,
        logging.WARNING: ORANGE + log_format + RESET,
        logging.ERROR: RED + log_format + RESET,
        logging.CRITICAL: BOLD_RED + log_format + RESET
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.log_format)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
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
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            today = datetime.now().strftime("%Y-%m-%d")
            log_filename = os.path.join(log_dir, f"{today}.log")
            
            fh = logging.FileHandler(log_filename, encoding='utf-8')
            # Consistent format for file logs (without ANSI codes)
            clean_format = logging.Formatter(
                "%(asctime)s - [%(name)s] [%(levelname)s] - %(message)s", 
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            fh.setFormatter(clean_format)
            logger.addHandler(fh)
        
    return logger