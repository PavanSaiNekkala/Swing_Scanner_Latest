"""
==============================================================================
File        : data/symbols.py
Project     : NSE Market Report

Description
-----------
Utility functions for working with NSE stock symbols.

Responsibilities
----------------
✓ Normalize symbols
✓ Validate symbols
✓ Remove duplicates
✓ Sort symbols
✓ Convert between DataFrame and List
✓ Read/Write symbol files

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pandas as pd

from config.logging_config import logger

###############################################################################
# EXCEPTIONS
###############################################################################


class SymbolError(Exception):
    """Base symbol exception."""


###############################################################################
# SYMBOL MANAGER
###############################################################################


class SymbolManager:
    """
    Utility class for managing NSE symbols.
    """

    REQUIRED_COLUMN = "Symbol"

    ###########################################################################
    # NORMALIZATION
    ###########################################################################

    @staticmethod
    def normalize(symbol: str) -> str:
        """
        Normalize a symbol.

        Example
        -------
        " reliance " -> "RELIANCE"
        """

        if symbol is None:
            raise SymbolError("Symbol cannot be None.")

        symbol = str(symbol).strip().upper()

        if not symbol:
            raise SymbolError("Empty symbol.")

        return symbol

    ###########################################################################
    # VALIDATION
    ###########################################################################

    @classmethod
    def validate(cls, symbol: str) -> bool:
        """
        Validate a symbol.
        """

        try:

            symbol = cls.normalize(symbol)

        except SymbolError:

            return False

        return symbol.isalnum()

    ###########################################################################
    # LIST OPERATIONS
    ###########################################################################

    @classmethod
    def unique(
        cls,
        symbols: Iterable[str],
    ) -> List[str]:
        """
        Normalize and remove duplicates while preserving order.
        """

        seen = set()
        output = []

        for symbol in symbols:

            try:

                symbol = cls.normalize(symbol)

            except SymbolError:

                continue

            if symbol not in seen:

                seen.add(symbol)

                output.append(symbol)

        return output

    ###########################################################################

    @classmethod
    def sort(
        cls,
        symbols: Iterable[str],
    ) -> List[str]:
        """
        Return sorted symbol list.
        """

        return sorted(cls.unique(symbols))

    ###########################################################################
    # DATAFRAME HELPERS
    ###########################################################################

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        column: str = REQUIRED_COLUMN,
    ) -> List[str]:
        """
        Extract symbol list from DataFrame.
        """

        if column not in df.columns:

            raise SymbolError(
                f"Column '{column}' not found."
            )

        return cls.unique(df[column].tolist())

    ###########################################################################

    @classmethod
    def to_dataframe(
        cls,
        symbols: Iterable[str],
    ) -> pd.DataFrame:
        """
        Convert symbol list to DataFrame.
        """

        return pd.DataFrame(

            {

                cls.REQUIRED_COLUMN:

                    cls.unique(symbols)

            }

        )

    ###########################################################################
    # FILE IO
    ###########################################################################

    @classmethod
    def read_csv(
        cls,
        path: str | Path,
    ) -> List[str]:
        """
        Read symbols from CSV.
        """

        df = pd.read_csv(path)

        return cls.from_dataframe(df)

    ###########################################################################

    @classmethod
    def write_csv(
        cls,
        symbols: Iterable[str],
        path: str | Path,
    ) -> None:
        """
        Save symbols to CSV.
        """

        df = cls.to_dataframe(symbols)

        df.to_csv(path, index=False)

        logger.info("Saved symbols -> %s", path)

    ###########################################################################
    # REPORT HELPERS
    ###########################################################################

    @classmethod
    def merge_unique(
        cls,
        *symbol_lists: Iterable[str],
    ) -> List[str]:
        """
        Merge multiple symbol collections.
        """

        merged = []

        for items in symbol_lists:

            merged.extend(items)

        return cls.unique(merged)


###############################################################################
# TESTING
###############################################################################

if __name__ == "__main__":

    symbols = [

        " reliance ",

        "INFY",

        "tcs",

        "RELIANCE",

        "SBIN",

        "sbin",

    ]

    manager = SymbolManager()

    print("Original")

    print(symbols)

    print("\nNormalized")

    print(manager.unique(symbols))

    print("\nSorted")

    print(manager.sort(symbols))

    df = manager.to_dataframe(symbols)

    print("\nDataFrame")

    print(df)