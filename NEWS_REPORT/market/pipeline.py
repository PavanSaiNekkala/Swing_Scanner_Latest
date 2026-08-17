"""
Market pipeline.

Responsibilities
----------------
- Load NSE universe
- Fetch latest market data
- Rank gainers and losers
- Produce MarketReport

This module orchestrates the market workflow.

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

import time

from config.logging_config import get_logger

from data.providers.yfinance_provider import (
    MarketDataProvider,
)

from market.loader import (
    UniverseLoader,
)

from market.ranking import (
    MarketRankingEngine,
)

from market.models import (
    MarketReport,
    MarketStock,
)

logger = get_logger(__name__)

###############################################################################
# Market Pipeline
###############################################################################


class MarketPipeline:
    """
    Executes the complete market workflow.
    """

    def __init__(
        self,
        loader: UniverseLoader,
        provider: MarketDataProvider,
        ranking_engine: MarketRankingEngine,
    ) -> None:

        self.loader = loader

        self.provider = provider

        self.ranking_engine = ranking_engine

        logger.info(
            "MarketPipeline initialized."
        )

###############################################################################
# Universe Loading
###############################################################################

    def load_universe(
        self,
    ):
        """
        Load NSE universe.
        """

        logger.info(
            "Loading NSE universe..."
        )

        universe = self.loader.load()

        logger.info(
            "Loaded %d stocks.",
            len(universe),
        )

        return universe

###############################################################################
# Market Data
###############################################################################

    def fetch_market_data(
        self,
        universe,
    ) -> list[MarketStock]:
        """
        Fetch market data for all stocks.
        """

        logger.info(
            "Downloading market data..."
        )

        stocks = self.provider.fetch_many(
            universe,
        )

        logger.info(
            "Downloaded market data for %d stocks.",
            len(stocks),
        )

        return stocks

###############################################################################
# Ranking
###############################################################################

    def rank_market(
        self,
        stocks: list[MarketStock],
    ):
        """
        Rank stocks into top gainers and top losers.
        """

        logger.info(
            "Ranking market..."
        )

        gainers, losers = (
            self.ranking_engine.rank(
                stocks,
            )
        )

        logger.info(
            "Ranking completed."
        )

        return (
            gainers,
            losers,
        )

###############################################################################
# Report Builder
###############################################################################

    @staticmethod
    def build_report(
        gainers,
        losers,
        universe_size: int,
        execution_time: float,
    ) -> MarketReport:
        """
        Build the final MarketReport.
        """

        return MarketReport(
            top_gainers=gainers,
            top_losers=losers,
            universe_size=universe_size,
            execution_time_seconds=round(
                execution_time,
                2,
            ),
        )

###############################################################################
# Pipeline Execution
###############################################################################

    def execute(
        self,
    ) -> MarketReport:
        """
        Execute the complete market pipeline.
        """

        logger.info(
            "=" * 80,
        )

        logger.info(
            "Starting Market Pipeline"
        )

        logger.info(
            "=" * 80,
        )

        start = time.perf_counter()

        #######################################################################
        # Load Universe
        #######################################################################

        universe = self.load_universe()

        #######################################################################
        # Fetch Market Data
        #######################################################################

        stocks = self.fetch_market_data(
            universe,
        )

        #######################################################################
        # Rank Stocks
        #######################################################################

        gainers, losers = self.rank_market(
            stocks,
        )

        #######################################################################
        # Build Report
        #######################################################################

        report = self.build_report(
            gainers=gainers,
            losers=losers,
            universe_size=len(
                universe,
            ),
            execution_time=(
                time.perf_counter()
                - start
            ),
        )

        logger.info(
            "Market Pipeline completed in %.2f seconds.",
            report.execution_time_seconds,
        )

        return report


###############################################################################
# Factory
###############################################################################

def build_market_pipeline(
    loader: UniverseLoader,
    provider: MarketDataProvider,
    ranking_engine: MarketRankingEngine,
) -> MarketPipeline:
    """
    Factory for MarketPipeline.
    """

    pipeline = MarketPipeline(
        loader=loader,
        provider=provider,
        ranking_engine=ranking_engine,
    )

    logger.info(
        "MarketPipeline created."
    )

    return pipeline