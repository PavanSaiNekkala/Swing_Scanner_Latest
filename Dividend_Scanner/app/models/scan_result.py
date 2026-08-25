"""
Scan Result Model

Contains raw data fetched from providers together with
all derived analytics required for the final Excel report.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.models.company import Company
from app.models.dividend import Dividend
from app.models.market import MarketData
from app.models.news import NewsArticle
from app.models.score import Score


class ScanResult(
    BaseModel,
):

    model_config = ConfigDict(

        frozen=False,

        from_attributes=True,

    )

    # ---------------------------------------------------------
    # Raw Provider Data
    # ---------------------------------------------------------

    company: Company

    dividend: list[Dividend] = Field(

        default_factory=list,

    )

    market: list[MarketData] = Field(

        default_factory=list,

    )

    news: list[NewsArticle] = Field(

        default_factory=list,

    )

    # ---------------------------------------------------------
    # Dividend Analytics
    # ---------------------------------------------------------

    annual_dividend: float | None = None

    average_dividend: float | None = None

    dividend_yield: float | None = None

    years_paying: int | None = None

    dividend_count: int = 0

    # ---------------------------------------------------------
    # OHLC Window
    # ---------------------------------------------------------

    d3_close: float | None = None

    d2_close: float | None = None

    d1_close: float | None = None

    d0_close: float | None = None

    p1_close: float | None = None

    p2_close: float | None = None

    p3_close: float | None = None

    # ---------------------------------------------------------
    # Return Analytics
    # ---------------------------------------------------------

    d3_to_d0_return: float | None = None

    d2_to_d0_return: float | None = None

    d1_to_d0_return: float | None = None

    d0_to_p1_return: float | None = None

    d0_to_p2_return: float | None = None

    d0_to_p3_return: float | None = None

    window_return: float | None = None

    # ---------------------------------------------------------
    # Volume Analytics
    # ---------------------------------------------------------

    volume_change: float | None = None

    average_volume: float | None = None

    # ---------------------------------------------------------
    # News Analytics
    # ---------------------------------------------------------

    news_count: int = 0

    latest_news: str | None = None

    latest_news_date: datetime | None = None

    news_sentiment: str | None = None

    # ---------------------------------------------------------
    # Final Composite Score
    # ---------------------------------------------------------

    score: Score | None = None