"""
==============================================================================
File        : data/nse_data.py
Project     : NSE Market Report

Description
-----------
Production-grade NSE data collector.
=============================================================================="""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.config import (
    TOP_GAINERS_COUNT,
    TOP_LOSERS_COUNT,
)

from config.logging_config import logger

try:
    from nselib.capital_market import live_market_data
    NSELIB_AVAILABLE = True
except ImportError:
    NSELIB_AVAILABLE = False


###############################################################################
# NSE URLS
###############################################################################

BASE_URL = "https://www.nseindia.com"

ENDPOINTS = {

    "MARKET_HOME":
        "https://www.nseindia.com/",

    "LIVE_VARIATION":
        "https://www.nseindia.com/api/live-analysis-variations",

}


###############################################################################
# REQUEST HEADERS
###############################################################################

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Origin": "https://www.nseindia.com",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


###############################################################################
# PROJECT SCHEMA
###############################################################################

OUTPUT_COLUMNS = [

    "Timestamp",
    "Category",
    "Symbol",
    "Company",
    "CMP",
    "Open",
    "High",
    "Low",
    "Previous Close",
    "Close",
    "Volume",
    "1 Day Change %",

]


###############################################################################
# COLUMN NORMALIZATION
###############################################################################

COLUMN_MAPPING = {

    "symbol": "Symbol",
    "identifier": "Symbol",

    "companyName": "Company",
    "meta": "Company",

    "ltp": "CMP",
    "lastPrice": "CMP",

    "open": "Open",
    "open_price": "Open",

    "high": "High",
    "high_price": "High",
    "dayHigh": "High",

    "low": "Low",
    "low_price": "Low",
    "dayLow": "Low",

    "close": "Close",

    "prev_price": "Previous Close",
    "previousClose": "Previous Close",

    "trade_quantity": "Volume",
    "volume": "Volume",
    "totalTradedVolume": "Volume",

    "net_price": "1 Day Change %",
    "pChange": "1 Day Change %",
    "perChange": "1 Day Change %",

}


###############################################################################
# CUSTOM EXCEPTIONS
###############################################################################

class NSEError(Exception):
    """Base NSE exception."""


class NSEConnectionError(NSEError):
    """Raised when connection to NSE fails."""


class NSEDataError(NSEError):
    """Raised when NSE returns invalid data."""


###############################################################################
# MAIN CLASS
###############################################################################

