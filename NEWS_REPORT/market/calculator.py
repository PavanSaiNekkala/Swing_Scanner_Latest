"""
Market calculation engine.

Responsibilities
----------------
- Calculate daily returns
- Calculate price change
- Validate market data
- Enrich MarketStock objects

No ranking or sorting is performed here.

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

from decimal import Decimal

from config.logging_config import get_logger

from market.models import (
    MarketStock,
)

logger = get_logger(__name__)


###############################################################################
# Market Calculator
###############################################################################


class MarketCalculator:
    """
    Performs market calculations.

    This class is completely stateless.
    """

    ###########################################################################
    # Validation
    ###########################################################################

    @staticmethod
    def validate_stock(
        stock: MarketStock,
    ) -> None:
        """
        Validate market snapshot.
        """

        snapshot = stock.snapshot

        if snapshot.previous_close <= 0:

            raise ValueError(
                f"{stock.identity.ticker}: "
                "Previous close must be positive."
            )

        if snapshot.current_price <= 0:

            raise ValueError(
                f"{stock.identity.ticker}: "
                "Current price must be positive."
            )

        if snapshot.volume < 0:

            raise ValueError(
                f"{stock.identity.ticker}: "
                "Volume cannot be negative."
            )

    ###########################################################################
    # Daily Return
    ###########################################################################

    @staticmethod
    def calculate_return(
        previous_close: Decimal,
        current_price: Decimal,
    ) -> Decimal:
        """
        Calculate 1-day return percentage.
        """

        if previous_close == 0:

            return Decimal("0")

        return (

            (
                current_price
                - previous_close
            )

            / previous_close

        ) * Decimal("100")

    ###########################################################################
    # Price Change
    ###########################################################################

    @staticmethod
    def calculate_change(
        previous_close: Decimal,
        current_price: Decimal,
    ) -> Decimal:
        """
        Absolute price change.
        """

        return (

            current_price

            - previous_close

        )

    ###########################################################################
    # Enrich Stock
    ###########################################################################

    def enrich(
        self,
        stock: MarketStock,
    ) -> MarketStock:
        """
        Recalculate market metrics.
        """

        self.validate_stock(
            stock,
        )

        snapshot = stock.snapshot

        snapshot.day_return_percent = (

            self.calculate_return(

                snapshot.previous_close,

                snapshot.current_price,

            )

        )

        logger.debug(

            "%-10s Return=%7.2f%%",

            stock.identity.ticker,

            float(

                snapshot.day_return_percent

            ),

        )

        return stock

    ###########################################################################
    # Batch Processing
    ###########################################################################

    def enrich_many(
        self,
        stocks: list[MarketStock],
    ) -> list[MarketStock]:
        """
        Enrich an entire market universe.
        """

        logger.info(

            "Calculating daily returns for %d stocks.",

            len(stocks),

        )

        results: list[
            MarketStock
        ] = []

        failed = 0

        for stock in stocks:

            try:

                results.append(

                    self.enrich(
                        stock,
                    )

                )

            except Exception:

                failed += 1

                logger.exception(

                    "Calculation failed | %s",

                    stock.identity.ticker,

                )

        logger.info(

            "Calculation complete | Success=%d Failed=%d",

            len(results),

            failed,

        )

        return results