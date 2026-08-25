"""
News Model
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class NewsArticle(

    BaseModel,

):

    model_config = ConfigDict(

        frozen=True,

        from_attributes=True,

    )

    symbol: str

    ticker: str | None = None

    stock: str | None = None

    company_name: str | None = None

    headline: str

    summary: str | None = None

    source: str | None = None

    provider: str | None = None

    url: str

    published_at: datetime

    category: str | None = None