"""
Market ranking engine.

Responsibilities
----------------
- Rank market stocks
- Identify top gainers
- Identify top losers
- Produce MarketRanking domain models

This module performs no market data retrieval.

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

from operator import attrgetter

from config.logging_config import get_logger
from config.settings import settings

from market.models import (
    MarketRanking,
    MarketStock,
)

logger = get_logger(__name__)

###############################################################################
# Ranking Engine
###############################################################################


class MarketRankingEngine:
    """
    Ranks market stocks based on one-day return.

    Produces the Top Gainers and Top Losers
    required by the reporting pipeline.
    """

    def __init__(
        self,
        top_count: int | None = None,
    ) -> None:

        self.top_count = (
            top_count
            or settings.market.top_gainers
        )

        logger.info(
            "MarketRankingEngine initialized "
            "(top_count=%d).",
            self.top_count,
        )

###############################################################################
# Internal Sorting
###############################################################################

    @staticmethod
    def sort_descending(
        stocks: list[MarketStock],
    ) -> list[MarketStock]:
        """
        Highest return first.
        """

        return sorted(
            stocks,
            key=attrgetter(
                "snapshot.day_return_percent",
            ),
            reverse=True,
        )

    @staticmethod
    def sort_ascending(
        stocks: list[MarketStock],
    ) -> list[MarketStock]:
        """
        Lowest return first.
        """

        return sorted(
            stocks,
            key=attrgetter(
                "snapshot.day_return_percent",
            ),
        )

###############################################################################
# Top Gainers
###############################################################################

    def top_gainers(
        self,
        stocks: list[MarketStock],
    ) -> MarketRanking:
        """
        Return the highest performing stocks.
        """

        ranking = MarketRanking(
            title="Top Gainers",
        )

        ordered = self.sort_descending(
            stocks,
        )

        ranking.extend(
            ordered[
                : self.top_count
            ],
        )

        logger.info(
            "Selected %d top gainers.",
            ranking.count,
        )

        return ranking

###############################################################################
# Top Losers
###############################################################################

    def top_losers(
        self,
        stocks: list[MarketStock],
    ) -> MarketRanking:
        """
        Return the lowest performing stocks.
        """

        ranking = MarketRanking(
            title="Top Losers",
        )

        ordered = self.sort_ascending(
            stocks,
        )

        ranking.stocks.extend(
            ordered[
                : self.top_count
            ],
        )

        logger.info(
            "Selected %d top losers.",
            ranking.count,
        )

        return ranking

###############################################################################
# Ranking
###############################################################################

    def rank(
        self,
        stocks: list[MarketStock],
    ) -> tuple[
        MarketRanking,
        MarketRanking,
    ]:
        """
        Rank all stocks.

        Returns
        -------
        tuple[MarketRanking, MarketRanking]
            Top gainers and top losers.
        """

        logger.info(
            "Ranking %d stocks...",
            len(stocks),
        )

        gainers = self.top_gainers(
            stocks,
        )

        losers = self.top_losers(
            stocks,
        )

        logger.info(
            "Ranking completed."
        )

        return (
            gainers,
            losers,
        )


###############################################################################
# Factory
###############################################################################


def build_market_ranking_engine(
    top_count: int | None = None,
) -> MarketRankingEngine:
    """
    Factory for MarketRankingEngine.
    """

    engine = MarketRankingEngine(
        top_count=top_count,
    )

    logger.info(
        "MarketRankingEngine created."
    )

    return engine