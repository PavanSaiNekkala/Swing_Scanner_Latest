"""
===============================================================================
File: validators.py

Description:
    Validation helpers for files, symbols, DataFrames and numeric values.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from modules.constants import CSVColumns
from modules.exceptions import (
    EmptyDataFrameError,
    InvalidCSVError,
    InvalidSymbolError,
    MissingColumnError,
)


# =============================================================================
# File Validation
# =============================================================================


def validate_file_exists(path: Path | str) -> None:
    """
    Validate that a file exists.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")


# =============================================================================
# DataFrame Validation
# =============================================================================


def validate_dataframe(df: pd.DataFrame) -> None:
    """
    Validate DataFrame is not empty.
    """

    if df is None:
        raise EmptyDataFrameError("DataFrame is None.")

    if df.empty:
        raise EmptyDataFrameError("DataFrame is empty.")


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: Iterable[str],
) -> None:
    """
    Validate required DataFrame columns.
    """

    validate_dataframe(df)

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:
        raise MissingColumnError(
            f"Missing required columns: {', '.join(missing)}"
        )


# =============================================================================
# CSV Validation
# =============================================================================


def validate_universe_csv(df: pd.DataFrame) -> None:
    """
    Validate NSE Universe CSV.
    """

    validate_required_columns(
        df,
        [CSVColumns.SYMBOL.value],
    )


# =============================================================================
# Symbol Validation
# =============================================================================


def validate_symbol(symbol: str) -> None:
    """
    Validate NSE symbol.
    """

    if not isinstance(symbol, str):
        raise InvalidSymbolError("Ticker must be a string.")

    symbol = symbol.strip()

    if not symbol:
        raise InvalidSymbolError("Ticker cannot be empty.")

    if " " in symbol:
        raise InvalidSymbolError(
            f"Invalid ticker: {symbol}"
        )


def validate_symbols(symbols: Iterable[str]) -> None:
    """
    Validate multiple symbols.
    """

    for symbol in symbols:
        validate_symbol(symbol)


# =============================================================================
# Numeric Validation
# =============================================================================


def validate_numeric(value, field_name: str) -> None:
    """
    Ensure value is numeric.
    """

    try:
        float(value)
    except (TypeError, ValueError):
        raise InvalidCSVError(
            f"{field_name} must be numeric."
        )


# =============================================================================
# Price Validation
# =============================================================================


def validate_price(price, field_name: str = "Price") -> None:
    """
    Ensure price is non-negative.
    """

    validate_numeric(price, field_name)

    if float(price) < 0:
        raise InvalidCSVError(
            f"{field_name} cannot be negative."
        )


# =============================================================================
# Volume Validation
# =============================================================================


def validate_volume(volume) -> None:
    """
    Ensure volume is valid.
    """

    validate_numeric(volume, "Volume")

    if float(volume) < 0:
        raise InvalidCSVError(
            "Volume cannot be negative."
        )


# =============================================================================
# Generic Helper
# =============================================================================


def validate_not_none(value, field_name: str) -> None:
    """
    Ensure a value is not None.
    """

    if value is None:
        raise ValueError(f"{field_name} cannot be None.")