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

from config.config import (
    LOG_FILE,
    LOG_LEVEL,
)

###############################################################################
# LOGGER SETUP
###############################################################################

def setup_logger(
    logger_name: str = "NSE_MARKET_REPORT",
) -> logging.Logger:
    """
    Configure and return an application logger.
    """

    logger = logging.getLogger(
        logger_name
    )

    if logger.handlers:
        return logger

    logger.setLevel(
        getattr(
            logging,
            LOG_LEVEL.upper(),
        )
    )

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ###########################################################################
    # Console
    ###########################################################################

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter
    )

    ###########################################################################
    # File
    ###########################################################################

    Path(
        LOG_FILE
    ).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        formatter
    )

    logger.addHandler(
        console_handler
    )

    logger.addHandler(
        file_handler
    )

    logger.propagate = False

    return logger


###############################################################################
# LOGGER ACCESSOR
###############################################################################

def get_logger(
    logger_name: str,
) -> logging.Logger:
    """
    Return a configured logger.

    Automatically initializes the logger if it
    has not already been created.
    """

    return setup_logger(
        logger_name
    )


###############################################################################
# DEFAULT LOGGER
###############################################################################

logger = setup_logger()