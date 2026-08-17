"""
Market universe loader.

Responsibilities
----------------
- Load NSE universe CSV
- Validate required columns
- Normalize stock metadata
- Return StockIdentity domain models

This module performs no market calculations.

Author
------
Pavan Sai Nekkala

Project
-------
NEWS_REPORT

Python
------
3.12+
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.constants import (
    NSE_UNIVERSE_FILE,
)
from config.logging_config import (
    get_logger,
)

from market.models import (
    StockIdentity,
)

logger = get_logger(__name__)


###############################################################################
# Market Universe Loader
###############################################################################

class UniverseLoader:
    """
    Loads the NSE stock universe from CSV.
    """

    REQUIRED_COLUMNS = (
        "ticker",
        "company_name",
        "sector",
        "category",
    )

    def __init__(
        self,
        csv_file: Path = NSE_UNIVERSE_FILE,
    ) -> None:

        self.csv_file = csv_file

    ###########################################################################
    # Validation
    ###########################################################################

    def validate(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Validate the input universe.
        """

        missing = [

            column

            for column in self.REQUIRED_COLUMNS

            if column not in dataframe.columns

        ]

        if missing:

            raise RuntimeError(
                "Missing required columns: "
                f"{', '.join(missing)}"
            )

    ###########################################################################
    # Normalization
    ###########################################################################

    def normalize(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize the dataframe.
        """

        dataframe = dataframe.copy()

        dataframe.columns = [

            column.strip().lower()

            for column in dataframe.columns

        ]

        dataframe["ticker"] = (

            dataframe["ticker"]

            .astype(str)

            .str.strip()

            .str.upper()

        )

        dataframe["company_name"] = (

            dataframe["company_name"]

            .astype(str)

            .str.strip()

        )

        dataframe["sector"] = (

            dataframe["sector"]

            .astype(str)

            .str.strip()

        )

        dataframe["category"] = (

            dataframe["category"]

            .astype(str)

            .str.strip()

        )

        dataframe = dataframe.drop_duplicates(
            subset="ticker",
        )

        dataframe = dataframe.dropna(
            subset=[
                "ticker",
                "company_name",
            ],
        )

        dataframe = dataframe.reset_index(
            drop=True,
        )

        return dataframe

    ###########################################################################
    # Convert to Domain Objects
    ###########################################################################

    def build_models(
        self,
        dataframe: pd.DataFrame,
    ) -> list[StockIdentity]:
        """
        Convert dataframe into StockIdentity models.
        """

        universe: list[
            StockIdentity
        ] = []

        for row in dataframe.itertuples():

            universe.append(

                StockIdentity(

                    ticker=row.ticker,

                    company_name=row.company_name,

                    sector=row.sector,

                    category=row.category,

                )

            )

        return universe

    ###########################################################################
    # Load
    ###########################################################################

    def load(
        self,
    ) -> list[StockIdentity]:
        """
        Load and validate the NSE universe.
        """

        logger.info(
            "Loading NSE universe | File=%s",
            self.csv_file,
        )

        if not self.csv_file.exists():

            raise FileNotFoundError(
                self.csv_file
            )

        dataframe = pd.read_csv(
            self.csv_file,
        )

        self.validate(
            dataframe,
        )

        dataframe = self.normalize(
            dataframe,
        )

        universe = self.build_models(
            dataframe,
        )

        logger.info(
            "Loaded %d stocks.",
            len(universe),
        )

        return universe


###############################################################################
# Factory
###############################################################################


def build_universe_loader(
    csv_file: Path = NSE_UNIVERSE_FILE,
) -> UniverseLoader:
    """
    Factory for UniverseLoader.

    Parameters
    ----------
    csv_file:
        Path to the NSE universe CSV.

    Returns
    -------
    MarketUniverseLoader
    """

    loader = UniverseLoader(
        csv_file=csv_file,
    )

    logger.info(
        "UniverseLoader created."
    )

    return loader