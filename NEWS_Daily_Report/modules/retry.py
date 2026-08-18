"""
===============================================================================
File: retry.py

Description:
    Generic retry decorator with exponential backoff.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

import random
import time
from functools import wraps
from typing import Callable, Tuple, Type

from modules.logger import logger
from modules.exceptions import RetryLimitExceededError


def retry(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    retries: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    jitter: bool = True,
):
    """
    Retry decorator.

    Parameters
    ----------
    exceptions : tuple
        Exceptions eligible for retry.

    retries : int
        Number of retry attempts.

    delay : float
        Initial delay in seconds.

    backoff : float
        Exponential multiplier.

    jitter : bool
        Add random jitter to avoid retry storms.
    """

    def decorator(func: Callable):

        @wraps(func)
        def wrapper(*args, **kwargs):

            current_delay = delay
            last_exception = None

            for attempt in range(1, retries + 1):

                try:
                    return func(*args, **kwargs)

                except exceptions as exc:

                    last_exception = exc

                    logger.warning(
                        "[Retry %d/%d] %s failed: %s",
                        attempt,
                        retries,
                        func.__name__,
                        exc,
                    )

                    if attempt == retries:
                        break

                    sleep_time = current_delay

                    if jitter:
                        sleep_time += random.uniform(0, 1)

                    logger.info(
                        "Sleeping %.2f seconds before retry...",
                        sleep_time,
                    )

                    time.sleep(sleep_time)

                    current_delay *= backoff

            raise RetryLimitExceededError(
                f"{func.__name__} failed after {retries} attempts."
            ) from last_exception

        return wrapper

    return decorator