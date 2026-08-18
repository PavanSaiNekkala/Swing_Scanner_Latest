"""
===============================================================================
File: returns.py

Description:
    Calculates daily percentage returns for NSE stocks.

Formula
-------
Return % = ((Close - Previous Close) / Previous Close) * 100

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from modules.constants import MarketColumns
from modules.logger import logger
from modules.validators import (
    validate_dataframe,
    validate_required_columns,
)

###############################################################################
# Return Calculator
###############################################################################


class ReturnCalculator:
    """
    Calculates stock returns.
    """

    REQUIRED_COLUMNS = [
        MarketColumns.CLOSE.value,
        MarketColumns.PREVIOUS_CLOSE.value,
    ]

    def calculate(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Calculate one-day percentage returns.

        Parameters
        ----------
        df : DataFrame

        Returns
        -------
        DataFrame
        """

        validate_dataframe(df)

        validate_required_columns(
            df,
            self.REQUIRED_COLUMNS,
        )

        logger.info(
            "Calculating one-day returns."
        )

        result = df.copy()

        previous = result[
            MarketColumns.PREVIOUS_CLOSE.value
        ]

        current = result[
            MarketColumns.CLOSE.value
        ]

        result[MarketColumns.RETURN.value] = np.where(
            previous != 0,
            ((current - previous) / previous) * 100,
            0.0,
        )

        result[MarketColumns.RETURN.value] = (
            result[MarketColumns.RETURN.value]
            .round(2)
            .fillna(0.0)
        )

        logger.info(
            "Calculated returns for %d stocks.",
            len(result),
        )

        return result

    ###########################################################################

    def sort_descending(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Sort by Return % descending.
        """

        validate_dataframe(df)

        return (
            df.sort_values(
                by=MarketColumns.RETURN.value,
                ascending=False,
            )
            .reset_index(drop=True)
        )


###############################################################################
# Public API
###############################################################################


def calculate_returns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Public API.

    Example
    -------
    df = calculate_returns(df)
    """

    calculator = ReturnCalculator()

    return calculator.calculate(df)