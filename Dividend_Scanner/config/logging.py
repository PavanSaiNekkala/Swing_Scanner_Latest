"""
Logging Configuration
"""

from __future__ import annotations

import sys

from loguru import logger

from config.settings import LOG_FORMAT
from config.settings import LOG_LEVEL


def configure_logging() -> None:
    """
    Configure Loguru.
    """

    logger.remove()

    logger.add(

        sys.stdout,

        level=LOG_LEVEL,

        format=LOG_FORMAT,

        enqueue=True,

        backtrace=False,

        diagnose=False,

    )