"""
Market Model
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel
from pydantic import ConfigDict


class MarketData(

    BaseModel,

):

    model_config = ConfigDict(

        frozen=True,

        from_attributes=True,

    )

    symbol: str

    trading_date: date

    open: float | None = None

    high: float | None = None

    low: float | None = None

    close: float |None = None

    adj_close: float | None = None

    volume: int | None = None