"""
logger.py

Centralized logging configuration for the NEWS Daily Report project.
Uses Asia/Kolkata (IST) timestamps across all environments.
"""

from __future__ import annotations

import logging
from datetime import datetime
from logging import Formatter
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

from config import LOG_DIR, LOG_FILE, LOG_LEVEL

###############################################################################
# Timezone
###############################################################################

IST = ZoneInfo(
    "Asia/Kolkata",
)

###############################################################################
# Custom Formatter
###############################################################################


class ISTFormatter(Formatter):
    """
    Logging formatter that always prints IST timestamps.
    """

    def formatTime(
        self,
        record,
        datefmt=None,
    ):

        dt = datetime.fromtimestamp(
            record.created,
            tz=IST,
        )

        if datefmt:

            return dt.strftime(
                datefmt,
            )

        return dt.isoformat()


###############################################################################
# Logger Factory
###############################################################################


def setup_logger(
    name: str = "NEWS_Daily_Report",
) -> logging.Logger:
    """
    Create and return a configured logger.
    """

    logger = logging.getLogger(
        name,
    )

    #
    # Prevent duplicate handlers
    #

    if logger.handlers:

        return logger

    logger.setLevel(
        getattr(
            logging,
            LOG_LEVEL.upper(),
            logging.INFO,
        )
    )

    #
    # Ensure log directory exists
    #

    Path(
        LOG_DIR,
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    formatter = ISTFormatter(
        fmt=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(filename)s:%(lineno)d | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S IST",
    )

    ############################################################################
    # Console Handler
    ############################################################################

    console_handler = logging.StreamHandler()

    console_handler.setFormatter(
        formatter,
    )

    ############################################################################
    # Rotating File Handler
    ############################################################################

    file_handler = RotatingFileHandler(
        filename=LOG_FILE,
        mode="a",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    file_handler.setFormatter(
        formatter,
    )

    logger.addHandler(
        console_handler,
    )

    logger.addHandler(
        file_handler,
    )

    logger.propagate = False

    return logger


###############################################################################
# Global Logger
###############################################################################

logger = setup_logger()