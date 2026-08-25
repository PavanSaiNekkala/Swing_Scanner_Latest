"""
General Helper Functions
"""

from __future__ import annotations

from typing import Iterable


def safe_float(
    value,
) -> float | None:

    try:

        if value is None:

            return None

        return float(value)

    except Exception:

        return None


def safe_int(
    value,
) -> int | None:

    try:

        if value is None:

            return None

        return int(value)

    except Exception:

        return None


def percentage_change(

    old,

    new,

) -> float | None:

    if (

        old is None

        or new is None

        or old == 0

    ):

        return None

    return round(

        (

            new - old

        )

        / old

        * 100,

        2,

    )


def first(

    values: Iterable,

):

    for item in values:

        return item

    return None