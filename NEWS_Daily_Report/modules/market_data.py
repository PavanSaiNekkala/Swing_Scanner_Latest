"""
===============================================================================
File: market_data.py

Description:
    Download, normalize and prepare OHLCV market data from Yahoo Finance.

Responsibilities
----------------
1. Download daily OHLCV
2. Validate downloaded data
3. Normalize DataFrame
4. Compute Previous Close
5. Calculate Daily Returns
6. Return clean DataFrame

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

import pandas as pd
import yfinance as yf

from config import (
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    YF_INTERVAL,
    YF_PERIOD,
)

from modules.constants import (
    MarketColumns,
)

from modules.exceptions import (
    DownloadError,
    NoMarketDataError,
)

from modules.logger import logger

from modules.retry import retry

from modules.utils import (
    normalize_symbols,
)

from modules.validators import (
    validate_dataframe,
)

from modules.datetime_utils import now_ist

###############################################################################
# Data Models
###############################################################################


@dataclass(slots=True)
class DownloadStatistics:
    """
    Stores execution statistics for market data download.
    """

    requested_symbols: int = 0

    downloaded_symbols: int = 0

    failed_symbols: int = 0

    failed_list: list[str] = field(default_factory=list)

    started_at: datetime | None = None

    completed_at: datetime | None = None


###############################################################################
# Market Data Service
###############################################################################


class MarketDataService:
    """
    Yahoo Finance Market Data Service.

    Responsibilities
    ----------------
    * Download OHLCV data
    * Retrieve company names
    * Normalize downloaded data
    * Calculate returns
    """

    ###########################################################################

    def __init__(self):

        self.stats = DownloadStatistics()

        #
        # Cache company names to avoid repeated API calls.
        #

        self.company_cache: dict[str, str] = {}

        logger.info(
            "MarketDataService initialized."
        )

    ###########################################################################
    # Internal Helpers
    ###########################################################################

    def _record_failure(
        self,
        symbol: str,
    ) -> None:
        """
        Record a failed symbol.
        """

        self.stats.failed_symbols += 1

        self.stats.failed_list.append(symbol)

    ###########################################################################

    def get_statistics(
        self,
    ) -> DownloadStatistics:
        """
        Return execution statistics.
        """

        self.stats.completed_at = now_ist()

        return self.stats

    ###########################################################################

    def get_company_name(
        self,
        symbol: str,
    ) -> str:
        """
        Retrieve company name.

        Uses an in-memory cache to avoid duplicate requests.
        """

        if symbol in self.company_cache:

            return self.company_cache[symbol]

        try:

            ticker = yf.Ticker(symbol)

            info = ticker.info

            company = (
                info.get("longName")
                or info.get("shortName")
                or symbol.replace(".NS", "")
            )

        except Exception:

            company = symbol.replace(".NS", "")

        self.company_cache[symbol] = company

        return company

###############################################################################
# Download Layer
###############################################################################

    @retry(
        retries=MAX_RETRIES,
    )
    def download(
        self,
        symbols: Iterable[str],
    ) -> pd.DataFrame:
        """
        Download daily OHLCV data for all symbols.

        Returns
        -------
        Multi-index DataFrame from yfinance.
        """

        symbols = normalize_symbols(
            list(symbols),
        )

        if not symbols:

            raise ValueError(
                "No symbols supplied."
            )

        self.stats.started_at = now_ist()

        self.stats.requested_symbols = len(
            symbols,
        )

        logger.info(
            "Downloading market data for %d symbols...",
            len(symbols),
        )

        try:

            data = yf.download(
                tickers=symbols,
                period=YF_PERIOD,
                interval=YF_INTERVAL,
                auto_adjust=False,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=REQUEST_TIMEOUT,
            )

        except Exception as exc:

            logger.exception(
                "Market download failed."
            )

            raise DownloadError(
                str(exc),
            ) from exc

        if data.empty:

            raise NoMarketDataError(
                "Yahoo Finance returned empty data."
            )

        logger.info(
            "Bulk download completed."
        )

        return data

    ###########################################################################

    @retry(
        retries=MAX_RETRIES,
    )
    def download_single(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Download one symbol.

        Used as a fallback whenever the bulk download
        does not contain usable data.
        """

        logger.info(
            "Retrying %s individually.",
            symbol,
        )

        try:

            data = yf.download(
                tickers=symbol,
                period=YF_PERIOD,
                interval=YF_INTERVAL,
                auto_adjust=False,
                progress=False,
                timeout=REQUEST_TIMEOUT,
            )

        except Exception as exc:

            raise DownloadError(
                str(exc),
            ) from exc

        if data.empty:

            raise NoMarketDataError(
                f"No market data for {symbol}"
            )

        return data

    ###########################################################################

    def get_symbol_data(
        self,
        downloaded: pd.DataFrame,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Retrieve one symbol's dataframe.

        Falls back to an individual download if
        the symbol is missing from the bulk data.
        """

        try:

            stock_df = downloaded[
                symbol
            ].copy()

        except Exception:

            logger.warning(
                "%s missing in bulk download.",
                symbol,
            )

            try:

                stock_df = self.download_single(
                    symbol,
                )

            except Exception:

                self._record_failure(
                    symbol,
                )

                return pd.DataFrame()

        if stock_df.empty:

            logger.warning(
                "%s returned empty dataframe.",
                symbol,
            )

            try:

                stock_df = self.download_single(
                    symbol,
                )

            except Exception:

                self._record_failure(
                    symbol,
                )

                return pd.DataFrame()

        self.stats.downloaded_symbols += 1

        return stock_df


###############################################################################
# Data Processing Layer
###############################################################################

    def normalize_dataframe(
        self,
        stock_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize downloaded OHLCV dataframe.
        """

        if stock_df.empty:

            return stock_df

        stock_df = stock_df.copy()

        #
        # Remove timezone if present.
        #

        if stock_df.index.tz is not None:

            stock_df.index = stock_df.index.tz_localize(
                None,
            )

        #
        # Sort chronologically.
        #

        stock_df.sort_index(
            inplace=True,
        )

        #
        # Remove duplicate dates.
        #

        stock_df = stock_df[
            ~stock_df.index.duplicated(
                keep="last",
            )
        ]

        return stock_df

    ###########################################################################

    def calculate_return(
        self,
        previous_close: float,
        close: float,
    ) -> float:
        """
        Calculate one-day percentage return.
        """

        if previous_close <= 0:

            return 0.0

        return round(
            (
                (close - previous_close)
                / previous_close
            ) * 100,
            2,
        )

    ###########################################################################

    def build_record(
        self,
        symbol: str,
        company: str,
        stock_df: pd.DataFrame,
    ) -> dict:
        """
        Convert OHLCV dataframe into a report record.
        """

        stock_df = self.normalize_dataframe(
            stock_df,
        )

        validate_dataframe(
            stock_df,
        )

        if len(stock_df) < 2:

            raise ValueError(
                f"Insufficient history for {symbol}"
            )

        latest = stock_df.iloc[-1]

        previous = stock_df.iloc[-2]

        previous_close = float(
            previous["Close"]
        )

        close = float(
            latest["Close"]
        )

        record = {

            MarketColumns.SYMBOL.value:
                symbol,

            MarketColumns.COMPANY.value:
                company,

            MarketColumns.OPEN.value:
                float(latest["Open"]),

            MarketColumns.HIGH.value:
                float(latest["High"]),

            MarketColumns.LOW.value:
                float(latest["Low"]),

            MarketColumns.CLOSE.value:
                close,

            MarketColumns.ADJ_CLOSE.value:
                float(
                    latest.get(
                        "Adj Close",
                        close,
                    )
                ),

            MarketColumns.VOLUME.value:
                int(
                    latest["Volume"]
                ),

            MarketColumns.PREVIOUS_CLOSE.value:
                previous_close,

            MarketColumns.RETURN.value:
                self.calculate_return(
                    previous_close,
                    close,
                ),

        }

        return record

    ###########################################################################

    def process_symbol(
        self,
        downloaded: pd.DataFrame,
        symbol: str,
        company: str,
    ) -> dict | None:
        """
        Process a single symbol into a report record.
        """

        stock_df = self.get_symbol_data(
            downloaded,
            symbol,
        )

        if stock_df.empty:

            return None

        try:

            return self.build_record(
                symbol,
                company,
                stock_df,
            )

        except Exception as exc:

            logger.warning(
                "%s : %s",
                symbol,
                exc,
            )

            self._record_failure(
                symbol,
            )

            return None

###############################################################################
# Pipeline Layer
###############################################################################

    def prepare_market_data(
        self,
        universe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare market data for all symbols.

        Parameters
        ----------
        symbols
            NSE symbols.

        Returns
        -------
        pd.DataFrame
        """

        symbols = normalize_symbols(
            universe["Symbol"].tolist(),
        )

        company_lookup = dict(
            zip(
                universe["Symbol"],
                universe["Company"],
            )
        )

        symbols = normalize_symbols(
            list(symbols),
        )

        if not symbols:

            raise ValueError(
                "No symbols supplied."
            )

        logger.info(
            "Preparing market data."
        )

        downloaded = self.download(
            symbols,
        )

        ###############################################################################
        # Build Records
        ###############################################################################

        records = []

        total_symbols = len(
            symbols,
        )

        logger.info(
            "Processing %d downloaded symbols...",
            total_symbols,
        )

        for index, symbol in enumerate(
            symbols,
            start=1,
        ):

            #
            # Progress logging every 100 symbols.
            #

            if (
                index == 1
                or index % 100 == 0
                or index == total_symbols
            ):

                logger.info(
                    "Progress: %d/%d (%.1f%%)",
                    index,
                    total_symbols,
                    (index / total_symbols) * 100,
                )

            company = company_lookup.get(
                    symbol,
                    "",
                )

            record = self.process_symbol(
                downloaded,
                symbol,
                company,
            )

            if record is None:

                continue

            records.append(
                record,
            )

        logger.info(
            "Finished processing %d records.",
            len(
                records,
            ),
        )

        if not records:

            raise NoMarketDataError(
                "No market data prepared."
            )

        market_df = pd.DataFrame(
            records,
        )

        market_df = market_df[
            [
                MarketColumns.SYMBOL.value,
                MarketColumns.COMPANY.value,
                MarketColumns.OPEN.value,
                MarketColumns.HIGH.value,
                MarketColumns.LOW.value,
                MarketColumns.CLOSE.value,
                MarketColumns.PREVIOUS_CLOSE.value,
                MarketColumns.ADJ_CLOSE.value,
                MarketColumns.VOLUME.value,
                MarketColumns.RETURN.value,
            ]
        ]

        validate_dataframe(
            market_df,
        )

        logger.info(
            "Prepared market data for %d symbols.",
            len(
                market_df,
            ),
        )

        stats = self.get_statistics()

        logger.info(
            (
                "Download Summary | "
                "Requested=%d | "
                "Downloaded=%d | "
                "Failed=%d"
            ),
            stats.requested_symbols,
            stats.downloaded_symbols,
            stats.failed_symbols,
        )

        if stats.failed_list:

            logger.warning(
                "Failed Symbols: %s",
                ", ".join(
                    stats.failed_list,
                ),
            )

        return market_df


###############################################################################
# Public API
###############################################################################

def fetch_market_data(
    universe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Public API.
    """

    service = MarketDataService()

    return service.prepare_market_data(
        universe,
    )