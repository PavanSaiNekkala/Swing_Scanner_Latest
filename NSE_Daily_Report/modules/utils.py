"""
===============================================================================
File: utils.py

Description:
    Common utility/helper functions used across the application.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from modules.constants import DATE_FORMAT, DATETIME_FORMAT, YFINANCE_SUFFIX


# =============================================================================
# Date Helpers
# =============================================================================

def today() -> datetime:
    """Return current local datetime."""
    return datetime.now()


def today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    return today().strftime(DATE_FORMAT)


def current_timestamp() -> str:
    """Return timestamp string."""
    return today().strftime(DATETIME_FORMAT)


def days_ago(days: int) -> datetime:
    """Return datetime N days ago."""
    return today() - timedelta(days=days)


# =============================================================================
# Symbol Helpers
# =============================================================================

def normalize_symbol(symbol: str) -> str:
    """
    Convert symbol to Yahoo Finance format.

    Example
    -------
    RELIANCE -> RELIANCE.NS
    infy -> INFY.NS
    """

    symbol = str(symbol).strip().upper()

    if not symbol:
        return ""

    if symbol.endswith(YFINANCE_SUFFIX):
        return symbol

    return f"{symbol}{YFINANCE_SUFFIX}"


def normalize_symbols(symbols: Iterable[str]) -> list[str]:
    """Normalize a collection of symbols."""

    return [
        normalize_symbol(symbol)
        for symbol in symbols
        if str(symbol).strip()
    ]


# =============================================================================
# Numeric Helpers
# =============================================================================

def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to integer."""

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def percentage_change(previous: float, current: float) -> float:
    """
    Calculate percentage change.

    Formula
    -------
    ((Current - Previous) / Previous) * 100
    """

    previous = safe_float(previous)
    current = safe_float(current)

    if previous == 0:
        return 0.0

    return round(((current - previous) / previous) * 100, 2)


# =============================================================================
# DataFrame Helpers
# =============================================================================

def is_dataframe_empty(df: pd.DataFrame | None) -> bool:
    """Return True if DataFrame is None or empty."""

    return df is None or df.empty


def remove_duplicate_symbols(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Remove duplicate symbols."""

    return (
        df.drop_duplicates(subset=[column])
        .reset_index(drop=True)
    )


# =============================================================================
# File Helpers
# =============================================================================

def ensure_directory(path: Path | str) -> Path:
    """
    Create directory if it doesn't exist.
    """

    path = Path(path)

    path.mkdir(parents=True, exist_ok=True)

    return path


# =============================================================================
# String Helpers
# =============================================================================

def clean_text(text: Any) -> str:
    """Normalize whitespace."""

    if text is None:
        return ""

    return " ".join(str(text).split())


def truncate_text(text: str, length: int = 120) -> str:
    """Truncate text to desired length."""

    text = clean_text(text)

    if len(text) <= length:
        return text

    return text[: length - 3] + "..."


# =============================================================================
# Miscellaneous
# =============================================================================

def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
    """
    Split list into chunks.

    Example
    -------
    [1,2,3,4,5]

    chunk_size=2

    [[1,2],[3,4],[5]]
    """

    return [
        items[i : i + chunk_size]
        for i in range(0, len(items), chunk_size)
    ]