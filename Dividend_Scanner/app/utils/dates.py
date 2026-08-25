"""
Date Utilities
"""

from __future__ import annotations

from datetime import date
from datetime import datetime


def today() -> date:

    return date.today()


def now() -> datetime:

    return datetime.now()


def to_date(
    value,
) -> date | None:

    if value is None:

        return None

    if isinstance(
        value,
        date,
    ):

        return value

    try:

        return datetime.fromisoformat(
            str(value)
        ).date()

    except Exception:

        return None


def to_datetime(
    value,
) -> datetime | None:

    if value is None:

        return None

    if isinstance(
        value,
        datetime,
    ):

        return value

    try:

        return datetime.fromisoformat(
            str(value)
        )

    except Exception:

        return None