"""
Application Logger

Provides a configured Loguru logger.
"""

from __future__ import annotations

from loguru import logger


def get_logger(
    name: str,
):
    """
    Return a logger with module context.
    """

    return logger.bind(
        module=name
    )