class NSEData:
    """
    Production-grade NSE client.
    """

    def __init__(self):

        self.timestamp = datetime.now()

        self.session = self._create_session()

        self.cookies_initialized = False

        logger.info("NSEData initialized.")

    ###########################################################################
    # SESSION CREATION
    ###########################################################################

    @staticmethod
    def _create_session() -> Session:
        """
        Creates a requests Session with retry support.
        """

        session = requests.Session()

        retry = Retry(

            total=5,
            connect=5,
            read=5,

            backoff_factor=1.5,

            status_forcelist=[
                403,
                429,
                500,
                502,
                503,
                504,
            ],

            allowed_methods=[
                "GET",
            ],

            raise_on_status=False,

        )

        adapter = HTTPAdapter(max_retries=retry)

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        session.headers.update(DEFAULT_HEADERS)

        return session

    ###########################################################################
    # COOKIE INITIALIZATION
    ###########################################################################

    def _initialize_session(self) -> None:
        """
        Initializes NSE cookies.

        NSE blocks direct API access until the homepage
        has been visited.
        """

        if self.cookies_initialized:
            return

        logger.info("Initializing NSE session...")

        try:

            response = self.session.get(
                ENDPOINTS["MARKET_HOME"],
                timeout=20,
            )

            response.raise_for_status()

            if not self.session.cookies:
                raise NSEConnectionError("No cookies received from NSE.")

            self.cookies_initialized = True

            time.sleep(1)

            logger.info("NSE session initialized.")

        except Exception as ex:

            logger.exception(ex)

            raise NSEConnectionError(
                "Unable to initialize NSE session."
            )

    ###########################################################################
    # HTTP REQUEST LAYER
    ###########################################################################

    def _request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 20,
    ) -> Dict[str, Any]:
        """
        Execute a GET request to the NSE API.
        """

        self._initialize_session()

        for attempt in range(2):

            try:

                logger.debug(
                    "GET %s | params=%s | attempt=%d",
                    url,
                    params,
                    attempt + 1,
                )

                response: Response = self.session.get(
                    url=url,
                    params=params,
                    timeout=timeout,
                )

                if response.status_code in (401, 403):

                    logger.warning(
                        "Cookie expired (%s). Reinitializing...",
                        response.status_code,
                    )

                    self.cookies_initialized = False
                    self._initialize_session()

                    continue

                response.raise_for_status()

                payload = response.json()

                if payload is None:
                    raise NSEDataError("Empty JSON received.")

                if not isinstance(payload, dict):
                    raise NSEDataError("Unexpected JSON response.")

                return payload

            except requests.Timeout as ex:

                logger.exception(ex)

                if attempt == 1:
                    raise NSEConnectionError(
                        "NSE request timed out."
                    )

            except requests.ConnectionError as ex:

                logger.exception(ex)

                if attempt == 1:
                    raise NSEConnectionError(
                        "Unable to connect to NSE."
                    )

            except requests.HTTPError:

                raise NSEConnectionError(
                    f"HTTP Error : {response.status_code}"
                )

            except ValueError as ex:

                logger.exception(ex)

                raise NSEDataError(
                    "Unable to decode JSON response."
                )

        raise NSEConnectionError(
            "Unable to retrieve data from NSE."
        )

    ###########################################################################
    # RAW PROVIDER METHODS
    ###########################################################################

    def _download_live_variation(
        self,
        index: str,
    ) -> Dict[str, Any]:
        """
        Download raw NSE market variation JSON.
        """

        logger.info(
            "Downloading NSE Live Variation (%s)...",
            index,
        )

        payload = self._request(
            f"{ENDPOINTS['LIVE_VARIATION']}?index={index}"
        )

        logger.info(
            "Live Variation downloaded successfully."
        )

        return payload

    ###########################################################################
    # PROVIDER ABSTRACTION
    ###########################################################################

    def _provider(
        self,
        index: str,
    ) -> Dict[str, Any]:
        """
        Returns market payload.
        """

        try:

            return self._download_live_variation(index)

        except Exception as ex:

            logger.exception(ex)

            raise

    ###########################################################################
    # JSON EXTRACTION
    ###########################################################################

    @staticmethod
    def _extract_section(
        payload: Dict[str, Any],
        section: str,
    ) -> List[Dict[str, Any]]:
        """
        Extract one section from the payload.

        Examples
        --------
        NIFTY
        BANKNIFTY
        """

        if section not in payload:

            raise NSEDataError(
                f"Section '{section}' not found."
            )

        value = payload[section]

        if isinstance(value, dict):

            if "data" in value:

                value = value["data"]

        if not isinstance(value, list):

            raise NSEDataError(
                f"Section '{section}' is invalid."
            )

        return value

    ###########################################################################
    # RAW DATA DOWNLOAD
    ###########################################################################

    def _download_gainers(self) -> pd.DataFrame:
        """
        Download raw Top Gainers.
        """

        payload = self._provider("gainers")

        records = self._extract_section(
            payload,
            "NIFTY",
        )

        df = pd.DataFrame(records)

        logger.info(
            "Downloaded %d Top Gainers.",
            len(df),
        )

        return df

    ###########################################################################

    def _download_losers(self) -> pd.DataFrame:
        """
        Download raw Top Losers.
        """

        payload = self._provider("losers")

        records = self._extract_section(
            payload,
            "NIFTY",
        )

        df = pd.DataFrame(records)

        logger.info(
            "Downloaded %d Top Losers.",
            len(df),
        )

        return df

    ###########################################################################
    # DATA NORMALIZATION
    ###########################################################################

    def _normalize_dataframe(
        self,
        df: pd.DataFrame,
        category: str,
    ) -> pd.DataFrame:
        """
        Normalize the raw NSE DataFrame into the project's schema.
        """

        if df.empty:

            logger.warning(
                "%s dataframe is empty.",
                category,
            )

            return pd.DataFrame(
                columns=OUTPUT_COLUMNS
            )

        df = df.rename(
            columns=COLUMN_MAPPING
        )

        for column in OUTPUT_COLUMNS:

            if column not in df.columns:

                df[column] = None

        df["Timestamp"] = self.timestamp.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        df["Category"] = category

        df = df[OUTPUT_COLUMNS]

        return df

    ###########################################################################
    # DATA TYPE CONVERSION
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
            "Previous Close",
            "Close",
            "Volume",
            "1 Day Change %",

        ]

        for column in numeric_columns:

            if column in df.columns:

                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce",
                )

        return df

    ###########################################################################
    # DATA CLEANING
    ###########################################################################

    @staticmethod
    def _clean_dataframe(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Remove duplicates and reset index.
        """

        if df.empty:

            return df

        df = df.drop_duplicates(
            subset=["Symbol"],
            keep="first",
        )

        df = df.reset_index(
            drop=True,
        )

        return df

    ###########################################################################
    # VALIDATION
    ###########################################################################

    @staticmethod
    def _validate_dataframe(
        df: pd.DataFrame,
    ) -> None:
        """
        Validate the output schema.
        """

        missing = [

            column

            for column in OUTPUT_COLUMNS

            if column not in df.columns

        ]

        if missing:

            raise NSEDataError(
                f"Missing columns: {missing}"
            )

        if df.empty:

            logger.warning(
                "Output dataframe is empty."
            )

    ###########################################################################
    # PIPELINE
    ###########################################################################

    def _prepare_dataframe(
        self,
        raw_df: pd.DataFrame,
        category: str,
    ) -> pd.DataFrame:
        """
        Complete processing pipeline.
        """

        logger.info(
            "Preparing %s dataframe...",
            category,
        )

        df = self._normalize_dataframe(
            raw_df,
            category,
        )

        df = self._convert_numeric(df)

        df = self._clean_dataframe(df)

        self._validate_dataframe(df)

        logger.info(
            "%s dataframe ready (%d rows).",
            category,
            len(df),
        )

        return df


    ###########################################################################
    # PUBLIC API
    ###########################################################################

    def fetch_top_gainers(self) -> pd.DataFrame:
        """
        Fetch Top N NSE Gainers.

        Returns
        -------
        pandas.DataFrame
        """

        logger.info("Fetching Top Gainers...")

        raw_df = self._download_gainers()

        df = self._prepare_dataframe(
            raw_df,
            category="Gainer",
        )

        df = df.head(
            TOP_GAINERS_COUNT
        )

        logger.info(
            "Top Gainers ready (%d stocks).",
            len(df),
        )

        return df

    ###########################################################################

    def fetch_top_losers(self) -> pd.DataFrame:
        """
        Fetch Top N NSE Losers.

        Returns
        -------
        pandas.DataFrame
        """

        logger.info("Fetching Top Losers...")

        raw_df = self._download_losers()

        df = self._prepare_dataframe(
            raw_df,
            category="Loser",
        )

        df = df.head(
            TOP_LOSERS_COUNT
        )

        logger.info(
            "Top Losers ready (%d stocks).",
            len(df),
        )

        return df

    ###########################################################################

    def fetch_market_report(self) -> pd.DataFrame:
        """
        Returns a combined dataframe containing
        Top Gainers and Top Losers.
        """

        logger.info(
            "Building market report..."
        )

        gainers = self.fetch_top_gainers()

        losers = self.fetch_top_losers()

        report = pd.concat(
            [
                gainers,
                losers,
            ],
            ignore_index=True,
        )

        report = report.sort_values(
            by=[
                "Category",
                "1 Day Change %",
            ],
            ascending=[
                True,
                False,
            ],
        )

        report.reset_index(
            drop=True,
            inplace=True,
        )

        logger.info(
            "Market report generated successfully (%d rows).",
            len(report),
        )

        return report

    ###########################################################################

    def get_symbols(self) -> List[str]:
        """
        Returns the symbol list from the report.

        Useful for:
        - OHLC enrichment
        - News collection
        - AI processing
        """

        report = self.fetch_market_report()

        return (
            report["Symbol"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

    ###########################################################################

    def refresh(self) -> None:
        """
        Refresh timestamp and session state.
        """

        self.timestamp = datetime.now()

        self.cookies_initialized = False

        logger.info(
            "NSE session refreshed."
        )

    ###########################################################################

    def health_check(self) -> Dict[str, Any]:
        """
        Return NSE service health information.
        """

        return {

            "component":
                "NSEData",

            "status":
                "ready",

            "session_initialized":
                self.cookies_initialized,

            "timestamp":
                self.timestamp.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

        }
