"""
Database Tables
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database.database import Base


# ---------------------------------------------------------
# Company
# ---------------------------------------------------------

class CompanyTable(
    Base,
):

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    symbol: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
    )

    company_name: Mapped[str | None]

    sector: Mapped[str | None]

    industry: Mapped[str | None]

    market_cap: Mapped[float | None] = mapped_column(
        Float,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


# ---------------------------------------------------------
# Dividend
# ---------------------------------------------------------

class DividendTable(
    Base,
):

    __tablename__ = "dividends"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    symbol: Mapped[str] = mapped_column(
        String,
        index=True,
    )

    ex_date: Mapped[datetime | None] = mapped_column(
        Date,
    )

    record_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
    )

    payment_date: Mapped[datetime | None] = mapped_column(
        Date,
        nullable=True,
    )

    amount: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    dividend_type: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ---------------------------------------------------------
# Market
# ---------------------------------------------------------

class MarketTable(
    Base,
):

    __tablename__ = "market_data"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    symbol: Mapped[str] = mapped_column(
        String,
        index=True,
    )

    trading_date: Mapped[datetime] = mapped_column(
        Date,
    )

    open: Mapped[float | None] = mapped_column(
        Float,
    )

    high: Mapped[float | None] = mapped_column(
        Float,
    )

    low: Mapped[float | None] = mapped_column(
        Float,
    )

    close: Mapped[float | None] = mapped_column(
        Float,
    )

    adj_close: Mapped[float | None] = mapped_column(

        Float,

    )

    volume: Mapped[int | None] = mapped_column(
        Integer,
    )


# ---------------------------------------------------------
# News
# ---------------------------------------------------------

class NewsArticleTable(
    Base,
):

    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    symbol: Mapped[str]

    headline: Mapped[str]

    summary: Mapped[str | None] = mapped_column(
        Text,
    )

    source: Mapped[str | None]

    provider: Mapped[str | None]

    url: Mapped[str] = mapped_column(
        String,
        unique=True,
    )

    published_at: Mapped[datetime]

    category: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )


# ---------------------------------------------------------
# Scan Results
# ---------------------------------------------------------


class ScanResultTable(
    Base,
):

    __tablename__ = "scan_results"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    symbol: Mapped[str] = mapped_column(
        String,
        index=True,
    )

    score: Mapped[float | None]

    recommendation: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )