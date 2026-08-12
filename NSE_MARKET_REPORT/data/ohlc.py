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

        self.nse = NSEData()

        self.session: Session = self.nse.session

        self.cache = QuoteCache()

        self.timestamp = datetime.now()

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
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Download quote JSON for a single NSE symbol.

        Features
        --------
        ✓ Cache lookup
        ✓ Retry
        ✓ Cookie refresh
        ✓ Rate limiting
        ✓ JSON validation

        Parameters
        ----------
        symbol : str

        Returns
        -------
        dict
        """

        symbol = symbol.strip().upper()

        # -------------------------------------------------------------
        # Cache Lookup
        # -------------------------------------------------------------

        cached = self.cache.get(symbol)

        if cached is not None:

            logger.debug("Cache hit : %s", symbol)

            return cached

        logger.info("Downloading quote : %s", symbol)

        # -------------------------------------------------------------
        # Retry Loop
        # -------------------------------------------------------------

        for attempt in range(1, DEFAULT_RETRIES + 1):

            try:

                # Small delay prevents NSE rate limiting
                time.sleep(REQUEST_DELAY)

                payload = self.nse._request(

                    QUOTE_ENDPOINT,

                    params={

                        "symbol": symbol

                    },

                    timeout=timeout,

                )

                if not payload:

                    raise NSEDataError(

                        f"Empty payload received for {symbol}"

                    )

                if not isinstance(payload, dict):

                    raise NSEDataError(

                        f"Invalid JSON received for {symbol}"

                    )

                # Save to cache

                self.cache.set(

                    symbol,

                    payload,

                )

                logger.info(

                    "Quote downloaded : %s",

                    symbol,

                )

                return payload

            except NSEConnectionError:

                logger.warning(

                    "Retry %d/%d : %s",

                    attempt,

                    DEFAULT_RETRIES,

                    symbol,

                )

                if attempt == DEFAULT_RETRIES:

                    raise

                time.sleep(

                    DEFAULT_BACKOFF ** attempt

                )

            except Exception as ex:

                logger.exception(ex)

                if attempt == DEFAULT_RETRIES:

                    raise

                time.sleep(

                    DEFAULT_BACKOFF ** attempt

                )

        raise NSEConnectionError(

            f"Unable to download quote for {symbol}"

        )

    ###########################################################################
    # RAW JSON EXTRACTION
    ###########################################################################

    @staticmethod
    def _safe_get(
        data: Dict[str, Any],
        *keys: str,
        default: Any = None,
    ) -> Any:
        """
        Safely retrieve nested dictionary values.

        Example
        -------
        _safe_get(payload, "priceInfo", "lastPrice")
        """

        value: Any = data

        for key in keys:

            if not isinstance(value, dict):

                return default

            value = value.get(key)

            if value is None:

                return default

        return value

    ###########################################################################

    def _download_quote(
        self,
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Returns validated quote JSON.
        """

        payload = self._request(symbol)

        required_sections = [

            "priceInfo",

            "metadata",

        ]

        missing = [

            section

            for section in required_sections

            if section not in payload

        ]

        if missing:

            raise NSEDataError(

                f"{symbol} missing sections: {missing}"

            )

        logger.debug(

            "Quote JSON validated : %s",

            symbol,

        )

        return payload


    ###########################################################################
    # JSON PARSING
    ###########################################################################

    def _parse_quote(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Parse NSE quote JSON into a flat dictionary.

        Parameters
        ----------
        payload : dict

        Returns
        -------
        dict
        """

        record = {

            "Symbol": self._safe_get(
                payload,
                "metadata",
                "symbol"
            ),

            "CMP": self._safe_get(
                payload,
                "priceInfo",
                "lastPrice"
            ),

            "Open": self._safe_get(
                payload,
                "priceInfo",
                "open"
            ),

            "High": self._safe_get(
                payload,
                "priceInfo",
                "intraDayHighLow",
                "max"
            ),

            "Low": self._safe_get(
                payload,
                "priceInfo",
                "intraDayHighLow",
                "min"
            ),

            "Close": self._safe_get(
                payload,
                "priceInfo",
                "close"
            ),

            "Previous Close": self._safe_get(
                payload,
                "priceInfo",
                "previousClose"
            ),

            "Volume": self._safe_get(
                payload,
                "securityWiseDP",
                "quantityTraded"
            ),

            "VWAP": self._safe_get(
                payload,
                "priceInfo",
                "vwap"
            ),

            "52 Week High": self._safe_get(
                payload,
                "priceInfo",
                "weekHighLow",
                "max"
            ),

            "52 Week Low": self._safe_get(
                payload,
                "priceInfo",
                "weekHighLow",
                "min"
            ),

            "Upper Circuit": self._safe_get(
                payload,
                "securityInfo",
                "upperCP"
            ),

            "Lower Circuit": self._safe_get(
                payload,
                "securityInfo",
                "lowerCP"
            ),

            "Face Value": self._safe_get(
                payload,
                "securityInfo",
                "faceValue"
            )

        }

        return record

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
        payload: Dict[str, Any],
    ) -> pd.DataFrame:
        """
        Complete processing pipeline.
        """

        record = self._parse_quote(payload)

        df = self._normalize(record)

        df = self._convert_numeric(df)

        df = self._validate(df)

        df = self._clean(df)

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

        Parameters
        ----------
        symbol : str

        Returns
        -------
        pandas.DataFrame
        """

        logger.info("Fetching OHLC : %s", symbol)

        payload = self._download_quote(symbol)

        return self._prepare_dataframe(payload)

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

        self.timestamp = datetime.now()

        self.clear_cache()

        logger.info("OHLCData refreshed.")


    def health_check(self) -> Dict[str, Any]:
        """
        Return OHLC service health information.
        """

        return {
            "component": "OHLCData",
            "status": "ready",
            "session_initialized": self.nse.cookies_initialized,
            "cache_enabled": self.cache is not None,
            "timestamp": self.timestamp.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }