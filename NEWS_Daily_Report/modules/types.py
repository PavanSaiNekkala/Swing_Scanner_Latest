"""
===============================================================================
File: types.py

Description:
    Common data models used throughout the NSE Daily Report application.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# =============================================================================
# News Model
# =============================================================================


@dataclass(slots=True)
class NewsItem:
    """
    Represents a single news article.
    """

    title: str
    publisher: str
    published: datetime
    link: str


# =============================================================================
# Stock Quote Model
# =============================================================================


@dataclass(slots=True)
class StockQuote:
    """
    Daily stock market data.
    """

    symbol: str
    company: str

    open: float
    high: float
    low: float
    close: float

    previous_close: float

    volume: int

    return_pct: float = 0.0


# =============================================================================
# Report Model
# =============================================================================


@dataclass(slots=True)
class StockReport:
    """
    Represents one row in the final Excel report.
    """

    rank: int

    symbol: str

    company: str

    return_pct: float

    previous_close: float

    close: float

    top_headline: str = ""

    news: list[str] = field(default_factory=list)


# =============================================================================
# Download Result
# =============================================================================


@dataclass(slots=True)
class DownloadResult:
    """
    Result of a market data download.
    """

    success: bool

    symbol: str

    message: str = ""

    data: Optional[StockQuote] = None


# =============================================================================
# News Result
# =============================================================================


@dataclass(slots=True)
class NewsResult:
    """
    Result returned by the news service.
    """

    success: bool

    symbol: str

    articles: list[NewsItem] = field(default_factory=list)

    error: str = ""


# =============================================================================
# Application Statistics
# =============================================================================


@dataclass(slots=True)
class RunStatistics:
    """
    Execution summary.
    """

    total_symbols: int = 0

    successful_downloads: int = 0

    failed_downloads: int = 0

    gainers: int = 0

    losers: int = 0

    execution_time: float = 0.0


# =============================================================================
# Excel Report Metadata
# =============================================================================


@dataclass(slots=True)
class ReportMetadata:
    """
    Metadata for the generated report.
    """

    report_name: str

    generated_at: datetime

    total_records: int

    gainers: int

    losers: int