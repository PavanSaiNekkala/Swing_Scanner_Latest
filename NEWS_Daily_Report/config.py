"""
config.py

Global configuration for the NEWS Daily Report Generator.
"""

from pathlib import Path
from datetime import datetime

# ==============================================================================
# Project Directories
# ==============================================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

CACHE_DIR = DATA_DIR / "cache"

ARCHIVE_DIR = DATA_DIR / "archive"

OUTPUT_DIR = BASE_DIR / "output"

OUTPUT_EXCEL_DIR = OUTPUT_DIR / "excel"

OUTPUT_REPORT_DIR = OUTPUT_DIR / "reports"

LOG_DIR = BASE_DIR / "logs"

# ==============================================================================
# Input Files
# ==============================================================================

INPUT_CSV = DATA_DIR / "nse_universe.csv"

# ==============================================================================
# Output Files
# ==============================================================================

TODAY = datetime.now().strftime("%Y%m%d")

OUTPUT_FILE = OUTPUT_EXCEL_DIR / f"NEWS_Daily_Report_{TODAY}.xlsx"

# Backward compatibility
OUTPUT_EXCEL = OUTPUT_FILE

# ==============================================================================
# Yahoo Finance
# ==============================================================================

YF_PERIOD = "5d"

YF_INTERVAL = "1d"

REQUEST_TIMEOUT = 30

MAX_RETRIES = 3

MAX_WORKERS = 10

# ==============================================================================
# Ranking
# ==============================================================================

TOP_GAINERS = 20

TOP_LOSERS = 20

# ==============================================================================
# News
# ==============================================================================

TOP_HEADLINES = 1

RECENT_NEWS = 5

MAX_NEWS = RECENT_NEWS

# ==============================================================================
# Logging
# ==============================================================================

LOG_LEVEL = "INFO"

LOG_FILE = LOG_DIR / "daily_report.log"

# ==============================================================================
# Excel
# ==============================================================================

SHEET_GAINERS = "Gainers"

SHEET_LOSERS = "Losers"

COLUMN_HEADERS = [
    "Rank",
    "Symbol",
    "Company",
    "Open",
    "High",
    "Low",
    "Close",
    "Previous Close",
    "Return %",
    "Top Headline",
    "News 1",
    "News 2",
    "News 3",
    "News 4",
    "News 5",
]

# ==============================================================================
# Validation
# ==============================================================================

REQUIRED_COLUMNS = [
    "Symbol",
]

# ==============================================================================
# Create Directories
# ==============================================================================

for directory in (
    DATA_DIR,
    CACHE_DIR,
    ARCHIVE_DIR,
    OUTPUT_DIR,
    OUTPUT_EXCEL_DIR,
    OUTPUT_REPORT_DIR,
    LOG_DIR,
):
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )
