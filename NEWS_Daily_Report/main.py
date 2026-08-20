"""
===============================================================================
File: main.py

Description:
    NEWS Daily Report Generator

Pipeline
--------
1. Load NSE Universe
2. Download Market Data
3. Calculate Returns
4. Rank Stocks
5. Fetch News
6. Generate Excel Report

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

import sys
import time
from typing import Callable, Any

from modules.logger import logger

from modules.loader import load_universe
from modules.market_data import fetch_market_data
from modules.returns import calculate_returns
from modules.ranking import rank_stocks
from modules.news import enrich_news
from modules.excel_writer import create_excel_report


###############################################################################
# Application
###############################################################################


class DailyReportApplication:

    def __init__(self):

        self.start_time = time.perf_counter()

    ###########################################################################

    @staticmethod
    def execute_step(
        step_name: str,
        func: Callable[..., Any],
        *args,
        **kwargs,
    ):
        """
        Execute one pipeline step and measure execution time.
        """

        logger.info("=" * 80)
        logger.info("START : %s", step_name)

        start = time.perf_counter()

        result = func(*args, **kwargs)

        elapsed = time.perf_counter() - start

        logger.info(
            "END   : %s (%.2f sec)",
            step_name,
            elapsed,
        )

        logger.info("=" * 80)

        return result

    ###########################################################################

    def run(self):

        logger.info("=" * 80)
        logger.info("NEWS DAILY REPORT STARTED")
        logger.info("=" * 80)

        try:

            # -----------------------------------------------------------------
            # Load Universe
            # -----------------------------------------------------------------

            universe = self.execute_step(
                "Load NSE Universe",
                load_universe,
            )

            logger.info(
                "Universe Loaded : %d symbols",
                len(universe),
            )

            # -----------------------------------------------------------------
            # Market Data
            # -----------------------------------------------------------------

            market_df = self.execute_step(
                "Download Market Data",
                fetch_market_data,
                universe,
            )

            logger.info(
                "Market Data Rows : %d",
                len(market_df),
            )

            # -----------------------------------------------------------------
            # Returns
            # -----------------------------------------------------------------

            market_df = self.execute_step(
                "Calculate Returns",
                calculate_returns,
                market_df,
            )

            # -----------------------------------------------------------------
            # Ranking
            # -----------------------------------------------------------------

            ranking = self.execute_step(
                "Rank Stocks",
                rank_stocks,
                market_df,
            )

            gainers = ranking.gainers
            losers = ranking.losers

            logger.info("Top Gainers : %d", len(gainers))
            logger.info("Top Losers  : %d", len(losers))

            # -----------------------------------------------------------------
            # News
            # -----------------------------------------------------------------

            gainers = self.execute_step(
                "Fetch News - Gainers",
                enrich_news,
                gainers,
            )

            logger.info(
                "Gainers after news enrichment:\n%s",
                gainers[
                    [
                        "Symbol",
                        "Top Headline",
                    ]
                ].head().to_string(),
            )

            losers = self.execute_step(
                "Fetch News - Losers",
                enrich_news,
                losers,
            )

            logger.info(
                "Losers after news enrichment:\n%s",
                losers[
                    [
                        "Symbol",
                        "Top Headline",
                    ]
                ].head().to_string(),
            )

            # -----------------------------------------------------------------
            # Excel
            # -----------------------------------------------------------------

            self.execute_step(
                "Generate Excel Report",
                create_excel_report,
                gainers,
                losers,
            )

            # -----------------------------------------------------------------
            # Summary
            # -----------------------------------------------------------------

            total = time.perf_counter() - self.start_time

            logger.info("=" * 80)
            logger.info("PIPELINE COMPLETED")
            logger.info("=" * 80)

            logger.info("Universe Size  : %d", len(universe))
            logger.info("Rows Processed    : %d", len(market_df))
            logger.info("Top Gainers       : %d", len(gainers))
            logger.info("Top Losers        : %d", len(losers))
            logger.info("Total Runtime     : %.2f sec", total)

            logger.info("=" * 80)

        except Exception as exc:

            logger.exception(
                "Application failed: %s",
                exc,
            )

            sys.exit(1)


###############################################################################
# Entry Point
###############################################################################


def main():

    DailyReportApplication().run()


if __name__ == "__main__":

    main()