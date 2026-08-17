"""
Enterprise logging configuration.

This module provides centralized logging for the NEWS_REPORT
application.

Features
--------
• Console logging
• Rotating file logging
• Dedicated error log
• UTF-8 support
• Thread-safe initialization
• Performance timing decorator
• Exception logging decorator
• Logger factory
• No duplicate handlers

Author
------
Pavan Sai Nekkala

Project
-------
NEWS_REPORT

Python
------
3.12+
"""

from __future__ import annotations

import functools
import logging
import logging.handlers
import threading
import time
from pathlib import Path
from typing import Any
from typing import Callable
from typing import TypeVar
from typing import ParamSpec

from config.constants import (
    LOG_DATE_FORMAT,
    LOG_FILE_NAME,
    LOG_FORMAT,
)
from config.settings import settings

###############################################################################
# Typing
###############################################################################

P = ParamSpec("P")

R = TypeVar("R")

###############################################################################
# Thread Safety
###############################################################################

_INITIALIZATION_LOCK = threading.Lock()

_INITIALIZED = False

###############################################################################
# Formatter
###############################################################################


def build_formatter() -> logging.Formatter:
    """
    Build the application log formatter.
    """

    return logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )


###############################################################################
# Console Handler
###############################################################################


def build_console_handler() -> logging.Handler:
    """
    Create console log handler.
    """

    handler = logging.StreamHandler()

    handler.setFormatter(
        build_formatter(),
    )

    handler.setLevel(
        settings.logging.level,
    )

    return handler


###############################################################################
# File Handler
###############################################################################


def build_file_handler() -> logging.Handler:
    """
    Create rotating application log handler.
    """

    logfile = (
        settings.base.log_directory
        / LOG_FILE_NAME
    )

    handler = logging.handlers.RotatingFileHandler(
        filename=logfile,
        maxBytes=(
            settings.logging.max_file_size_mb
            * 1024
            * 1024
        ),
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
    )

    handler.setFormatter(
        build_formatter(),
    )

    handler.setLevel(
        settings.logging.level,
    )

    return handler


###############################################################################
# Error Handler
###############################################################################


def build_error_handler() -> logging.Handler:
    """
    Dedicated error log.
    """

    logfile = (
        settings.base.log_directory
        / "errors.log"
    )

    handler = logging.handlers.RotatingFileHandler(
        filename=logfile,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )

    handler.setFormatter(
        build_formatter(),
    )

    handler.setLevel(
        logging.ERROR,
    )

    return handler


###############################################################################
# Configure Logging
###############################################################################


def configure_logging() -> None:
    """
    Configure root logger.

    Safe to call multiple times.
    """

    global _INITIALIZED

    with _INITIALIZATION_LOCK:

        if _INITIALIZED:
            return

        settings.base.log_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        root = logging.getLogger()

        root.setLevel(
            settings.logging.level,
        )

        root.handlers.clear()

        if settings.logging.console_enabled:

            root.addHandler(
                build_console_handler(),
            )

        if settings.logging.file_enabled:

            root.addHandler(
                build_file_handler(),
            )

            root.addHandler(
                build_error_handler(),
            )

        _INITIALIZED = True


###############################################################################
# Logger Factory
###############################################################################


def get_logger(
    name: str,
) -> logging.Logger:
    """
    Return configured logger.
    """

    configure_logging()

    return logging.getLogger(name)


###############################################################################
# Performance Decorator
###############################################################################


def log_execution_time(
    logger: logging.Logger,
) -> Callable[
    [Callable[P, R]],
    Callable[P, R],
]:
    """
    Log execution time of a function.
    """

    def decorator(
        function: Callable[P, R],
    ) -> Callable[P, R]:

        @functools.wraps(function)
        def wrapper(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:

            start = time.perf_counter()

            try:

                return function(
                    *args,
                    **kwargs,
                )

            finally:

                elapsed = (
                    time.perf_counter()
                    - start
                )

                logger.info(
                    "Execution completed | Function=%s | %.3f sec",
                    function.__name__,
                    elapsed,
                )

        return wrapper

    return decorator


###############################################################################
# Exception Decorator
###############################################################################


def log_exceptions(
    logger: logging.Logger,
) -> Callable[
    [Callable[P, R]],
    Callable[P, R],
]:
    """
    Automatically log uncaught exceptions.
    """

    def decorator(
        function: Callable[P, R],
    ) -> Callable[P, R]:

        @functools.wraps(function)
        def wrapper(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:

            try:

                return function(
                    *args,
                    **kwargs,
                )

            except Exception:

                logger.exception(
                    "Unhandled exception in %s",
                    function.__name__,
                )

                raise

        return wrapper

    return decorator


###############################################################################
# Banner Logging
###############################################################################


def log_banner(
    logger: logging.Logger,
    title: str,
) -> None:
    """
    Log application banner.
    """

    separator = "=" * 80

    logger.info(separator)
    logger.info(title)
    logger.info(separator)


###############################################################################
# Configuration Dump
###############################################################################


def log_configuration(
    logger: logging.Logger,
) -> None:
    """
    Log runtime configuration.
    """

    logger.info(
        "Project Root      : %s",
        settings.base.project_root,
    )

    logger.info(
        "Output Directory  : %s",
        settings.base.output_directory,
    )

    logger.info(
        "Cache Directory   : %s",
        settings.base.cache_directory,
    )

    logger.info(
        "Log Directory     : %s",
        settings.base.log_directory,
    )

    logger.info(
        "Workers           : %d",
        settings.thread_pool.max_workers,
    )

    logger.info(
        "HTTP Timeout      : %d sec",
        settings.http.timeout_seconds,
    )

    logger.info(
        "News Lookback     : %d days",
        settings.news.lookback_days,
    )


###############################################################################
# Initialize Logging
###############################################################################

configure_logging()