"""
config/config.py

Central configuration for the NSE Market Report project.

Author: Your Name
"""

from pathlib import Path
import os

from dotenv import load_dotenv

# =============================================================================
# LOAD ENVIRONMENT VARIABLES
# =============================================================================

load_dotenv()

# =============================================================================
# PROJECT DIRECTORIES
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_EXCEL_DIR = OUTPUT_DIR / "excel"
OUTPUT_CSV = OUTPUT_DIR / "csv"
OUTPUT_EXCEL = (
    OUTPUT_EXCEL_DIR
    / "NSE_Market_Report.xlsx"
)

LOG_DIR = PROJECT_ROOT / "logs"
CACHE_DIR = PROJECT_ROOT / "cache"

# Create required directories

for directory in (
    OUTPUT_EXCEL_DIR,
    OUTPUT_CSV,
    LOG_DIR,
    CACHE_DIR,
):
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

# =============================================================================
# API KEYS
# =============================================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")

# =============================================================================
# MARKET SETTINGS
# =============================================================================

MARKET = "NSE"

TIMEZONE = "Asia/Kolkata"

TOP_GAINERS_COUNT = 30
TOP_LOSERS_COUNT = 30

# =============================================================================
# NETWORK SETTINGS
# =============================================================================

DEFAULT_TIMEOUT = 20          # seconds
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 2           # exponential backoff
REQUEST_DELAY = 0.50          # seconds between requests
MAX_WORKERS = 5               # ThreadPoolExecutor workers

# =============================================================================
# CACHE SETTINGS
# =============================================================================

CACHE_TTL_MINUTES = 15

# =============================================================================
# GOOGLE NEWS SETTINGS
# =============================================================================

GOOGLE_NEWS_LANGUAGE = "en-IN"
GOOGLE_NEWS_COUNTRY = "IN"

MAX_NEWS_ARTICLES = 5
MIN_NEWS_RELEVANCE_SCORE = 25

# =============================================================================
# FULL NEWS UNIVERSE SETTINGS
# =============================================================================

NEWS_UNIVERSE_FILE = (
    PROJECT_ROOT
    / "data"
    / "universe"
    / "news_universe.csv"
)

NEWS_UNIVERSE_OUTPUT = (
    OUTPUT_EXCEL_DIR
    / "NSE_News_Universe.xlsx"
)

NEWS_UNIVERSE_LOOKBACK_DAYS = 15

NEWS_UNIVERSE_MAX_ARTICLES = 5

NEWS_UNIVERSE_BATCH_SIZE = 20

# =============================================================================
# GENERAL NEWS SETTINGS
# =============================================================================

MAX_NEWS_PER_STOCK = 5

NEWS_LANGUAGE = "en"

NEWS_LOOKBACK_DAYS = 15

# =============================================================================
# AI SETTINGS
# =============================================================================

AI_PROVIDER = "gemini"

MODEL_NAME = "gemini-3.1-flash-lite"

TEMPERATURE = 0.20

MAX_TOKENS = 500

# =============================================================================
# EXCEL SETTINGS
# =============================================================================

HEADER_COLOR = "1F4E78"

GAINER_COLOR = "C6EFCE"

LOSER_COLOR = "FFC7CE"

WRAP_TEXT = True

AUTO_FILTER = True

FREEZE_HEADER = True

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"

LOG_FILE = LOG_DIR / "market.log"

# =============================================================================
# DATE & TIME FORMATS
# =============================================================================

DATE_FORMAT = "%Y-%m-%d"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

###############################################################################
# NEWS PROVIDERS
###############################################################################

ENABLED_NEWS_PROVIDERS = [
    "google",
    "newsapi",
]

PRIMARY_NEWS_PROVIDER = "google"

FALLBACK_NEWS_PROVIDER = "newsapi"

NEWS_REQUEST_TIMEOUT = DEFAULT_TIMEOUT

NEWS_MAX_RETRIES = DEFAULT_RETRIES

# =============================================================================
# REPORT COLUMNS
# =============================================================================

REPORT_COLUMNS = [
    "Timestamp",
    "Category",
    "Symbol",
    "Company",
    "CMP",
    "Open",
    "High",
    "Low",
    "Previous Close",
    "Close",
    "Volume",
    "1 Day Change %",
    "Top Headline",
    "Recent News",
    "Final Remarks",
]
