"""
Runtime application settings.

This module is responsible for loading and validating all configurable
runtime settings for the NEWS_REPORT application.

Responsibilities
----------------
- Load environment variables
- Provide strongly typed settings
- Validate runtime configuration
- Initialize application directories
- Expose a singleton settings instance

Do NOT place immutable application constants here.
Use config.constants for project-wide constants.

Author:
    Pavan Sai Nekkala

Project:
    NEWS_REPORT

Python:
    3.12+
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

from config.constants import (
    CACHE_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)

###############################################################################
# Load Environment Variables
###############################################################################

load_dotenv(
    PROJECT_ROOT / ".env",
)

###############################################################################
# Helper Functions
###############################################################################


def get_env(
    key: str,
    default: str | None = None,
) -> str:
    """
    Return an environment variable.

    Raises
    ------
    RuntimeError
        If the environment variable is required but missing.
    """

    value = os.getenv(
        key,
        default,
    )

    if value is None:

        raise RuntimeError(
            f"Missing environment variable: {key}"
        )

    return value


def get_env_int(
    key: str,
    default: int,
) -> int:
    """
    Return an integer environment variable.
    """

    value = os.getenv(
        key,
    )

    if value is None:

        return default

    try:

        return int(value)

    except ValueError as exc:

        raise RuntimeError(
            f"Environment variable '{key}' "
            "must be an integer."
        ) from exc


def get_env_float(
    key: str,
    default: float,
) -> float:
    """
    Return a floating-point environment variable.
    """

    value = os.getenv(
        key,
    )

    if value is None:

        return default

    try:

        return float(value)

    except ValueError as exc:

        raise RuntimeError(
            f"Environment variable '{key}' "
            "must be a float."
        ) from exc


def get_env_bool(
    key: str,
    default: bool,
) -> bool:
    """
    Return a boolean environment variable.
    """

    value = os.getenv(
        key,
    )

    if value is None:

        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


###############################################################################
# Base Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class BaseSettings:
    """
    Base runtime settings shared by the application.
    """

    project_root: Path = PROJECT_ROOT

    output_directory: Path = OUTPUT_DIR

    cache_directory: Path = CACHE_DIR

    log_directory: Path = LOG_DIR

    debug: bool = get_env_bool(
        "DEBUG",
        False,
    )


###############################################################################
# Directory Initialization
###############################################################################


def initialize_directories() -> None:
    """
    Create required runtime directories.
    """

    directories: Final = (
        OUTPUT_DIR,
        CACHE_DIR,
        LOG_DIR,
    )

    for directory in directories:

        directory.mkdir(
            parents=True,
            exist_ok=True,
        )


###############################################################################
# API Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class ApiSettings:
    """
    External service API credentials.
    """

    news_api_key: str = get_env(
        "NEWS_API_KEY",
        "",
    )

    marketaux_api_key: str = get_env(
        "MARKETAUX_API_KEY",
        "",
    )

    finnhub_api_key: str = get_env(
        "FINNHUB_API_KEY",
        "",
    )

    openai_api_key: str = get_env(
        "OPENAI_API_KEY",
        "",
    )

    gemini_api_key: str = get_env(
        "GEMINI_API_KEY",
        "",
    )


###############################################################################
# Thread Pool Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class ThreadPoolSettings:
    """
    Parallel execution settings.
    """

    max_workers: int = get_env_int(
        "MAX_WORKERS",
        8,
    )

    batch_size: int = get_env_int(
        "BATCH_SIZE",
        50,
    )


###############################################################################
# HTTP Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class HttpSettings:
    """
    HTTP networking configuration.
    """

    timeout_seconds: int = get_env_int(
        "HTTP_TIMEOUT",
        30,
    )

    retry_count: int = get_env_int(
        "HTTP_RETRY_COUNT",
        3,
    )

    retry_delay_seconds: int = get_env_int(
        "HTTP_RETRY_DELAY",
        2,
    )

    user_agent: str = get_env(
        "USER_AGENT",
        "NEWS_REPORT/1.0",
    )


###############################################################################
# Market Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class MarketSettings:
    """
    Market data configuration.
    """

    exchange: str = get_env(
        "MARKET_EXCHANGE",
        "NSE",
    )

    yahoo_suffix: str = get_env(
        "YAHOO_SUFFIX",
        ".NS",
    )

    top_gainers: int = get_env_int(
        "TOP_GAINERS",
        20,
    )

    top_losers: int = get_env_int(
        "TOP_LOSERS",
        20,
    )


###############################################################################
# News Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class NewsSettings:
    """
    News collection configuration.
    """

    lookback_days: int = get_env_int(
        "NEWS_LOOKBACK_DAYS",
        7,
    )

    articles_per_stock: int = get_env_int(
        "NEWS_PER_STOCK",
        5,
    )

    enable_google_news: bool = get_env_bool(
        "ENABLE_GOOGLE_NEWS",
        True,
    )

    enable_news_api: bool = get_env_bool(
        "ENABLE_NEWS_API",
        True,
    )

    enable_marketaux: bool = get_env_bool(
        "ENABLE_MARKETAUX",
        True,
    )

    enable_finnhub: bool = get_env_bool(
        "ENABLE_FINNHUB",
        True,
    )


###############################################################################
# AI Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class AISettings:
    """
    AI summarization configuration.
    """

    enabled: bool = get_env_bool(
        "ENABLE_AI_SUMMARY",
        True,
    )

    provider: str = get_env(
        "AI_PROVIDER",
        "gemini",
    )

    model: str = get_env(
        "AI_MODEL",
        "gemini-2.5-pro",
    )

    max_tokens: int = get_env_int(
        "AI_MAX_TOKENS",
        1024,
    )

    temperature: float = get_env_float(
        "AI_TEMPERATURE",
        0.20,
    )


###############################################################################
# Report Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class ReportSettings:
    """
    Excel report generation settings.
    """

    auto_adjust_columns: bool = get_env_bool(
        "AUTO_ADJUST_COLUMNS",
        True,
    )

    freeze_header: bool = get_env_bool(
        "FREEZE_HEADER",
        True,
    )

    include_ai_summary: bool = get_env_bool(
        "INCLUDE_AI_SUMMARIES",
        True,
    )

    overwrite_existing: bool = get_env_bool(
        "OVERWRITE_REPORT",
        True,
    )

###############################################################################
# Logging Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class LoggingSettings:
    """
    Logging configuration.
    """

    level: str = get_env(
        "LOG_LEVEL",
        "INFO",
    ).upper()

    console_enabled: bool = get_env_bool(
        "LOG_CONSOLE",
        True,
    )

    file_enabled: bool = get_env_bool(
        "LOG_FILE",
        True,
    )

    rotate_logs: bool = get_env_bool(
        "LOG_ROTATE",
        True,
    )

    max_file_size_mb: int = get_env_int(
        "LOG_MAX_SIZE_MB",
        10,
    )

    backup_count: int = get_env_int(
        "LOG_BACKUP_COUNT",
        10,
    )


###############################################################################
# Application Settings
###############################################################################


@dataclass(slots=True, frozen=True)
class ApplicationSettings:
    """
    Root application configuration.

    Every subsystem should access configuration through this object.
    """

    base: BaseSettings = BaseSettings()

    api: ApiSettings = ApiSettings()

    http: HttpSettings = HttpSettings()

    thread_pool: ThreadPoolSettings = ThreadPoolSettings()

    market: MarketSettings = MarketSettings()

    news: NewsSettings = NewsSettings()

    ai: AISettings = AISettings()

    report: ReportSettings = ReportSettings()

    logging: LoggingSettings = LoggingSettings()


###############################################################################
# Validation
###############################################################################


def validate_configuration(
    settings: ApplicationSettings,
) -> None:
    """
    Validate runtime configuration.

    Raises
    ------
    RuntimeError
        If configuration is invalid.
    """

    if settings.thread_pool.max_workers < 1:

        raise RuntimeError(
            "MAX_WORKERS must be greater than zero."
        )

    if settings.thread_pool.batch_size < 1:

        raise RuntimeError(
            "BATCH_SIZE must be greater than zero."
        )

    if settings.market.top_gainers < 1:

        raise RuntimeError(
            "TOP_GAINERS must be greater than zero."
        )

    if settings.market.top_losers < 1:

        raise RuntimeError(
            "TOP_LOSERS must be greater than zero."
        )

    if settings.news.lookback_days < 1:

        raise RuntimeError(
            "NEWS_LOOKBACK_DAYS must be greater than zero."
        )

    if settings.news.articles_per_stock < 1:

        raise RuntimeError(
            "NEWS_PER_STOCK must be greater than zero."
        )

    if settings.http.timeout_seconds <= 0:

        raise RuntimeError(
            "HTTP_TIMEOUT must be greater than zero."
        )

    if settings.http.retry_count < 0:

        raise RuntimeError(
            "HTTP_RETRY_COUNT cannot be negative."
        )

    if settings.ai.temperature < 0.0:

        raise RuntimeError(
            "AI_TEMPERATURE cannot be negative."
        )

    if settings.ai.temperature > 2.0:

        raise RuntimeError(
            "AI_TEMPERATURE cannot exceed 2.0."
        )


###############################################################################
# Initialization
###############################################################################


def initialize_application() -> ApplicationSettings:
    """
    Initialize application configuration.

    Creates runtime directories and validates all settings.
    """

    initialize_directories()

    application_settings = ApplicationSettings()

    validate_configuration(
        application_settings,
    )

    return application_settings


###############################################################################
# Singleton
###############################################################################

settings = initialize_application()