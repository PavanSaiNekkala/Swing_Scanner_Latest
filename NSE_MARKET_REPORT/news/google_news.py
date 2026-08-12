"""
==============================================================================
File        : news/google_news.py
Project     : NSE Market Report

Description
-----------
Downloads news from Google News RSS for NSE stocks.

Responsibilities
----------------
✓ Google News RSS search
✓ In-memory cache
✓ Thread-safe design
✓ Retry support
✓ Rate limiting
✓ XML parsing (Part 3)
✓ Relevance scoring (Part 3)
✓ Parallel downloads (Part 4)

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

import threading
import time

from datetime import datetime
from typing import Dict
from typing import List
from typing import Optional
from typing import Any

import pandas as pd

import requests
from requests import Session
from requests.adapters import HTTPAdapter

from urllib3.util.retry import Retry

from config.logging_config import logger

###############################################################################
# CONFIGURATION
###############################################################################

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
)

DEFAULT_TIMEOUT = 20

DEFAULT_RETRIES = 3

DEFAULT_BACKOFF = 2

REQUEST_DELAY = 0.50

MAX_WORKERS = 5

MAX_ARTICLES = 5

LANGUAGE = "en-IN"

COUNTRY = "IN"

###############################################################################
# REQUEST HEADERS
###############################################################################

DEFAULT_HEADERS = {

    "User-Agent":

        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/138.0 Safari/537.36"
        ),

    "Accept":

        "application/rss+xml, application/xml, text/xml",

    "Connection":

        "keep-alive",

}

###############################################################################
# OUTPUT SCHEMA
###############################################################################

OUTPUT_COLUMNS = [

    "Symbol",

    "Top Headline",

    "Headline Link",

    "Published",

    "Recent News",

]

###############################################################################
# CUSTOM EXCEPTIONS
###############################################################################


class GoogleNewsError(Exception):
    """Base Google News exception."""


class GoogleNewsConnectionError(GoogleNewsError):
    """Raised when Google News cannot be reached."""


class GoogleNewsParsingError(GoogleNewsError):
    """Raised when RSS parsing fails."""


###############################################################################
# CACHE
###############################################################################


class NewsCache:
    """
    Thread-safe in-memory cache.
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


