"""
Validation Helpers
"""

from __future__ import annotations

from datetime import date
from datetime import datetime


def valid_symbol(

    symbol,

) -> bool:

    return (

        isinstance(
            symbol,
            str,
        )

        and bool(
            symbol.strip()
        )

    )


def valid_date(

    value,

) -> bool:

    return isinstance(

        value,

        (

            date,

            datetime,

        ),

    )


def valid_price(

    value,

) -> bool:

    return (

        isinstance(

            value,

            (

                int,

                float,

            ),

        )

        and value >= 0

    )


def valid_volume(

    value,

) -> bool:

    return (

        isinstance(

            value,

            int,

        )

        and value >= 0

    )