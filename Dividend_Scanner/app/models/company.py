"""
Company Model
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class Company(

    BaseModel,

):

    model_config = ConfigDict(

        frozen=True,

        from_attributes=True,

    )

    symbol: str

    company_name: str | None = None

    sector: str | None = None

    industry: str | None = None

    market_cap: float | None = None

    currency: str | None = None

    exchange: str | None = None

    country: str | None = None