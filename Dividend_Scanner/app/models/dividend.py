"""
Dividend Model
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from pydantic import ConfigDict


class Dividend(

    BaseModel,

):

    model_config = ConfigDict(

        frozen=True,

        from_attributes=True,

    )

    symbol: str

    ex_date: date | None = None

    record_date: date | None = None

    payment_date: date | None = None

    amount: float | None = None

    dividend_type: str | None = None

    dividend_yield: float | None = None

    currency: str | None = None

    #provider: str | None = None