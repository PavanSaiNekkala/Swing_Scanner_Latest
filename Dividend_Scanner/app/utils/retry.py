"""
Retry Utilities
"""

from __future__ import annotations

from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from config.settings import MAX_RETRIES
from config.settings import RETRY_BACKOFF


retry_network = retry(

    stop=stop_after_attempt(
        MAX_RETRIES
    ),

    wait=wait_exponential(
        multiplier=RETRY_BACKOFF,
    ),

    retry=retry_if_exception_type(
        Exception,
    ),

    reraise=True,

)