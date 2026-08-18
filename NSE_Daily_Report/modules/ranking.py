"""
===============================================================================
File: ranking.py

Description:
    Creates Top Gainers and Top Losers rankings.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from modules.constants import (
    MarketColumns,
    TOP_GAINERS,
    TOP_LOSERS,
)

from modules.logger import logger

from modules.validators import (
    validate_dataframe,
    validate_required_columns,
)

###############################################################################
# Ranking Result
###############################################################################


@dataclass(slots=True)
class RankingResult:
    """
    Stores ranking results.
    """

    gainers: pd.DataFrame

    losers: pd.DataFrame


###############################################################################
# Ranking Service
###############################################################################


class RankingService:
    """
    Creates Top Gainers and Top Losers.
    """

    REQUIRED_COLUMNS = [
        MarketColumns.SYMBOL.value,
        MarketColumns.COMPANY.value,
        MarketColumns.RETURN.value,
    ]

    ###########################################################################

    def rank(
        self,
        df: pd.DataFrame,
    ) -> RankingResult:
        """
        Create Top Gainers and Top Losers.
        """

        validate_dataframe(df)

        validate_required_columns(
            df,
            self.REQUIRED_COLUMNS,
        )

        logger.info("Ranking stocks.")

        gainers = self.top_gainers(df)

        losers = self.top_losers(df)

        logger.info(
            "Top gainers: %d | Top losers: %d",
            len(gainers),
            len(losers),
        )

        return RankingResult(
            gainers=gainers,
            losers=losers,
        )

    ###########################################################################

    def top_gainers(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Return Top 20 Gainers.
        """

        gainers = (
            df.sort_values(
                by=MarketColumns.RETURN.value,
                ascending=False,
            )
            .head(TOP_GAINERS)
            .reset_index(drop=True)
        )

        gainers.insert(
            0,
            "Rank",
            range(1, len(gainers) + 1),
        )

        return gainers

    ###########################################################################

    def top_losers(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Return Top 20 Losers.
        """

        losers = (
            df.sort_values(
                by=MarketColumns.RETURN.value,
                ascending=True,
            )
            .head(TOP_LOSERS)
            .reset_index(drop=True)
        )

        losers.insert(
            0,
            "Rank",
            range(1, len(losers) + 1),
        )

        return losers


###############################################################################
# Public API
###############################################################################


def rank_stocks(
    df: pd.DataFrame,
) -> RankingResult:
    """
    Public API.

    Example
    -------
    result = rank_stocks(df)

    gainers = result.gainers

    losers = result.losers
    """

    service = RankingService()

    return service.rank(df)