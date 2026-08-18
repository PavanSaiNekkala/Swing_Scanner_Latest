"""
===============================================================================
File: loader.py

Description:
    Loads, validates and normalizes the NSE Universe CSV.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import INPUT_CSV
from modules.constants import CSVColumns
from modules.logger import logger
from modules.utils import normalize_symbols
from modules.validators import (
    validate_file_exists,
    validate_universe_csv,
)


class UniverseLoader:
    """
    Responsible for loading the NSE Universe CSV.
    """

    def __init__(self, csv_path: Path = INPUT_CSV):

        self.csv_path = Path(csv_path)

    def load(self) -> list[str]:
        """
        Load and return normalized ticker symbols.

        Returns
        -------
        list[str]
        """

        logger.info("Loading universe: %s", self.csv_path)

        validate_file_exists(self.csv_path)

        try:
            df = pd.read_csv(self.csv_path)

        except Exception as exc:
            logger.exception("Unable to read CSV.")
            raise

        validate_universe_csv(df)

        symbols = (
            df[CSVColumns.SYMBOL.value]
            .dropna()
            .astype(str)
            .tolist()
        )

        symbols = normalize_symbols(symbols)

        # Remove duplicates while preserving order
        symbols = list(dict.fromkeys(symbols))

        logger.info(
            "Loaded %d symbols.",
            len(symbols),
        )

        return symbols


def load_universe() -> list[str]:
    """
    Convenience wrapper.
    """

    return UniverseLoader().load()


if __name__ == "__main__":

    symbols = load_universe()

    print(f"Loaded {len(symbols)} symbols")

    print(symbols[:20])