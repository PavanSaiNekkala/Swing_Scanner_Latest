"""
config/logging_config.py

Central logging configuration for the NSE Market Report project.

Features
--------
✓ Console logging
✓ Rotating log files
✓ Timestamped log format
✓ Configurable log level
✓ UTF-8 support
"""

from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from config.config import LOG_LEVEL, LOG_FILE


def setup_logger(
    logger_name: str = "NSE_MARKET_REPORT"
) -> logging.Logger:
    """
    Creates and returns a configured logger.

    Parameters
    ----------
    logger_name : str

    Returns
    -------
    logging.Logger
    """

    logger = logging.getLogger(logger_name)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper()))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ----------------------------
    # Console Handler
    # ----------------------------
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # ----------------------------
    # Rotating File Handler
    # ----------------------------
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger


# Default project logger
logger = setup_logger()