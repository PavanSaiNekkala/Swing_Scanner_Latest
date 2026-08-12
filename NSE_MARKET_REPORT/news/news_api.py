"""
==============================================================================
File        : news/news_api.py
Project     : NSE Market Report

Description
-----------
Downloads financial news using NewsAPI and returns structured news
objects for NSE stocks.

Responsibilities
----------------
✓ NewsAPI Client
✓ Persistent HTTP Session
✓ Retry Support
✓ Thread-safe Cache
✓ TTL Cache
✓ Rate Limiter
✓ Structured Logging
✓ JSON Parsing (Part 3)
✓ Parallel Downloads (Part 4)

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
import requests

from requests import Session
from requests.adapters import HTTPAdapter

from urllib3.util.retry import Retry

from config.config import (
    NEWS_API_KEY,
    DEFAULT_TIMEOUT,
    DEFAULT_RETRIES,
    DEFAULT_BACKOFF,
    REQUEST_DELAY,
    MAX_WORKERS,
    CACHE_TTL_MINUTES,
    MAX_NEWS_PER_STOCK,
    NEWS_LANGUAGE,
    NEWS_LOOKBACK_DAYS,
)

from config.logging_config import logger

###############################################################################
# API CONFIGURATION
###############################################################################

NEWS_API_ENDPOINT = "https://newsapi.org/v2/everything"

###############################################################################
# REQUEST HEADERS
###############################################################################

DEFAULT_HEADERS = {

    "User-Agent": (

        "Mozilla/5.0 "

        "(Windows NT 10.0; Win64; x64) "

        "AppleWebKit/537.36 "

        "(KHTML, like Gecko) "

        "Chrome/138.0 Safari/537.36"

    ),

    "Accept": "application/json",

    "Connection": "keep-alive",

}

###############################################################################
# OUTPUT SCHEMA
###############################################################################

OUTPUT_COLUMNS = [

    "Symbol",

    "Top Headline",

    "Headline Link",

    "Description",

    "Source",

    "Published",

    "Recent News",

]

###############################################################################
# EXCEPTIONS
###############################################################################


class NewsAPIError(Exception):
    """Base exception."""


class NewsAPIConnectionError(NewsAPIError):
    """Raised when API cannot be reached."""


class NewsAPIParsingError(NewsAPIError):
    """Raised when response parsing fails."""


###############################################################################
# CACHE
###############################################################################


class NewsCache:
    """
    Thread-safe in-memory cache with TTL.
    """

    def __init__(self):

        self._cache: Dict[str, Dict[str, Any]] = {}

        self._lock = threading.Lock()

    ###########################################################################

    def get(
        self,
        key: str,
    ) -> Optional[Dict[str, Any]]:

        with self._lock:

            item = self._cache.get(key)

            if item is None:

                return None

            age = (

                datetime.now()

                - item["timestamp"]

            ).total_seconds()

            if age > CACHE_TTL_MINUTES * 60:

                del self._cache[key]

                return None

            return item["payload"]

    ###########################################################################

    def set(
        self,
        key: str,
        payload: Dict[str, Any],
    ) -> None:

        with self._lock:

            self._cache[key] = {

                "timestamp": datetime.now(),

                "payload": payload,

            }

    ###########################################################################

    def clear(self) -> None:

        with self._lock:

            self._cache.clear()


###############################################################################
# MAIN CLASS
###############################################################################


class NewsAPIClient:
    """
    NewsAPI client.

    Public Methods
    --------------
    fetch()

    fetch_many()

    merge()

    clear_cache()
    """

    ###########################################################################

    def __init__(self):

        logger.info("Initializing NewsAPI Client...")

        if not NEWS_API_KEY:

            raise NewsAPIError(

                "NEWS_API_KEY not configured."

            )

        self.cache = NewsCache()

        self.timestamp = datetime.now()

        self.session = self._create_session()

        logger.info(

            "NewsAPI Client initialized."

        )

    ###########################################################################

    @staticmethod
    def _create_session() -> Session:
        """
        Create persistent HTTP session.
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

            allowed_methods=["GET"],

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

    def clear_cache(self) -> None:
        """
        Clear cached API responses.
        """

        self.cache.clear()

        logger.info(

            "NewsAPI cache cleared."

        )

