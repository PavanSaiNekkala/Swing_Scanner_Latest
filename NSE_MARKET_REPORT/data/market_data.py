"""
===============================================================================
Module    : market_data.py
Package   : data
Purpose   : Business service for market data
Layer     : Service Layer
Provider  : Yahoo Finance
===============================================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from config.logging_config import get_logger
from config.timezone import ist_now

from data.providers.yfinance_provider import YahooFinanceProvider

logger = get_logger(__name__)


###############################################################################
# DEFAULT UNIVERSE
###############################################################################

DEFAULT_UNIVERSE = Path(
    "data/universe/news_universe.csv"
)


###############################################################################
# MARKET DATA SERVICE
###############################################################################

class MarketData:
    """
    Business layer sitting between main.py and
    YahooFinanceProvider.

    Responsibilities
    ----------------
    • Load and maintain the market universe
    • Initialize/configure the provider
    • Expose application-facing market-data APIs
    • Provide health status
    • Manage provider lifecycle
    """

    def __init__(
        self,
        provider: Optional[YahooFinanceProvider] = None,
        universe_file: Optional[Path] = None,
    ) -> None:

        logger.info(
            "Initializing MarketData..."
        )

        self.universe_file = (
            Path(
                universe_file
            )
            if universe_file is not None
            else DEFAULT_UNIVERSE
        )

        # ---------------------------------------------------------
        # Load market universe
        # ---------------------------------------------------------

        self.symbols = (
            self._load_universe()
        )

        # ---------------------------------------------------------
        # Initialize provider with universe
        # ---------------------------------------------------------

        self.provider = (
            provider
            if provider is not None
            else YahooFinanceProvider(
                symbols=self.symbols,
            )
        )

        # ---------------------------------------------------------
        # Ensure provider uses latest universe
        # ---------------------------------------------------------

        self.set_universe(
            self.symbols
        )

        logger.info(
            "Loaded %d symbols.",
            len(
                self.symbols
            ),
        )

        logger.info(
            "MarketData initialized successfully."
        )

    ###############################################################################
    # UPDATE UNIVERSE
    ###############################################################################

    def set_universe(
        self,
        symbols: list[str],
    ) -> None:

        self.symbols = sorted(
            list(
                set(symbols)
            )
        )

        logger.info(
            "Universe updated (%d symbols).",
            len(
                self.symbols
            ),
        )

        if hasattr(
            self.provider,
            "set_universe",
        ):

            self.provider.set_universe(
                self.symbols
            )
            
    ###########################################################################
    # UNIVERSE
    ###########################################################################

    def _load_universe(
        self,
    ) -> list[str]:
        """
        Load the market symbol universe from CSV.
        """

        if not self.universe_file.exists():

            raise FileNotFoundError(
                "Market universe file not found: "
                f"{self.universe_file}"
            )

        dataframe = pd.read_csv(
            self.universe_file
        )

        if dataframe.empty:

            raise ValueError(
                "Market universe file is empty: "
                f"{self.universe_file}"
            )

        normalized_columns = {
            str(
                column
            )
            .strip()
            .casefold(): column
            for column in dataframe.columns
        }

        symbol_column = None

        for candidate in (
            "symbol",
            "stock",
            "ticker",
        ):

            if candidate in normalized_columns:

                symbol_column = (
                    normalized_columns[
                        candidate
                    ]
                )

                break

        if symbol_column is None:

            raise RuntimeError(
                "Universe file does not contain a "
                "supported symbol column. "
                f"Available columns: "
                f"{list(dataframe.columns)}"
            )

        symbols = (
            dataframe[
                symbol_column
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        symbols = symbols[
            symbols.ne("")
        ]

        symbols = symbols[
            ~symbols.isin(
                {
                    "SYMBOL",
                    "STOCK",
                    "TICKER",
                    "NAN",
                    "NONE",
                }
            )
        ]

        # Preserve first occurrence order while removing duplicates.
        symbols = list(
            dict.fromkeys(
                symbols.tolist()
            )
        )

        if not symbols:

            raise RuntimeError(
                "No valid market symbols were found in "
                f"{self.universe_file}"
            )

        return symbols

    def reload_universe(
        self,
    ) -> None:
        """
        Reload the configured universe from disk.
        """

        self.symbols = (
            self._load_universe()
        )

        self.set_universe(
            self.symbols
        )

        logger.info(
            "Universe reloaded | Symbols=%d",
            len(
                self.symbols
            ),
        )

    def universe(
        self,
    ) -> list[str]:
        """
        Return a copy of the active market universe.
        """

        return self.symbols.copy()

    def set_universe(
        self,
        symbols: list[str],
    ) -> None:
        """
        Replace the active market universe and propagate it
        to the underlying provider.
        """

        normalized_symbols = []

        for symbol in symbols:

            value = (
                str(
                    symbol
                )
                .strip()
                .upper()
            )

            if not value:

                continue

            normalized_symbols.append(
                value
            )

        self.symbols = list(
            dict.fromkeys(
                normalized_symbols
            )
        )

        logger.info(
            "Universe updated | Symbols=%d",
            len(
                self.symbols
            ),
        )

        if hasattr(
            self.provider,
            "set_symbols",
        ):

            self.provider.set_symbols(
                self.symbols
            )

        elif hasattr(
            self.provider,
            "set_universe",
        ):

            self.provider.set_universe(
                self.symbols
            )

        else:

            raise AttributeError(
                "YahooFinanceProvider does not expose "
                "set_symbols() or set_universe()."
            )

    ###########################################################################
    # PUBLIC MARKET APIs
    ###########################################################################

    def fetch_quotes(
        self,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Fetch latest market quotes.
        """

        requested_symbols = (
            symbols
            if symbols is not None
            else self.symbols
        )

        if not requested_symbols:

            raise RuntimeError(
                "No market symbols are available "
                "for quote retrieval."
            )

        logger.info(
            "Fetching quotes | Symbols=%d",
            len(
                requested_symbols
            ),
        )

        return self.provider.fetch_quotes(
            requested_symbols
        )

    def fetch_ohlc(
        self,
        symbol: str,
        *,
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch historical OHLC data for one symbol.
        """

        if not symbol:

            raise ValueError(
                "Symbol is required for OHLC retrieval."
            )

        logger.info(
            "Fetching OHLC | Symbol=%s | "
            "Period=%s | Interval=%s",
            symbol,
            period,
            interval,
        )

        return self.provider.fetch_ohlc(
            symbol,
            period=period,
            interval=interval,
        )

    def fetch_top_gainers(
        self,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Return the top gaining securities
        from the configured universe.
        """

        if not self.symbols:

            raise RuntimeError(
                "Cannot fetch top gainers because "
                "the market universe is empty."
            )

        logger.info(
            "Fetching Top Gainers..."
        )

        return self.provider.fetch_top_gainers(
            symbols=self.symbols,
            limit=limit,
        )

    def fetch_top_losers(
        self,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Return the top losing securities
        from the configured universe.
        """

        if not self.symbols:

            raise RuntimeError(
                "Cannot fetch top losers because "
                "the market universe is empty."
            )

        logger.info(
            "Fetching Top Losers..."
        )

        return self.provider.fetch_top_losers(
            symbols=self.symbols,
            limit=limit,
        )

    def fetch_most_active(
        self,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Return the most active securities.
        """

        logger.info(
            "Fetching Most Active..."
        )

        if hasattr(
            self.provider,
            "fetch_most_active",
        ):

            return self.provider.fetch_most_active(
                symbols=self.symbols,
                limit=limit,
            )

        return pd.DataFrame()

    def fetch_indices(
        self,
    ) -> pd.DataFrame:
        """
        Fetch benchmark indices when supported
        by the configured provider.
        """

        logger.info(
            "Fetching benchmark indices..."
        )

        if hasattr(
            self.provider,
            "fetch_indices",
        ):

            return self.provider.fetch_indices()

        return pd.DataFrame()

    def fetch_market_breadth(
        self,
    ) -> dict:
        """
        Fetch market breadth when supported.
        """

        logger.info(
            "Fetching market breadth..."
        )

        if hasattr(
            self.provider,
            "fetch_market_breadth",
        ):

            return self.provider.fetch_market_breadth()

        return {}

    ###########################################################################
    # PROVIDER INFORMATION
    ###########################################################################

    @property
    def provider_name(
        self,
    ) -> str:
        """
        Return the configured provider class name.
        """

        return type(
            self.provider
        ).__name__

    ###########################################################################
    # HEALTH
    ###########################################################################

    def health_check(
        self,
    ) -> dict:
        """
        Return structured market-data health status.
        """

        try:

            if not self.symbols:

                return {
                    "component": "MarketData",
                    "provider": self.provider_name,
                    "status": "WARNING",
                    "symbols_loaded": 0,
                    "timestamp": ist_now(),
                }

            health = (
                self.provider.health()
            )

            return {
                "component": "MarketData",
                "provider": health.get(
                    "provider",
                    self.provider_name,
                ),
                "status": health.get(
                    "status",
                    "UNKNOWN",
                ),
                "symbols_loaded": len(
                    self.symbols
                ),
                "timestamp": ist_now(),
            }

        except Exception as exc:

            logger.exception(
                "MarketData health check failed."
            )

            raise RuntimeError(
                "MarketData health check failed."
            ) from exc

    ###########################################################################
    # CLEANUP
    ###########################################################################

    def close(
        self,
    ) -> None:
        """
        Close the underlying provider when supported.
        """

        logger.info(
            "Closing MarketData..."
        )

        if hasattr(
            self.provider,
            "close",
        ):

            self.provider.close()

        logger.info(
            "MarketData closed."
        )


###############################################################################
# UNIVERSE
###############################################################################

    def _load_universe(
        self,
    ) -> list[str]:
        """
        Load the market universe.
        """

        if not self.universe_file.exists():

            logger.warning(
                "Universe file not found: %s",
                self.universe_file,
            )

            return []

        df = pd.read_csv(
            self.universe_file
        )

        possible_columns = [

            "Symbol",

            "SYMBOL",

            "symbol",

            "Ticker",

            "ticker",

        ]

        column = next(

            (
                c
                for c in possible_columns
                if c in df.columns
            ),

            None,

        )

        if column is None:

            raise RuntimeError(
                "Universe file does not contain a Symbol column."
            )

        symbols = (

            df[column]
            .astype(str)
            .str.strip()
            .tolist()

        )

        symbols = [

            s
            for s in symbols
            if s

        ]

        return sorted(
            list(
                set(symbols)
            )
        )


###############################################################################
# CONFIGURATION
###############################################################################

    def reload_universe(
        self,
    ) -> None:
        """
        Reload symbol universe.
        """

        self.symbols = self._load_universe()

        self.provider.set_universe(
            self.symbols
        )

        logger.info(
            "Universe reloaded (%d symbols).",
            len(self.symbols),
        )


    def universe(
        self,
    ) -> list[str]:

        return self.symbols.copy()


###############################################################################
# PROVIDER ACCESS
###############################################################################

    @property
    def provider_name(
        self,
    ) -> str:

        return type(
            self.provider
        ).__name__


###############################################################################
# PUBLIC MARKET APIS
###############################################################################

    def fetch_quotes(
        self,
        symbols: list[str],
    ) -> pd.DataFrame:
        """
        Fetch latest quotes.
        """

        logger.info(
            "Fetching quotes for %d symbols...",
            len(symbols),
        )

        symbols = symbols or self.symbols

        if not symbols:
            raise RuntimeError(
                "No symbols available."
            )

        return self.provider.fetch_quotes(symbols)

    ###########################################################################

    def fetch_ohlc(
        self,
        symbols: list[str],
        period: str = "6mo",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch OHLC history.
        """

        logger.info(
            "Fetching OHLC data..."
        )

        return self.provider.fetch_ohlc(
            symbols=symbols,
            period=period,
            interval=interval,
        )

###############################################################################
# MARKET MOVERS
###############################################################################

    def fetch_top_gainers(
        self,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Return today's top gainers.
        """

        logger.info(
            "Fetching Top Gainers..."
        )

        return self.provider.fetch_top_gainers(
            limit=limit
        )

    ###########################################################################

    def fetch_top_losers(
        self,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Return today's top losers.
        """

        logger.info(
            "Fetching Top Losers..."
        )

        return self.provider.fetch_top_losers(
            limit=limit
        )

    ###########################################################################

    def fetch_most_active(
        self,
        limit: int = 20,
    ) -> pd.DataFrame:
        """
        Return most active stocks.
        """

        logger.info(
            "Fetching Most Active..."
        )

        return self.provider.fetch_most_active(
            limit=limit
        )

###############################################################################
# INDICES
###############################################################################

    def fetch_indices(
        self,
    ) -> pd.DataFrame:
        """
        Fetch benchmark indices.
        """

        logger.info(
            "Fetching benchmark indices..."
        )

        if hasattr(
            self.provider,
            "fetch_indices",
        ):
            return self.provider.fetch_indices()

        return pd.DataFrame()

###############################################################################
# MARKET BREADTH
###############################################################################

    def fetch_market_breadth(
        self,
    ) -> dict:
        """
        Fetch advance decline information.
        """

        logger.info(
            "Fetching market breadth..."
        )

        if hasattr(
            self.provider,
            "fetch_market_breadth",
        ):
            return self.provider.fetch_market_breadth()

        return {}

###############################################################################
# UTILITIES
###############################################################################

    def set_universe(
        self,
        symbols: list[str],
    ) -> None:

        self.symbols = sorted(
            list(
                set(symbols)
            )
        )

        logger.info(
            "Universe updated (%d symbols).",
            len(self.symbols),
        )

        if hasattr(
            self.provider,
            "set_universe",
        ):
            self.provider.set_universe(
                self.symbols
            )

###############################################################################
# HEALTH
###############################################################################

    def health_check(
        self,
    ) -> str:
        """
        Health status for application.
        """

        try:

            health = self.provider.health()

            status = health.get(
                "status",
                "UNKNOWN",
            )

            provider = health.get(
                "provider",
                self.provider.__class__.__name__,
            )

            return {
                "component": "MarketData",
                "provider": provider,
                "status": status,
                "symbols_loaded": len(self.symbols),
                "timestamp": ist_now(),
            }

        except Exception as ex:

            logger.exception(
                "MarketData health check failed."
            )

            raise RuntimeError(
                "MarketData unavailable."
            ) from ex

###############################################################################
# CLEANUP
###############################################################################

    def close(
        self,
    ) -> None:
        """
        Shutdown provider.
        """

        logger.info(
            "Closing MarketData..."
        )

        if hasattr(
            self.provider,
            "close",
        ):
            self.provider.close()

        logger.info(
            "MarketData closed."
        )