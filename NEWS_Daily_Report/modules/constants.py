"""
===============================================================================
File: constants.py

Description:
    Centralized constants used throughout the NEWS Daily Report application.

Author:
    Pavan Sai

===============================================================================
"""

from enum import Enum

# =============================================================================
# Excel Sheet Names
# =============================================================================


class SheetNames(str, Enum):
    GAINERS = "Gainers"
    LOSERS = "Losers"


# =============================================================================
# Input CSV Columns
# =============================================================================


class CSVColumns(str, Enum):
    SYMBOL = "Symbol"


# =============================================================================
# Market Data Columns
# =============================================================================


class MarketColumns(str, Enum):
    SYMBOL = "Symbol"
    COMPANY = "Company"

    OPEN = "Open"
    HIGH = "High"
    LOW = "Low"
    CLOSE = "Close"

    PREVIOUS_CLOSE = "Previous Close"

    ADJ_CLOSE = "Adj Close"

    VOLUME = "Volume"

    RETURN = "Return %"


# =============================================================================
# News Columns
# =============================================================================


class NewsColumns(str, Enum):
    HEADLINE = "Top Headline"
    LATEST = "Latest News"

    NEWS1 = "News 1"
    NEWS2 = "News 2"
    NEWS3 = "News 3"


NEWS_COLUMNS = [
    NewsColumns.HEADLINE.value,
    NewsColumns.LATEST.value,
    NewsColumns.NEWS1.value,
    NewsColumns.NEWS2.value,
    NewsColumns.NEWS3.value,
]

# =============================================================================
# Output Columns
# =============================================================================

REPORT_COLUMNS = [
    "Rank",
    "Ticker",
    "Company",
    "Return %",
    "Previous Close",
    "Close",
    "Top Headline",
    "Latest News",
    "News 1",
    "News 2",
    "News 3",
]

# =============================================================================
# Yahoo Finance
# =============================================================================

YFINANCE_SUFFIX = ".NS"

DOWNLOAD_PERIOD = "5d"

DOWNLOAD_INTERVAL = "1d"

# =============================================================================
# Ranking
# =============================================================================

TOP_GAINERS = 20

TOP_LOSERS = 20

# =============================================================================
# News
# =============================================================================

NEWS_LOOKBACK_DAYS = 30

TOP_NEWS = 3

# =============================================================================
# Excel
# =============================================================================

DEFAULT_COLUMN_WIDTH = 25

HEADER_ROW_HEIGHT = 22

DATA_ROW_HEIGHT = 20

# =============================================================================
# Logging
# =============================================================================

LOGGER_NAME = "NEWS_DAILY_REPORT"

# =============================================================================
# Date Formats
# =============================================================================

DATE_FORMAT = "%Y-%m-%d"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

TIMEZONE = "Asia/Kolkata"

# =============================================================================
# Retry Configuration
# =============================================================================

DEFAULT_RETRIES = 3

DEFAULT_DELAY = 2

# =============================================================================
# HTTP
# =============================================================================

DEFAULT_TIMEOUT = 30

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/137.0 Safari/537.36"
)

# =============================================================================
# Colors
# =============================================================================

GAINER_FILL = "C6EFCE"

LOSER_FILL = "FFC7CE"

HEADER_FILL = "4F81BD"

WHITE_FONT = "FFFFFF"

BLACK_FONT = "000000"

# =============================================================================
# Supported File Extensions
# =============================================================================

CSV_EXTENSION = ".csv"

EXCEL_EXTENSION = ".xlsx"

LOG_EXTENSION = ".log"