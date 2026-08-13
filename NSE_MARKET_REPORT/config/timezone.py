from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """
    Return the current timezone-aware timestamp in IST.
    """
    return datetime.now(IST)


def format_ist(
    value: datetime | None = None,
) -> str:
    """
    Return an IST timestamp formatted for reports/logging.
    """

    if value is None:
        value = now_ist()
    elif value.tzinfo is None:
        value = value.replace(
            tzinfo=IST
        )
    else:
        value = value.astimezone(IST)

    return value.strftime(
        "%Y-%m-%d %H:%M:%S IST"
    )