class GoogleNews:
    """
    Google News RSS client.

    Public Methods
    --------------
    fetch(symbol)

    fetch_many(symbols)

    clear_cache()
    """

    ###########################################################################

    def __init__(self):

        logger.info(
            "Initializing GoogleNews..."
        )

        self.timestamp = datetime.now()

        self.cache = NewsCache()

        self.session = self._create_session()

        logger.info(
            "GoogleNews initialized."
        )

    ###########################################################################
    # SESSION
    ###########################################################################

    @staticmethod
    def _create_session() -> Session:
        """
        Create a persistent HTTP session
        with retry support.
        """

        session = requests.Session()

        retry = Retry(

            total=DEFAULT_RETRIES,

            connect=DEFAULT_RETRIES,

            read=DEFAULT_RETRIES,

            backoff_factor=1.5,

            status_forcelist=[

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

        adapter = HTTPAdapter(

            max_retries=retry

        )

        session.mount(

            "https://",

            adapter,

        )

        session.mount(

            "http://",

            adapter,

        )

        session.headers.update(

            DEFAULT_HEADERS

        )

        return session

    ###########################################################################

    def clear_cache(
        self,
    ) -> None:
        """
        Clear in-memory cache.
        """

        self.cache.clear()

        logger.info(
            "Google News cache cleared."
        )

###############################################################################
# HTTP REQUEST LAYER
###############################################################################

    def _request(
        self,
        symbol: str,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> str:
        """
        Download Google News RSS XML for a symbol.

        Features
        --------
        ✓ Cache
        ✓ Retry
        ✓ Rate limiting
        ✓ XML validation

        Returns
        -------
        Raw XML string
        """

        symbol = symbol.strip().upper()

        cached = self.cache.get(symbol)

        if cached is not None:

            logger.debug("Google News cache hit : %s", symbol)

            return cached["xml"]

        params = {

            "q": f"{symbol} NSE OR {symbol} stock",

            "hl": LANGUAGE,

            "gl": COUNTRY,

            "ceid": f"{COUNTRY}:{LANGUAGE}"

        }

        logger.info("Downloading Google News RSS : %s", symbol)

        for attempt in range(1, DEFAULT_RETRIES + 1):

            try:

                time.sleep(REQUEST_DELAY)

                response = self.session.get(

                    GOOGLE_NEWS_RSS,

                    params=params,

                    timeout=timeout,

                )

                response.raise_for_status()

                xml = response.text

                if not xml:

                    raise GoogleNewsParsingError(

                        "Empty RSS response."

                    )

                if "<rss" not in xml.lower():

                    raise GoogleNewsParsingError(

                        "Invalid RSS document."

                    )

                self.cache.set(

                    symbol,

                    {

                        "xml": xml,

                        "timestamp": datetime.now(),

                    }

                )

                logger.info(

                    "RSS downloaded : %s",

                    symbol,

                )

                return xml

            except requests.Timeout:

                logger.warning(

                    "Timeout (%d/%d) : %s",

                    attempt,

                    DEFAULT_RETRIES,

                    symbol,

                )

            except requests.ConnectionError:

                logger.warning(

                    "Connection Error (%d/%d) : %s",

                    attempt,

                    DEFAULT_RETRIES,

                    symbol,

                )

            except Exception as ex:

                logger.exception(ex)

            if attempt < DEFAULT_RETRIES:

                time.sleep(

                    DEFAULT_BACKOFF ** attempt

                )

        raise GoogleNewsConnectionError(

            f"Unable to download news for {symbol}"

        )

###############################################################################
# XML VALIDATION
###############################################################################

    @staticmethod
    def _validate_xml(
        xml: str,
    ) -> None:
        """
        Validate RSS XML.
        """

        if not xml:

            raise GoogleNewsParsingError(

                "RSS document is empty."

            )

        if "<rss" not in xml.lower():

            raise GoogleNewsParsingError(

                "Invalid RSS XML."

            )

        if "<channel>" not in xml.lower():

            raise GoogleNewsParsingError(

                "Missing RSS channel."

            )

###############################################################################
# DOWNLOAD RSS
###############################################################################

    def _download_feed(
        self,
        symbol: str,
    ) -> str:
        """
        Download and validate RSS feed.
        """

        xml = self._request(symbol)

        self._validate_xml(xml)

        logger.debug(

            "RSS validated : %s",

            symbol,

        )

        return xml

###############################################################################
# XML PARSING
###############################################################################

    def _parse_feed(
        self,
        xml: str,
        symbol: str,
    ) -> List[Dict[str, str]]:
        """
        Parse Google News RSS feed.

        Parameters
        ----------
        xml : str
            RSS XML document.

        symbol : str
            NSE Symbol.

        Returns
        -------
        List[Dict]
        """

        import xml.etree.ElementTree as ET

        try:

            root = ET.fromstring(xml)

        except Exception as ex:

            logger.exception(ex)

            raise GoogleNewsParsingError(
                "Unable to parse RSS XML."
            )

        articles = []

        channel = root.find("channel")

        if channel is None:

            raise GoogleNewsParsingError(
                "RSS channel missing."
            )

        for item in channel.findall("item"):

            articles.append({

                "Symbol": symbol,

                "Headline":

                    item.findtext("title", default="").strip(),

                "Link":

                    item.findtext("link", default="").strip(),

                "Published":

                    item.findtext("pubDate", default="").strip(),

                "Source":

                    item.findtext("source", default="Google News").strip()

            })

        logger.info(

            "%d articles parsed for %s",

            len(articles),

            symbol,

        )

        return articles

###############################################################################
# DEDUPLICATION
###############################################################################

    @staticmethod
    def _deduplicate(
        articles: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Remove duplicate headlines.
        """

        seen = set()

        cleaned = []

        for article in articles:

            headline = article["Headline"].lower()

            if headline not in seen:

                seen.add(headline)

                cleaned.append(article)

        return cleaned

###############################################################################
# RELEVANCE SCORING
###############################################################################

    @staticmethod
    def _score_article(
        article: Dict[str, str],
        symbol: str,
    ) -> int:
        """
        Calculate relevance score.

        Higher score = more relevant.
        """

        score = 0

        headline = article["Headline"].lower()

        symbol = symbol.lower()

        if symbol in headline:

            score += 20

        important_words = [

            "results",

            "earnings",

            "profit",

            "loss",

            "order",

            "contract",

            "dividend",

            "board",

            "acquisition",

            "merger",

            "buyback",

            "share",

            "stock",

            "nse",

            "bse",

        ]

        for word in important_words:

            if word in headline:

                score += 5

        return score

###############################################################################
# SORT NEWS
###############################################################################

    def _rank_articles(
        self,
        articles: List[Dict[str, str]],
        symbol: str,
    ) -> List[Dict[str, str]]:
        """
        Sort articles by relevance.
        """

        articles.sort(

            key=lambda article:

                self._score_article(
                    article,
                    symbol,
                ),

            reverse=True,

        )

        return articles

###############################################################################
# BUILD NEWS OBJECT
###############################################################################

    def _prepare_news(
        self,
        articles: List[Dict[str, str]],
    ) -> Dict[str, object]:
        """
        Convert article list into report format.
        """

        if not articles:

            return {

                "Symbol": None,

                "Top Headline": None,

                "Headline Link": None,

                "Published": None,

                "Recent News": []

            }

        top = articles[0]

        recent = [

            item["Headline"]

            for item in articles[:MAX_ARTICLES]

        ]

        return {

            "Symbol":

                top["Symbol"],

            "Top Headline":

                top["Headline"],

            "Headline Link":

                top["Link"],

            "Published":

                top["Published"],

            "Recent News":

                recent,

        }

###############################################################################
# COMPLETE PARSER
###############################################################################

    def _process_feed(
        self,
        xml: str,
        symbol: str,
    ) -> Dict[str, object]:
        """
        Complete RSS processing pipeline.
        """

        articles = self._parse_feed(

            xml,

            symbol,

        )

        articles = self._deduplicate(

            articles

        )

        articles = self._rank_articles(

            articles,

            symbol,

        )

        return self._prepare_news(

            articles

        )

###############################################################################
# PUBLIC API
###############################################################################

    def fetch(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Dict[str, object]:
        """
        Fetch Google News for a single stock.

        Parameters
        ----------
        symbol : str
            NSE trading symbol.

        company : str | None
            Company name for better search relevance.

        Returns
        -------
        dict
        """

        symbol = symbol.strip().upper()

        logger.info("Fetching Google News : %s", symbol)

        search_term = company if company else symbol

        xml = self._download_feed(search_term)

        result = self._process_feed(xml, symbol)

        return result

###############################################################################

    def _fetch_worker(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        """
        Thread worker.
        """

        try:

            return self.fetch(

                symbol,

                company,

            )

        except Exception as ex:

            logger.exception(

                "Google News failed for %s : %s",

                symbol,

                ex,

            )

            return None

###############################################################################

    def fetch_many(
        self,
        stocks: List[Dict[str, str]],
    ) -> pd.DataFrame:
        """
        Fetch news for multiple stocks.

        Parameters
        ----------
        stocks

        Example
        -------

        [

            {

                "Symbol":"RELIANCE",

                "Company":"Reliance Industries"

            }

        ]
        """

        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import as_completed

        if not stocks:

            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        logger.info(

            "Downloading Google News for %d stocks.",

            len(stocks),

        )

        rows = []

        with ThreadPoolExecutor(

            max_workers=MAX_WORKERS,

        ) as executor:

            futures = {

                executor.submit(

                    self._fetch_worker,

                    stock["Symbol"],

                    stock.get("Company"),

                ): stock

                for stock in stocks

            }

            for future in as_completed(futures):

                result = future.result()

                if result:

                    rows.append(result)

        if not rows:

            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        df = pd.DataFrame(rows)

        df.drop_duplicates(

            subset=["Symbol"],

            inplace=True,

        )

        df.reset_index(

            drop=True,

            inplace=True,

        )

        logger.info(

            "Google News downloaded for %d stocks.",

            len(df),

        )

        return df

###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge news with report dataframe.

        Parameters
        ----------
        report_df : DataFrame

        Returns
        -------
        DataFrame
        """

        if report_df.empty:

            return report_df

        stocks = []

        for _, row in report_df.iterrows():

            stocks.append(

                {

                    "Symbol":

                        row["Symbol"],

                    "Company":

                        row.get("Company"),

                }

            )

        news_df = self.fetch_many(

            stocks

        )

        if news_df.empty:

            logger.warning(

                "No Google News available."

            )

            return report_df

        merged = report_df.merge(

            news_df,

            on="Symbol",

            how="left",

        )

        logger.info(

            "Google News merged successfully."

        )

        return merged

###############################################################################

    def refresh(self) -> None:
        """
        Reset cache and timestamp.
        """

        self.timestamp = datetime.now()

        self.clear_cache()

        logger.info(

            "Google News refreshed."

        )

###############################################################################
# TESTING
###############################################################################

if __name__ == "__main__":

    try:

        google = GoogleNews()

        # ---------------------------------------------------------
        # Single Symbol
        # ---------------------------------------------------------

        result = google.fetch(

            symbol="RELIANCE",

            company="Reliance Industries",

        )

        print("\nSingle Symbol\n")

        print(result)

        # ---------------------------------------------------------
        # Multiple Symbols
        # ---------------------------------------------------------

        stocks = [

            {

                "Symbol": "RELIANCE",

                "Company": "Reliance Industries",

            },

            {

                "Symbol": "TCS",

                "Company": "Tata Consultancy Services",

            },

            {

                "Symbol": "INFY",

                "Company": "Infosys",

            },

            {

                "Symbol": "SBIN",

                "Company": "State Bank of India",

            },

        ]

        df = google.fetch_many(

            stocks

        )

        print("\nMultiple Stocks\n")

        print(df)

    except Exception as ex:

        logger.exception(ex)