"""
Centralized IST date/time utilities.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """
    Return current datetime in IST.
    """
    return datetime.now(
        IST,
    )


def timestamp() -> str:
    """
    Example:
    2026-08-20 12:30:45 IST
    """
    return now_ist().strftime(
        "%Y-%m-%d %H:%M:%S IST",
    )


def report_filename_timestamp() -> str:
    """
    Example:
    20260820_123045
    """
    return now_ist().strftime(
        "%Y%m%d_%H%M%S",
    )


def report_date() -> str:
    """
    Example:
    20-Aug-2026
    """
    return now_ist().strftime(
        "%d-%b-%Y",
    )