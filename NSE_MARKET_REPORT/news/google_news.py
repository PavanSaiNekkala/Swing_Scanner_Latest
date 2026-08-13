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

from datetime import timedelta

from config.logging_config import logger

from email.utils import parsedate_to_datetime

from config.timezone import (
    IST,
    now_ist,
)

from config.config import (
    MAX_WORKERS,
    NEWS_LOOKBACK_DAYS,
)


###############################################################################
# CONFIGURATION
###############################################################################

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
)

DEFAULT_TIMEOUT = 20

DEFAULT_RETRIES = 3

DEFAULT_BACKOFF = 2

REQUEST_DELAY = 0.75

MAX_BACKOFF_SECONDS = 120

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

    def __init__(
        self,
    ):

        logger.info(
            "Initializing GoogleNews..."
        )

        self.timestamp = now_ist()

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

            status=0,

            backoff_factor=1.5,

            status_forcelist=[],

            allowed_methods=[

                "GET",

            ],

            respect_retry_after_header=True,

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
        ✓ Global rate limiting
        ✓ Retry
        ✓ 429/503-aware backoff
        ✓ XML validation

        Parameters
        ----------
        symbol : str
            Search symbol.

        timeout : int
            HTTP timeout in seconds.

        Returns
        -------
        str
            Raw RSS XML.
        """

        symbol = symbol.strip().upper()

        cached = self.cache.get(
            symbol
        )

        if cached is not None:

            logger.debug(
                "Google News cache hit : %s",
                symbol,
            )

            return cached["xml"]

        #######################################################################
        # SEARCH PARAMETERS
        #######################################################################

        params = {
            "q": (
                f"({symbol} NSE OR {symbol} stock) "
                "when:15d"
            ),
            "hl": LANGUAGE,
            "gl": COUNTRY,
            "ceid": f"{COUNTRY}:{LANGUAGE}",
        }

        #######################################################################
        # RETRIES
        #######################################################################

        for attempt in range(
            1,
            DEFAULT_RETRIES + 1,
        ):

            try:

                time.sleep(
                    REQUEST_DELAY
                )

                response = self.session.get(
                    GOOGLE_NEWS_RSS,
                    params=params,
                    timeout=timeout,
                )

                status_code = (
                    response.status_code
                )

                if status_code in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):

                    wait_seconds = min(
                        DEFAULT_BACKOFF ** attempt,
                        MAX_BACKOFF_SECONDS,
                    )

                    logger.warning(
                        "Google News HTTP %s | "
                        "symbol=%s | attempt=%d/%d | "
                        "sleep=%.1fs",
                        status_code,
                        symbol,
                        attempt,
                        DEFAULT_RETRIES,
                        wait_seconds,
                    )

                    if attempt < DEFAULT_RETRIES:

                        time.sleep(
                            wait_seconds
                        )

                        continue

                    break

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
                        "timestamp": now_ist(),
                    },
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

            except GoogleNewsParsingError:

                raise

            except requests.HTTPError as ex:

                logger.warning(
                    "HTTP error (%d/%d) : %s | %s",
                    attempt,
                    DEFAULT_RETRIES,
                    symbol,
                    ex,
                )

            except Exception as ex:

                logger.exception(
                    "Unexpected Google News error | "
                    "symbol=%s | attempt=%d/%d",
                    symbol,
                    attempt,
                    DEFAULT_RETRIES,
                )

            if attempt < DEFAULT_RETRIES:

                wait_seconds = min(
                    DEFAULT_BACKOFF ** attempt,
                    MAX_BACKOFF_SECONDS,
                )

                time.sleep(
                    wait_seconds
                )

        raise GoogleNewsConnectionError(
            f"Unable to download news for {symbol}"
        )



    @staticmethod
    def _filter_recent_articles(
        articles: List[Dict[str, Any]],
        days: int,
    ) -> List[Dict[str, Any]]:
        """
        Keep only articles published within the last N days.
        """

        if not articles:
            return []

        cutoff = (
            now_ist()
            - timedelta(days=days)
        )

        return [
            article
            for article in articles
            if (
                article.get("Published") is not None
                and article["Published"] >= cutoff
            )
        ]

    

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

        xml = self._request(
            symbol
        )



    @staticmethod
    def _parse_published_date(
        value: str,
    ) -> Optional[datetime]:
        """
        Parse RSS publication date and normalize it to IST.
        """

        if not value:
            return None

        try:

            published = parsedate_to_datetime(
                value
            )

            if published.tzinfo is None:

                published = published.replace(
                    tzinfo=IST
                )

            else:

                published = published.astimezone(
                    IST
                )

            return published

        except (
            TypeError,
            ValueError,
            OverflowError,
        ):

            logger.warning(
                "Unable to parse publication date: %s",
                value,
            )

            return None

        

###############################################################################
# XML PARSING
###############################################################################

    def _parse_feed(
        self,
        xml: str,
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """
        Parse Google News RSS feed and retain only articles
        published within the last 15 days.
        """

        import xml.etree.ElementTree as ET

        try:

            root = ET.fromstring(xml)

        except Exception as ex:

            logger.exception(ex)

            raise GoogleNewsParsingError(
                "Unable to parse RSS XML."
            )

        articles: List[Dict[str, Any]] = []

        channel = root.find("channel")

        if channel is None:

            raise GoogleNewsParsingError(
                "RSS channel missing."
            )

        raw_count = 0

        for item in channel.findall("item"):

            raw_count += 1

            published = self._parse_published_date(
                item.findtext(
                    "pubDate",
                    default="",
                ).strip()
            )

            # Skip articles where publication time
            # cannot be verified.
            if published is None:
                continue

            article = {
                "Symbol": symbol,

                "Headline":
                    item.findtext(
                        "title",
                        default="",
                    ).strip(),

                "Link":
                    item.findtext(
                        "link",
                        default="",
                    ).strip(),

                "Published":
                    published,

                "Source":
                    item.findtext(
                        "source",
                        default="Google News",
                    ).strip(),
            }

            articles.append(
                article
            )

        #######################################################################
        # 15-DAY FILTER
        #######################################################################

        recent_articles = self._filter_recent_articles(
            articles,
            days=NEWS_LOOKBACK_DAYS,
        )

        logger.info(
            "Google News RSS : %s | "
            "Raw=%d | Last%dDays=%d",
            symbol,
            raw_count,
            NEWS_LOOKBACK_DAYS,
            len(recent_articles),
        )

        return recent_articles

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
# PUBLIC FETCH
###############################################################################

    def fetch(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Dict[str, object]:
        """
        Fetch Google News for a single stock.
        """

        symbol = symbol.strip().upper()

        logger.info(
            "Fetching Google News : %s",
            symbol,
        )

        #######################################################################
        # SEARCH TERM
        #######################################################################

        search_term = (
            company
            if company
            else symbol
        )

        #######################################################################
        # DOWNLOAD
        #######################################################################

        xml = self._download_feed(
            search_term,
        )

        #######################################################################
        # PROCESS
        #######################################################################

        result = self._process_feed(
            xml,
            symbol,
        )

        return result

###############################################################################
# FETCH WORKER
###############################################################################

    def _fetch_worker(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        """
        Thread worker for Google News retrieval.
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
# PUBLIC API
###############################################################################

    def fetch_many(
        self,
        stocks: List[Dict[str, str]],
    ) -> pd.DataFrame:
        """
        Fetch news for multiple stocks.
        """

        from concurrent.futures import (
            ThreadPoolExecutor,
            as_completed,
        )

        if not stocks:

            return pd.DataFrame(
                columns=OUTPUT_COLUMNS
            )

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
                ): stock["Symbol"]

                for stock in stocks

            }

            for future in as_completed(
                futures
            ):

                symbol = futures[future]

                try:

                    result = future.result()

                    if result:

                        rows.append(
                            result
                        )

                except Exception as ex:

                    logger.exception(
                        "Google News failed for %s : %s",
                        symbol,
                        ex,
                    )

        if not rows:

            return pd.DataFrame(
                columns=OUTPUT_COLUMNS
            )

        df = pd.DataFrame(
            rows
        )

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

        self.timestamp = now_ist()

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