###############################################################################
# REQUEST LAYER
###############################################################################

    def _build_query(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> str:
        """
        Build NewsAPI search query.
        """

        symbol = symbol.strip().upper()

        if company:

            return f'"{company}" OR {symbol}'

        return symbol

    ###########################################################################

    def _request(
        self,
        symbol: str,
        company: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Dict[str, Any]:
        """
        Download raw JSON from NewsAPI.
        """

        cache_key = symbol.upper()

        cached = self.cache.get(cache_key)

        if cached is not None:

            logger.debug("[NEWSAPI] Cache hit : %s", symbol)

            return cached

        logger.info("[NEWSAPI] Downloading : %s", symbol)

        query = self._build_query(

            symbol,

            company,

        )

        params = {

            "q": query,

            "language": NEWS_LANGUAGE,

            "sortBy": "publishedAt",

            "pageSize": MAX_NEWS_PER_STOCK,

            "apiKey": NEWS_API_KEY,

        }

        for attempt in range(1, DEFAULT_RETRIES + 1):

            try:

                time.sleep(REQUEST_DELAY)

                response = self.session.get(

                    NEWS_API_ENDPOINT,

                    params=params,

                    timeout=timeout,

                )

                response.raise_for_status()

                payload = response.json()

                self._validate_response(payload)

                self.cache.set(

                    cache_key,

                    payload,

                )

                logger.info(

                    "[NEWSAPI] Download completed : %s",

                    symbol,

                )

                return payload

            except requests.Timeout:

                logger.warning(

                    "[NEWSAPI] Timeout (%d/%d) : %s",

                    attempt,

                    DEFAULT_RETRIES,

                    symbol,

                )

            except requests.ConnectionError:

                logger.warning(

                    "[NEWSAPI] Connection Error (%d/%d) : %s",

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

        raise NewsAPIConnectionError(

            f"Unable to download news for {symbol}"

        )

###############################################################################
# RESPONSE VALIDATION
###############################################################################

    @staticmethod
    def _validate_response(
        payload: Dict[str, Any],
    ) -> None:
        """
        Validate NewsAPI response.
        """

        if not isinstance(payload, dict):

            raise NewsAPIParsingError(

                "Invalid JSON response."

            )

        status = payload.get("status")

        if status != "ok":

            raise NewsAPIParsingError(

                payload.get(

                    "message",

                    "NewsAPI request failed."

                )

            )

        if "articles" not in payload:

            raise NewsAPIParsingError(

                "Missing articles."

            )

###############################################################################
# SAFE VALUE
###############################################################################

    @staticmethod
    def _safe_get(
        data: Dict[str, Any],
        *keys: str,
        default: Any = None,
    ) -> Any:
        """
        Safely retrieve nested values.
        """

        value: Any = data

        for key in keys:

            if not isinstance(value, dict):

                return default

            value = value.get(key)

            if value is None:

                return default

        return value

###############################################################################
# DOWNLOAD NEWS
###############################################################################

    def _download_news(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Download and validate NewsAPI payload.
        """

        payload = self._request(

            symbol,

            company,

        )

        self._validate_response(

            payload

        )

        logger.debug(

            "[NEWSAPI] Payload validated : %s",

            symbol,

        )

        return payload


###############################################################################
# JSON PARSING
###############################################################################

    def _parse_articles(
        self,
        payload: Dict[str, Any],
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """
        Parse NewsAPI JSON into a normalized list of articles.
        """

        articles = []

        for article in payload.get("articles", []):

            articles.append({

                "Symbol": symbol,

                "Headline":

                    article.get("title", "").strip(),

                "Description":

                    article.get("description", "").strip(),

                "Content":

                    article.get("content", "").strip(),

                "Headline Link":

                    article.get("url", "").strip(),

                "Image":

                    article.get("urlToImage", "").strip(),

                "Published":

                    article.get("publishedAt", "").strip(),

                "Source":

                    self._safe_get(

                        article,

                        "source",

                        "name",

                        default="Unknown",

                    ),

            })

        logger.info(

            "[NEWSAPI] Parsed %d articles for %s",

            len(articles),

            symbol,

        )

        return articles

###############################################################################
# REMOVE DUPLICATES
###############################################################################

    @staticmethod
    def _deduplicate(
        articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate news articles.
        """

        seen = set()

        cleaned = []

        for article in articles:

            key = (

                article["Headline"].lower(),

                article["Headline Link"]

            )

            if key not in seen:

                seen.add(key)

                cleaned.append(article)

        return cleaned

###############################################################################
# RELEVANCE SCORING
###############################################################################

    @staticmethod
    def _score_article(
        article: Dict[str, Any],
        symbol: str,
    ) -> int:
        """
        Score article relevance.
        """

        score = 0

        symbol = symbol.lower()

        headline = article["Headline"].lower()

        description = article["Description"].lower()

        if symbol in headline:

            score += 30

        if symbol in description:

            score += 15

        KEYWORDS = {

            "earnings": 20,

            "results": 20,

            "profit": 15,

            "loss": 15,

            "dividend": 15,

            "bonus": 15,

            "split": 12,

            "buyback": 12,

            "merger": 12,

            "acquisition": 12,

            "contract": 10,

            "order": 10,

            "guidance": 10,

            "share": 8,

            "stock": 8,

            "nse": 6,

            "bse": 6,

        }

        text = f"{headline} {description}"

        for word, weight in KEYWORDS.items():

            if word in text:

                score += weight

        return score

###############################################################################
# SORT ARTICLES
###############################################################################

    def _rank_articles(
        self,
        articles: List[Dict[str, Any]],
        symbol: str,
    ) -> List[Dict[str, Any]]:
        """
        Sort articles by relevance score.
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
# BUILD FINAL NEWS OBJECT
###############################################################################

    def _prepare_news(
        self,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Convert article list into report format.
        """

        if not articles:

            return {

                "Symbol": None,

                "Top Headline": None,

                "Headline Link": None,

                "Description": None,

                "Source": None,

                "Published": None,

                "Recent News": [],

            }

        top = articles[0]

        recent_news = [

            article["Headline"]

            for article in articles[:MAX_NEWS_PER_STOCK]

        ]

        return {

            "Symbol":

                top["Symbol"],

            "Top Headline":

                top["Headline"],

            "Headline Link":

                top["Headline Link"],

            "Description":

                top["Description"],

            "Source":

                top["Source"],

            "Published":

                top["Published"],

            "Recent News":

                recent_news,

        }

###############################################################################
# COMPLETE PIPELINE
###############################################################################

    def _process_news(
        self,
        payload: Dict[str, Any],
        symbol: str,
    ) -> Dict[str, Any]:
        """
        Complete NewsAPI processing pipeline.
        """

        articles = self._parse_articles(

            payload,

            symbol,

        )

        articles = self._deduplicate(

            articles,

        )

        articles = self._rank_articles(

            articles,

            symbol,

        )

        return self._prepare_news(

            articles,

        )
    

###############################################################################
# PUBLIC API
###############################################################################

    def fetch(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch news for a single stock.

        Parameters
        ----------
        symbol : str
            NSE stock symbol.

        company : Optional[str]
            Company name.

        Returns
        -------
        dict
        """

        symbol = symbol.strip().upper()

        logger.info(
            "[NEWSAPI] Fetching %s",
            symbol,
        )

        payload = self._download_news(
            symbol,
            company,
        )

        return self._process_news(
            payload,
            symbol,
        )

###############################################################################

    def _fetch_worker(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Worker used by ThreadPoolExecutor.
        """

        try:

            return self.fetch(
                symbol,
                company,
            )

        except Exception as ex:

            logger.exception(
                "[NEWSAPI] %s : %s",
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
                "Symbol": "RELIANCE",
                "Company": "Reliance Industries"
            }
        ]
        """

        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import as_completed

        if not stocks:

            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        logger.info(

            "[NEWSAPI] Downloading news for %d stocks.",

            len(stocks),

        )

        rows = []

        with ThreadPoolExecutor(
            max_workers=MAX_WORKERS
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

            "[NEWSAPI] Completed for %d stocks.",

            len(df),

        )

        return df

###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge NewsAPI results with report dataframe.
        """

        if report_df.empty:

            logger.warning(
                "[NEWSAPI] Empty report."
            )

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
                "[NEWSAPI] No news available."
            )

            return report_df

        merged = report_df.merge(

            news_df,

            on="Symbol",

            how="left",

            suffixes=("", "_NewsAPI"),

        )

        logger.info(
            "[NEWSAPI] Merge completed."
        )

        return merged

###############################################################################

    def refresh(self) -> None:
        """
        Refresh cache and timestamp.
        """

        self.timestamp = datetime.now()

        self.clear_cache()

        logger.info(
            "[NEWSAPI] Cache refreshed."
        )