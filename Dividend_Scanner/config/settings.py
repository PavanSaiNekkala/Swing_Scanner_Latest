"""
Application Settings

Centralized configuration for the Dividend Scanner.

All filesystem paths are resolved relative to the project root.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------
# Project
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------
# Data Directories
# ---------------------------------------------------------

DATA_DIR = PROJECT_ROOT / "data"

INPUT_DIR = DATA_DIR / "input"

OUTPUT_DIR = DATA_DIR / "output"

CACHE_DIR = DATA_DIR / "cache"

DATABASE_DIR = DATA_DIR / "database"

# ---------------------------------------------------------
# Files
# ---------------------------------------------------------

INPUT_FILE = INPUT_DIR / "nse_universe.csv"

OUTPUT_FILE = OUTPUT_DIR / "dividend_report.xlsx"

DATABASE_NAME = "scanner.db"


DATABASE_FILE = DATABASE_DIR / DATABASE_NAME

# ---------------------------------------------------------
# Database
# ---------------------------------------------------------

DATABASE_FILE = DATABASE_DIR / "scanner.db"

SQLITE_URL = f"sqlite:///{DATABASE_FILE}"

# ---------------------------------------------------------
# Cache
# ---------------------------------------------------------

DISKCACHE_DIR = CACHE_DIR / "disk"

CACHE_TTL_DAYS = 7

# ---------------------------------------------------------
# Requests
# ---------------------------------------------------------

REQUEST_TIMEOUT = 20

MAX_RETRIES = 3

RETRY_BACKOFF = 2

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/138.0 Safari/537.36"
)

# ---------------------------------------------------------
# Scanner
# ---------------------------------------------------------

DEFAULT_EXCHANGE = "XNSE"

WINDOW_BEFORE = 3

WINDOW_AFTER = 3

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

LOG_LEVEL = "INFO"

LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level:<8} | "
    "{extra[module]} | "
    "{message}"
)

# ---------------------------------------------------------
# Create Directories
# ---------------------------------------------------------

for directory in (

    DATA_DIR,

    INPUT_DIR,

    OUTPUT_DIR,

    CACHE_DIR,

    DATABASE_DIR,

    DISKCACHE_DIR,

):

    directory.mkdir(

        parents=True,

        exist_ok=True,

    )