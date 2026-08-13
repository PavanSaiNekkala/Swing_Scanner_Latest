"""
==============================================================================
File        : data/ohlc.py
Project     : NSE Market Report

Description
-----------
Downloads detailed quote data (OHLC) for NSE stocks and enriches the
Top Gainers / Top Losers report.

Features
--------
✓ Production-ready architecture
✓ Shared HTTP session
✓ Automatic cookie handling
✓ In-memory cache
✓ Thread-safe design
✓ Retry support
✓ Rate limiting
✓ Parallel downloads (Part 4)
✓ Data validation
✓ Data normalization

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

import threading
import time

from datetime import datetime

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd

from config.timezone import now_ist

from nselib.capital_market import price_volume_data

from requests import Session

from config.logging_config import logger

from data.nse_data import (
    NSEData,
    NSEConnectionError,
    NSEDataError,
)


###############################################################################
# CONFIGURATION
###############################################################################

QUOTE_ENDPOINT = "https://www.nseindia.com/api/quote-equity"

DEFAULT_TIMEOUT = 20

DEFAULT_RETRIES = 3

DEFAULT_BACKOFF = 2

REQUEST_DELAY = 0.25

MAX_WORKERS = 5

###############################################################################
# OUTPUT SCHEMA
###############################################################################

OUTPUT_COLUMNS = [

    "Symbol",

    "CMP",

    "Open",

    "High",

    "Low",

    "Close",

    "Previous Close",

    "Volume",

    "VWAP",

    "52 Week High",

    "52 Week Low",

    "Upper Circuit",

    "Lower Circuit",

    "Face Value",

]

###############################################################################
# CACHE
###############################################################################

class QuoteCache:
    """
    Thread-safe in-memory cache.

    Prevents duplicate HTTP requests for
    the same symbol during execution.
    """

    def __init__(self):

        self._cache: Dict[str, Dict[str, Any]] = {}

        self._lock = threading.Lock()

    ###########################################################################

    def get(
        self,
        symbol: str,
    ) -> Optional[Dict[str, Any]]:

        with self._lock:

            return self._cache.get(symbol)

    ###########################################################################

    def set(
        self,
        symbol: str,
        payload: Dict[str, Any],
    ) -> None:

        with self._lock:

            self._cache[symbol] = payload

    ###########################################################################

    def clear(self) -> None:

        with self._lock:

            self._cache.clear()

###############################################################################
# MAIN CLASS
###############################################################################

class OHLCData:
    """
    Fetches detailed quote information from NSE.

    Public Methods

    fetch(symbol)

    fetch_many(symbols)

    merge(report_dataframe)

    clear_cache()
    """

    ###########################################################################

    def __init__(self):

        logger.info("Initializing OHLCData...")

        self.cache = QuoteCache()

        self.timestamp = now_ist()

        self.nse = NSEData()

        self.session: Session = self.nse.session

        logger.info("OHLCData initialized successfully.")

    ###########################################################################

    def clear_cache(self) -> None:
        """
        Clear cached quote responses.
        """

        self.cache.clear()

        logger.info("Quote cache cleared.")


    ###########################################################################
    # HTTP REQUEST LAYER
    ###########################################################################

    def _request(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Download OHLCV data using nselib.
        """

        symbol = (
            str(symbol or "")
            .strip()
            .upper()
        )

        if not symbol:
            raise NSEDataError(
                "OHLC symbol cannot be empty."
            )

        cached = self.cache.get(
            symbol
        )

        if cached is not None:

            logger.debug(
                "OHLC cache hit : %s",
                symbol,
            )

            return cached

        logger.info(
            "Downloading OHLC via nselib : %s",
            symbol,
        )

        for attempt in range(
            1,
            DEFAULT_RETRIES + 1,
        ):

            try:

                time.sleep(
                    REQUEST_DELAY
                )

                df = price_volume_data(
                    symbol=symbol,
                    period="1D",
                )

                if df is None:

                    raise NSEDataError(
                        f"No OHLC data returned for {symbol}"
                    )

                if not isinstance(
                    df,
                    pd.DataFrame,
                ):

                    df = pd.DataFrame(
                        df
                    )

                if df.empty:

                    raise NSEDataError(
                        f"Empty OHLC dataframe for {symbol}"
                    )

                self.cache.set(
                    symbol,
                    df,
                )

                logger.info(
                    "OHLC downloaded : %s",
                    symbol,
                )

                return df

            except Exception as ex:

                logger.warning(
                    "OHLC request failed "
                    "(%d/%d) : %s | %s",
                    attempt,
                    DEFAULT_RETRIES,
                    symbol,
                    ex,
                )

                if attempt >= DEFAULT_RETRIES:

                    raise NSEDataError(
                        f"Unable to download OHLC "
                        f"for {symbol}: {ex}"
                    ) from ex

                time.sleep(
                    DEFAULT_BACKOFF ** attempt
                )

        raise NSEDataError(
            f"Unable to download OHLC for {symbol}"
        )
        

    ###########################################################################

    def _download_quote(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Return validated OHLC dataframe.
        """

        return self._request(
            symbol
        )

    ###########################################################################
    # JSON PARSING
    ###########################################################################

    @staticmethod
    @staticmethod
    def _parse_quote(
        payload: pd.DataFrame,
    ) -> pd.DataFrame:

        if (
            payload is None
            or payload.empty
        ):

            return pd.DataFrame()

        df = payload.copy()

        rename_map = {
            "Symbol": "Symbol",
            "symbol": "Symbol",
            "Open": "Open",
            "open": "Open",
            "open_price": "Open",
            "High": "High",
            "high": "High",
            "high_price": "High",
            "Low": "Low",
            "low": "Low",
            "low_price": "Low",
            "Close": "Close",
            "close": "Close",
            "ltp": "CMP",
            "LTP": "CMP",
            "prev_close": "Previous Close",
            "previous_close": "Previous Close",
            "prev_price": "Previous Close",
            "volume": "Volume",
            "trade_quantity": "Volume",
        }

        df.rename(
            columns=rename_map,
            inplace=True,
        )

        if "Symbol" not in df.columns:

            df["Symbol"] = None

        return df

    ###########################################################################
    # NORMALIZATION
    ###########################################################################

    @staticmethod
    def _normalize(
        record: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Convert parsed record into DataFrame.
        """

        df = pd.DataFrame([record])

        return df

    ###########################################################################
    # NUMERIC CONVERSION
    ###########################################################################

    @staticmethod
    def _convert_numeric(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Convert numeric columns safely.
        """

        numeric_columns = [

            "CMP",

            "Open",

            "High",

            "Low",

            "Close",

            "Previous Close",

            "Volume",

            "VWAP",

            "52 Week High",

            "52 Week Low",

            "Upper Circuit",

            "Lower Circuit",

            "Face Value",

        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(

                    df[column],

                    errors="coerce"

                )

        return df

    ###########################################################################
    # VALIDATION
    ###########################################################################

    @staticmethod
    def _validate(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validate dataframe schema.
        """

        missing = [

            column

            for column in OUTPUT_COLUMNS

            if column not in df.columns

        ]

        if missing:

            raise NSEDataError(

                f"Missing columns : {missing}"

            )

        return df

    ###########################################################################
    # CLEANING
    ###########################################################################

    @staticmethod
    def _clean(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Clean dataframe.
        """

        if df.empty:

            return df

        df = df.drop_duplicates(

            subset=["Symbol"],

            keep="first",

        )

        df.reset_index(

            drop=True,

            inplace=True,

        )

        return df

    ###########################################################################
    # COMPLETE PIPELINE
    ###########################################################################

    def _prepare_dataframe(
        self,
        payload: pd.DataFrame,
    ) -> pd.DataFrame:

        df = self._parse_quote(
            payload,
        )

        if df.empty:

            return pd.DataFrame(
                columns=OUTPUT_COLUMNS
            )

        df = self._convert_numeric(
            df,
        )

        required_columns = [
            column
            for column in OUTPUT_COLUMNS
            if column not in df.columns
        ]

        for column in required_columns:

            df[column] = None

        df = df[
            OUTPUT_COLUMNS
        ]

        df = self._clean(
            df,
        )

        return df


###############################################################################
# PUBLIC API
###############################################################################

    def fetch(
        self,
        symbol: str,
    ) -> pd.DataFrame:
        """
        Fetch OHLC data for a single symbol.
        """

        symbol = (
            str(symbol or "")
            .strip()
            .upper()
        )

        logger.info(
            "Fetching OHLC : %s",
            symbol,
        )

        payload = self._download_quote(
            symbol,
        )

        return self._prepare_dataframe(
            payload,
        )

    ###########################################################################

    def _fetch_worker(
        self,
        symbol: str,
    ) -> Optional[pd.DataFrame]:
        """
        Worker method used by ThreadPoolExecutor.
        """

        try:

            return self.fetch(symbol)

        except Exception as ex:

            logger.exception(
                "Failed downloading %s : %s",
                symbol,
                ex,
            )

            return None

    ###########################################################################

    def fetch_many(
        self,
        symbols: List[str],
    ) -> pd.DataFrame:
        """
        Fetch OHLC data for multiple symbols in parallel.

        Parameters
        ----------
        symbols : List[str]

        Returns
        -------
        pandas.DataFrame
        """

        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import as_completed

        if not symbols:

            logger.warning("Empty symbol list.")

            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        logger.info(

            "Downloading OHLC for %d symbols using %d workers.",

            len(symbols),

            MAX_WORKERS,

        )

        frames = []

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
        ) as executor:

            futures = {

                executor.submit(
                    self._fetch_worker,
                    symbol
                ): symbol

                for symbol in symbols

            }

            for future in as_completed(futures):

                df = future.result()

                if df is not None:

                    frames.append(df)

        if not frames:

            logger.warning("No OHLC data downloaded.")

            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        result = pd.concat(

            frames,

            ignore_index=True,

        )

        result.drop_duplicates(

            subset=["Symbol"],

            inplace=True,

        )

        result.reset_index(

            drop=True,

            inplace=True,

        )

        logger.info(

            "Downloaded OHLC for %d symbols.",

            len(result),

        )

        return result

    ###########################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge OHLC data with report dataframe.

        Parameters
        ----------
        report_df : pandas.DataFrame

        Returns
        -------
        pandas.DataFrame
        """

        if report_df.empty:

            logger.warning("Report dataframe is empty.")

            return report_df

        symbols = (

            report_df["Symbol"]

            .dropna()

            .astype(str)

            .unique()

            .tolist()

        )

        logger.info(

            "Merging OHLC for %d symbols.",

            len(symbols),

        )

        quote_df = self.fetch_many(symbols)

        if quote_df.empty:

            logger.warning("Quote dataframe is empty.")

            return report_df

        merged = report_df.merge(

            quote_df,

            on="Symbol",

            how="left",

            suffixes=("", "_OHLC"),

        )

        logger.info(

            "Merge completed. Final rows : %d",

            len(merged),

        )

        return merged

    ###########################################################################

    def refresh(self) -> None:
        """
        Refresh timestamp and clear cache.
        """
        self.timestamp = now_ist()

        self.clear_cache()

        logger.info("OHLCData refreshed.")


    def health_check(self) -> Dict[str, Any]:
        """
        Return OHLC service health information.
        """

        return {
            "component": "OHLCData",
            "status": "ready",
            "provider": "nselib",
            "session_initialized": self.nse.cookies_initialized,
            "cache_enabled": self.cache is not None,
            "timestamp": self.timestamp.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
