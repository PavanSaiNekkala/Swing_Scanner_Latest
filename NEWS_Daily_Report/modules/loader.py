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
from modules.logger import logger
from modules.validators import (
    validate_file_exists,
    validate_universe_csv,
)

###############################################################################
# Loader
###############################################################################


class UniverseLoader:
    """
    Responsible for loading and normalizing the NSE Universe.
    """

    def __init__(
        self,
        csv_path: Path = INPUT_CSV,
    ):

        self.csv_path = Path(
            csv_path,
        )

    ###########################################################################

    def load(
        self,
    ) -> pd.DataFrame:
        """
        Load and normalize the NSE universe.

        Returns
        -------
        pd.DataFrame

        Columns
        -------
        Symbol
        Company
        """

        logger.info(
            "Loading universe: %s",
            self.csv_path,
        )

        validate_file_exists(
            self.csv_path,
        )

        try:

            df = pd.read_csv(
                self.csv_path,
            )

        except Exception:

            logger.exception(
                "Unable to read universe CSV.",
            )

            raise

        #
        # Normalize column names
        #

        df.columns = (
            df.columns
            .str.strip()
        )

        df.rename(
            columns={
                "SYMBOL": "Symbol",
                "NAME OF COMPANY": "Company",
            },
            inplace=True,
        )

        #
        # Validate
        #

        validate_universe_csv(
            df,
        )

        #
        # Keep only required columns
        #

        df = df[
            [
                "Symbol",
                "Company",
            ]
        ].copy()

        #
        # Normalize Symbol
        #

        df["Symbol"] = (
            df["Symbol"]
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df["Symbol"] = df["Symbol"].apply(
            lambda symbol:
            symbol
            if symbol.endswith(".NS")
            else f"{symbol}.NS"
        )

        #
        # Normalize Company
        #

        df["Company"] = (
            df["Company"]
            .astype(str)
            .str.strip()
        )

        #
        # Remove empty rows
        #

        df = df.dropna(
            subset=[
                "Symbol",
                "Company",
            ]
        )

        #
        # Remove duplicate symbols
        #

        df = df.drop_duplicates(
            subset="Symbol",
            keep="first",
        ).reset_index(
            drop=True,
        )

        logger.info(
            "Loaded %d symbols.",
            len(df),
        )

        return df


###############################################################################
# Public API
###############################################################################


def load_universe() -> pd.DataFrame:

    return UniverseLoader().load()


###############################################################################
# Debug
###############################################################################

if __name__ == "__main__":

    universe = load_universe()

    print(universe.head())

    print()

    print(
        f"Loaded {len(universe)} symbols."
    )