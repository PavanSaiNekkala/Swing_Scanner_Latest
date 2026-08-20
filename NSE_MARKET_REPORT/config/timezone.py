"""
config/timezone.py

Central timezone utilities for the NSE Market Report project.
"""

from __future__ import annotations

from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo


###############################################################################
# CONSTANTS
###############################################################################

IST = ZoneInfo(
    "Asia/Kolkata"
)


###############################################################################
# CURRENT TIME
###############################################################################

def ist_now() -> datetime:
    """
    Return the current datetime in IST.
    """

    return datetime.now(
        IST
    )


def now_ist() -> datetime:
    """
    Backward-compatible alias for ist_now().
    """

    return ist_now()


def now() -> datetime:
    """
    Return the current application datetime in IST.
    """

    return ist_now()


###############################################################################
# CURRENT DATE
###############################################################################

def ist_today() -> date:
    """
    Return the current date in IST.
    """

    return ist_now().date()


###############################################################################
# FORMATTING
###############################################################################

def format_ist(
    value: datetime | None = None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    Format a datetime in IST.

    Parameters
    ----------
    value:
        Datetime to format. When omitted, current IST time is used.

    fmt:
        strftime format.
    """

    timestamp = (
        value
        if value is not None
        else ist_now()
    )

    if timestamp.tzinfo is None:

        timestamp = timestamp.replace(
            tzinfo=IST
        )

    else:

        timestamp = timestamp.astimezone(
            IST
        )

    return timestamp.strftime(
        fmt
    )


def ist_timestamp() -> str:
    """
    Return the current IST timestamp.

    Format:
        YYYY-MM-DD HH:MM:SS
    """

    return format_ist()


def timestamp() -> str:
    """
    Backward-compatible alias for ist_timestamp().
    """

    return ist_timestamp()


###############################################################################
# DATE FORMATTING
###############################################################################

def format_ist_date(
    value: datetime | date | None = None,
    fmt: str = "%Y-%m-%d",
) -> str:
    """
    Format a datetime/date using IST-aware project conventions.
    """

    if value is None:

        value = ist_now()

    if isinstance(
        value,
        datetime,
    ):

        if value.tzinfo is None:

            value = value.replace(
                tzinfo=IST
            )

        else:

            value = value.astimezone(
                IST
            )

    return value.strftime(
        fmt
    )