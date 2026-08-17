"""
Application-wide immutable constants.

This module defines constants that are shared across the application.
Only values that are effectively immutable should be placed here.

Do NOT store:
    - API Keys
    - Environment variables
    - User configurable values

Those belong in config.settings.

Author:
    Pavan Sai Nekkala

Project:
    NEWS_REPORT

Python:
    3.12+
"""

from __future__ import annotations

from pathlib import Path

###############################################################################
# Project Information
###############################################################################

PROJECT_NAME: str = "NEWS_REPORT"

APPLICATION_NAME: str = "NSE Market News Intelligence"

APPLICATION_VERSION: str = "1.0.0"

AUTHOR: str = "Pavan Sai Nekkala"

###############################################################################
# Directories
###############################################################################

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

CONFIG_DIR: Path = PROJECT_ROOT / "config"

DATA_DIR: Path = PROJECT_ROOT / "data"

PROVIDER_DIR: Path = DATA_DIR / "providers"

UNIVERSE_DIR: Path = DATA_DIR / "universe"

OUTPUT_DIR: Path = PROJECT_ROOT / "output"

REPORT_DIR: Path = PROJECT_ROOT / "reports"

LOG_DIR: Path = PROJECT_ROOT / "logs"

CACHE_DIR: Path = PROJECT_ROOT / "cache"

###############################################################################
# Input Files
###############################################################################

NSE_UNIVERSE_FILE: Path = (
    UNIVERSE_DIR
    / "nse_universe.csv"
)

###############################################################################
# Output Files
###############################################################################

EXCEL_REPORT_FILE: Path = (
    OUTPUT_DIR
    / "NSE_Market_Report.xlsx"
)

###############################################################################
# Cache
###############################################################################

NEWS_CACHE_DIR: Path = (
    CACHE_DIR
    / "news"
)

MARKET_CACHE_DIR: Path = (
    CACHE_DIR
    / "market"
)

###############################################################################
# Date Formats
###############################################################################

DATE_FORMAT: str = "%Y-%m-%d"

DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

TIMESTAMP_FORMAT: str = "%Y%m%d_%H%M%S"

###############################################################################
# Timezone
###############################################################################

TIMEZONE: str = "Asia/Kolkata"

###############################################################################
# Market Constants
###############################################################################

NSE_EXCHANGE: str = "NSE"

YAHOO_SUFFIX: str = ".NS"

TOP_GAINERS_LIMIT: int = 20

TOP_LOSERS_LIMIT: int = 20

NEWS_LOOKBACK_DAYS: int = 7

NEWS_PER_STOCK: int = 5

###############################################################################
# Parallel Processing
###############################################################################

DEFAULT_MAX_WORKERS: int = 8

DEFAULT_BATCH_SIZE: int = 50

###############################################################################
# HTTP
###############################################################################

DEFAULT_TIMEOUT_SECONDS: int = 30

MAX_RETRY_COUNT: int = 3

RETRY_BACKOFF_SECONDS: int = 2

###############################################################################
# News Ranking
###############################################################################

RECENCY_WEIGHT: float = 0.40

SOURCE_WEIGHT: float = 0.30

RELEVANCE_WEIGHT: float = 0.20

HEADLINE_WEIGHT: float = 0.10

###############################################################################
# Logging
###############################################################################

LOG_FILE_NAME: str = "news_report.log"

LOG_FORMAT: str = (
    "%(asctime)s | "
    "%(levelname)-8s | "
    "%(name)s | "
    "%(message)s"
)

LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

###############################################################################
# Excel
###############################################################################

SUMMARY_SHEET: str = "Summary"

TOP_GAINERS_SHEET: str = "Top_20_Gainers"

TOP_LOSERS_SHEET: str = "Top_20_Losers"

GAINERS_NEWS_SHEET: str = "Gainers_News"

LOSERS_NEWS_SHEET: str = "Losers_News"

AI_INSIGHTS_SHEET: str = "AI_Insights"

###############################################################################
# News Sources
###############################################################################

GOOGLE_NEWS: str = "Google News"

NEWS_API: str = "NewsAPI"

MARKETAUX: str = "MarketAux"

FINNHUB: str = "Finnhub"

###############################################################################
# HTTP User Agent
###############################################################################

DEFAULT_USER_AGENT: str = (
    "NEWS_REPORT/1.0 "
    "(Institutional Market Intelligence)"
)