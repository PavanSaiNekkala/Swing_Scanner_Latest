"""
===============================================================================
File: main.py

Description:
    NSE Daily Report Generator

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

from modules.logger import logger

from modules.loader import load_universe
from modules.market_data import fetch_market_data
from modules.returns import calculate_returns
from modules.ranking import rank_stocks
from modules.news import enrich_news
from modules.excel_writer import create_excel_report


###############################################################################
# Main Application
###############################################################################


class DailyReportApplication:
    """
    Main application class.
    """

    def __init__(self):

        self.start_time = time.perf_counter()

    ###########################################################################

    def run(self):

        logger.info("=" * 80)
        logger.info("NSE DAILY REPORT STARTED")
        logger.info("=" * 80)

        try:

            # -----------------------------------------------------------------
            # Load Universe
            # -----------------------------------------------------------------

            logger.info("Loading NSE Universe...")

            symbols = load_universe()

            logger.info(
                "Loaded %d symbols.",
                len(symbols),
            )

            # -----------------------------------------------------------------
            # Download Market Data
            # -----------------------------------------------------------------

            logger.info("Downloading Market Data...")

            market_df = fetch_market_data(symbols)

            # -----------------------------------------------------------------
            # Calculate Returns
            # -----------------------------------------------------------------

            logger.info("Calculating Returns...")

            market_df = calculate_returns(market_df)

            # -----------------------------------------------------------------
            # Ranking
            # -----------------------------------------------------------------

            logger.info("Creating Rankings...")

            ranking = rank_stocks(market_df)

            gainers = ranking.gainers

            losers = ranking.losers

            # -----------------------------------------------------------------
            # Fetch News
            # -----------------------------------------------------------------

            logger.info("Fetching News for Gainers...")

            gainers = enrich_news(gainers)

            logger.info("Fetching News for Losers...")

            losers = enrich_news(losers)

            # -----------------------------------------------------------------
            # Excel
            # -----------------------------------------------------------------

            logger.info("Generating Excel Report...")

            create_excel_report(
                gainers=gainers,
                losers=losers,
            )

            elapsed = time.perf_counter() - self.start_time

            logger.info(
                "Completed successfully in %.2f seconds.",
                elapsed,
            )

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

    app = DailyReportApplication()

    app.run()


if __name__ == "__main__":

    main()