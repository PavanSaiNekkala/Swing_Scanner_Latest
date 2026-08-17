"""
Yahoo Finance market data provider.

Responsibilities
----------------
- Download market data from Yahoo Finance
- Normalize market data
- Return domain models
- Handle retries
- Handle network failures

This provider does NOT perform any business logic.

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

from abc import ABC
from abc import abstractmethod
from decimal import Decimal

import yfinance as yf

from config.logging_config import get_logger
from config.settings import settings

from market.models import (
    MarketSnapshot,
    MarketStock,
    StockIdentity,
)

logger = get_logger(__name__)

###############################################################################
# Provider Interface
###############################################################################


class MarketDataProvider(ABC):
    """
    Abstract market data provider.
    """

    @abstractmethod
    def fetch_stock(
        self,
        identity: StockIdentity,
    ) -> MarketStock:
        """
        Fetch a single stock.
        """

    @abstractmethod
    def fetch_many(
        self,
        stocks: list[StockIdentity],
    ) -> list[MarketStock]:
        """
        Fetch multiple stocks.
        """

###############################################################################
# Yahoo Finance Provider
###############################################################################


class YahooFinanceProvider(
    MarketDataProvider,
):
    """
    Yahoo Finance implementation.
    """

    def __init__(
        self,
    ) -> None:

        self.timeout = (
            settings.http.timeout_seconds
        )

        self.retry_count = (
            settings.http.retry_count
        )

        logger.info(
            "YahooFinanceProvider initialized."
        )

###############################################################################
# Symbol Helpers
###############################################################################


    @staticmethod
    def build_symbol(
        ticker: str,
    ) -> str:
        """
        Convert NSE ticker to Yahoo symbol.
        """

        return (
            f"{ticker}"
            f"{settings.market.yahoo_suffix}"
        )

###############################################################################
# History Downloader
###############################################################################


    def download_history(
        self,
        symbol: str,
    ):
        """
        Download historical OHLCV data.
        """

        ticker = yf.Ticker(
            symbol,
        )

        return ticker.history(
            period="5d",
            auto_adjust=True,
            timeout=self.timeout,
        )

###############################################################################
# Metadata Downloader
###############################################################################


    def download_metadata(
        self,
        symbol: str,
    ):
        """
        Download metadata.
        """

        ticker = yf.Ticker(
            symbol,
        )

        return ticker.fast_info


###############################################################################
# Snapshot Builder
###############################################################################


    def build_snapshot(
        self,
        history,
        metadata,
    ) -> MarketSnapshot:
        """
        Convert Yahoo data into MarketSnapshot.
        """

        previous_close = Decimal(
            str(
                history["Close"].iloc[-2]
            )
        )

        current_price = Decimal(
            str(
                history["Close"].iloc[-1]
            )
        )

        return_percent = (
            (
                current_price
                - previous_close
            )
            / previous_close
        ) * Decimal("100")

        return MarketSnapshot(
            previous_close=previous_close,
            current_price=current_price,
            day_return_percent=return_percent,
            volume=int(
                history["Volume"].iloc[-1]
            ),
            market_cap=metadata.get(
                "marketCap",
            ),
        )

###############################################################################
# Domain Model Builder
###############################################################################


    def build_stock(
        self,
        identity: StockIdentity,
        history,
        metadata,
    ) -> MarketStock:
        """
        Build MarketStock.
        """

        snapshot = self.build_snapshot(
            history,
            metadata,
        )

        return MarketStock(
            identity=identity,
            snapshot=snapshot,
        )

###############################################################################
# Fetch Single Stock
###############################################################################


    def fetch_stock(
        self,
        identity: StockIdentity,
    ) -> MarketStock:
        """
        Fetch market data for a single stock.

        Parameters
        ----------
        identity
            Stock identity.

        Returns
        -------
        MarketStock

        Raises
        ------
        RuntimeError
            If the stock cannot be downloaded after all retry attempts.
        """

        symbol = self.build_symbol(
            identity.ticker,
        )

        last_exception: Exception | None = None

        for attempt in range(
            1,
            self.retry_count + 1,
        ):

            try:

                logger.debug(
                    "Downloading %s (Attempt %d/%d)",
                    symbol,
                    attempt,
                    self.retry_count,
                )

                history = self.download_history(
                    symbol,
                )

                if history.empty:

                    raise RuntimeError(
                        "No historical market data returned."
                    )

                if len(history) < 2:

                    raise RuntimeError(
                        "Insufficient historical data."
                    )

                metadata = self.download_metadata(
                    symbol,
                )

                stock = self.build_stock(
                    identity=identity,
                    history=history,
                    metadata=metadata,
                )

                logger.info(
                    "Downloaded %-12s Return=%8.2f%% Price=%10.2f",
                    identity.ticker,
                    float(
                        stock.snapshot.day_return_percent
                    ),
                    float(
                        stock.snapshot.current_price
                    ),
                )

                return stock

            except Exception as exc:

                last_exception = exc

                logger.warning(
                    "Download failed | %s | Attempt %d/%d | %s",
                    symbol,
                    attempt,
                    self.retry_count,
                    exc,
                )

        logger.error(
            "Unable to download %s after %d attempts.",
            symbol,
            self.retry_count,
        )

        raise RuntimeError(
            f"Failed downloading {symbol}"
        ) from last_exception


###############################################################################
# Fetch Multiple Stocks
###############################################################################

    def fetch_many(
        self,
        stocks: list[StockIdentity],
    ) -> list[MarketStock]:
        """
        Download multiple stocks in parallel.

        Parameters
        ----------
        stocks
            List of stock identities.

        Returns
        -------
        list[MarketStock]
            Successfully downloaded stocks.
        """

        from concurrent.futures import (
            ThreadPoolExecutor,
            as_completed,
        )

        results: list[MarketStock] = []

        success = 0

        failed = 0

        logger.info(
            "Downloading %d stocks using %d workers.",
            len(stocks),
            settings.thread_pool.max_workers,
        )

        with ThreadPoolExecutor(
            max_workers=settings.thread_pool.max_workers,
            thread_name_prefix="YahooFinance",
        ) as executor:

            futures = {
                executor.submit(
                    self.fetch_stock,
                    stock,
                ): stock
                for stock in stocks
            }

            for future in as_completed(
                futures,
            ):

                identity = futures[
                    future
                ]

                try:

                    market_stock = future.result()

                    results.append(
                        market_stock
                    )

                    success += 1

                except Exception:

                    failed += 1

                    logger.exception(
                        "Failed downloading %s",
                        identity.ticker,
                    )

                if (
                    (success + failed)
                    % 100
                    == 0
                ):

                    logger.info(
                        "Progress | Processed=%d/%d | Success=%d | Failed=%d",
                        success + failed,
                        len(stocks),
                        success,
                        failed,
                    )

        logger.info(
            "Download completed | Total=%d | Success=%d | Failed=%d",
            len(stocks),
            success,
            failed,
        )

        return sorted(
            results,
            key=lambda stock: stock.identity.ticker,
        )