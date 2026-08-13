"""
==============================================================================
File        : news/news_manager.py
Project     : NSE Market Report

Description
-----------
Central News Management Service.

Responsibilities
----------------
✓ Load configured news providers
✓ Fetch news from multiple providers
✓ Merge provider results
✓ Remove duplicates
✓ Rank articles
✓ Produce final news dataset
✓ Merge with market report

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

from pathlib import Path

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

from datetime import datetime
<<<<<<< HEAD
from datetime import timedelta
<<<<<<< HEAD
from datetime import timezone
=======
>>>>>>> 263a17d ("13/08/2026")
=======
>>>>>>> 59d6ab5 ("13/08/2026")

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd

from config.config import (
    MAX_WORKERS,
    ENABLED_NEWS_PROVIDERS,
    NEWS_LOOKBACK_DAYS,
    MARKETAUX_API_KEY,
)

<<<<<<< HEAD
from config.timezone import (
    IST,
    now_ist,
)

=======
>>>>>>> 263a17d ("13/08/2026")
from config.logging_config import logger

from news.google_news import GoogleNews

from news.marketaux_news import MarketauxNews

from news.news_api import NewsAPIClient

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
# NEWS MANAGER
###############################################################################


class NewsManager:
    """
    Central news orchestration service.

    Workflow
    --------

        Google News
              │
              ▼

        NewsAPI

              │

              ▼

      Merge Providers

              │

              ▼

      Remove Duplicates

              │

              ▼

      Rank Articles

              │

              ▼

      Final News Dataset

    Public Methods
    --------------

    fetch()

    fetch_many()

    merge()

    refresh()
    """

    ###########################################################################

    def __init__(self):

        logger.info(
            "[NEWS MANAGER] Initializing..."
        )

<<<<<<< HEAD
        self.timestamp = now_ist()
=======
        self.timestamp = datetime.now()
>>>>>>> 263a17d ("13/08/2026")

        #######################################################################
        # NORMAL MARKET-REPORT PROVIDERS
        #######################################################################

        self.providers = self._load_providers()

        #######################################################################
        # FULL NEWS UNIVERSE PROVIDER
        #######################################################################

        self.universe_provider = None

        try:

            self.universe_provider = MarketauxNews(
                MARKETAUX_API_KEY
            )

            logger.info(
                "[NEWS MANAGER] "
                "Marketaux universe provider enabled."
            )

        except Exception as ex:

            logger.exception(
                "[NEWS MANAGER] "
                "Marketaux initialization failed: %s",
                ex,
            )

            self.universe_provider = None

        logger.info(
            "[NEWS MANAGER] %d provider(s) loaded.",
            len(self.providers),
        )

    ###########################################################################

    @staticmethod
    def _load_providers() -> List[Any]:
        """
        Load configured news providers.
        """

        providers = []

        if "google" in ENABLED_NEWS_PROVIDERS:

            try:

                providers.append(

                    GoogleNews()

                )

                logger.info(

                    "[NEWS MANAGER] Google News enabled."

                )

            except Exception as ex:

                logger.exception(ex)

        if "newsapi" in ENABLED_NEWS_PROVIDERS:

            try:

                providers.append(

                    NewsAPIClient()

                )

                logger.info(

                    "[NEWS MANAGER] NewsAPI enabled."

                )

            except Exception as ex:

                logger.exception(ex)

        if not providers:

            logger.warning(

                "[NEWS MANAGER] No news providers available."

            )

        return providers

    ###########################################################################

    @property
    def provider_count(self) -> int:
        """
        Number of active providers.
        """

        return len(self.providers)

    ###########################################################################

    def refresh(self) -> None:
        """
        Refresh all providers.
        """

<<<<<<< HEAD
        self.timestamp = now_ist()
=======
        self.timestamp = datetime.now()
>>>>>>> 263a17d ("13/08/2026")

        for provider in self.providers:

            try:

                provider.refresh()

            except Exception as ex:

                logger.exception(ex)

        logger.info(

            "[NEWS MANAGER] Providers refreshed."

        )

    ###########################################################################

    def list_providers(self) -> List[str]:
        """
        Return provider names.
        """

        return [

            provider.__class__.__name__

            for provider in self.providers

        ]

###############################################################################
# PROVIDER FETCH
###############################################################################

    def _fetch_provider(
        self,
        provider: Any,
        symbol: str,
        company: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch news from a single provider.
        """

        try:

            logger.info(

                "[NEWS MANAGER] %s -> %s",

                provider.__class__.__name__,

                symbol,

            )

            result = provider.fetch(

                symbol=symbol,

                company=company,

            )

            if result:

                result["Provider"] = provider.__class__.__name__

                return result

        except Exception as ex:

            logger.exception(

                "[NEWS MANAGER] %s failed : %s",

                provider.__class__.__name__,

                ex,

            )

        return None

###############################################################################
# FETCH ALL PROVIDERS
###############################################################################

    def _collect_news(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect news from every enabled provider.
        """

        if not self.providers:

            return []

        results = []

        with ThreadPoolExecutor(

            max_workers=min(

                MAX_WORKERS,

                len(self.providers),

            )

        ) as executor:

            futures = [

                executor.submit(

                    self._fetch_provider,

                    provider,

                    symbol,

                    company,

                )

                for provider in self.providers

            ]

            for future in as_completed(futures):

                result = future.result()

                if result:

                    results.append(result)

        logger.info(

            "[NEWS MANAGER] %d provider(s) returned news for %s",

            len(results),

            symbol,

        )

        return results

###############################################################################
# FETCH MULTIPLE STOCKS
###############################################################################

    def _collect_news_many(
        self,
        stocks: List[Dict[str, str]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect news for multiple stocks.

        Returns
        -------
        {

            "RELIANCE":[...],

            "TCS":[...]

        }
        """

        news_map: Dict[str, List[Dict[str, Any]]] = {}

        if not stocks:

            return news_map

        with ThreadPoolExecutor(

            max_workers=MAX_WORKERS,

        ) as executor:

            futures = {

                executor.submit(

                    self._collect_news,

                    stock["Symbol"],

                    stock.get("Company"),

                ): stock["Symbol"]

                for stock in stocks

            }

            for future in as_completed(futures):

                symbol = futures[future]

                try:

                    news_map[symbol] = future.result()

                except Exception as ex:

                    logger.exception(ex)

                    news_map[symbol] = []

        logger.info(

            "[NEWS MANAGER] News collected for %d stocks.",

            len(news_map),

        )

        return news_map

###############################################################################
# FLATTEN RESULTS
###############################################################################

    @staticmethod
    def _flatten(
        provider_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Convert provider output into a flat article list.
        """

        articles = []

        for provider in provider_results:

            if not provider:

                continue

            recent = provider.get(

                "Recent News",

                [],

            )

            for headline in recent:

                articles.append(

                    {

                        "Symbol":

                            provider.get("Symbol"),

                        "Headline":

                            headline,

                        "Top Headline":

                            provider.get(

                                "Top Headline"

                            ),

                        "Description":

                            provider.get(

                                "Description"

                            ),

                        "Headline Link":

                            provider.get(

                                "Headline Link"

                            ),

                        "Published":

                            provider.get(

                                "Published"

                            ),

                        "Source":

                            provider.get(

                                "Source"

                            ),

                        "Provider":

                            provider.get(

                                "Provider"

                            ),

                    }

                )

        return articles

<<<<<<< HEAD

###############################################################################
# 15 DAYS FILTER
###############################################################################

    @staticmethod
    def _filter_recent_articles(
        articles: List[Dict[str, Any]],
        days: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Keep only articles published within the last N days.

        Publication timestamps are normalized to IST before
        comparison.
        """

        if not articles:
            return []

        cutoff = (
            now_ist()
            - timedelta(days=days)
        )

        filtered: List[Dict[str, Any]] = []

        for article in articles:

            published = article.get(
                "Published"
            )

            if not published:
                continue

            try:

                if isinstance(
                    published,
                    datetime,
                ):

                    published_dt = published

                else:

                    published_text = str(
                        published
                    ).strip()

                    published_dt = datetime.fromisoformat(
                        published_text.replace(
                            "Z",
                            "+00:00",
                        )
                    )

                if published_dt.tzinfo is None:

                    logger.warning(
                        "[NEWS MANAGER] "
                        "Naive publication timestamp "
                        "for article: %s",
                        article.get("Headline"),
                    )

                    published_dt = published_dt.replace(
                        tzinfo=IST
                    )

                else:

                    published_dt = published_dt.astimezone(
                        IST
                    )

                if published_dt >= cutoff:

                    filtered.append(
                        article
                    )

            except (
                ValueError,
                TypeError,
                OverflowError,
            ) as ex:

                logger.warning(
                    "[NEWS MANAGER] "
                    "Unable to parse publication date "
                    "for article '%s': %s",
                    article.get("Headline"),
                    ex,
                )

        return filtered



=======
>>>>>>> 263a17d ("13/08/2026")
###############################################################################
# REMOVE DUPLICATE ARTICLES
###############################################################################

    @staticmethod
    def _deduplicate(
        articles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate articles.

        Duplicate criteria:
        - Same headline (case-insensitive)
        - Same article URL
        """

        seen = set()

        cleaned = []

        for article in articles:

            key = (

<<<<<<< HEAD
                str(
                    article.get("Headline") or ""
                ).strip().lower(),

                str(
                    article.get("Headline Link") or ""
                ).strip(),
=======
                article.get("Headline", "").strip().lower(),

                article.get("Headline Link", "").strip(),
>>>>>>> 263a17d ("13/08/2026")

            )

            if key in seen:
                continue

            seen.add(key)

            cleaned.append(article)

        return cleaned

###############################################################################
# RELEVANCE SCORE
###############################################################################

    @staticmethod
    def _score_article(
        article: Dict[str, Any],
        symbol: str,
    ) -> int:
        """
        Calculate a unified relevance score.
<<<<<<< HEAD

        All text inputs are normalized to strings so that
        missing/None provider fields cannot cause .lower()
        failures.
=======
>>>>>>> 263a17d ("13/08/2026")
        """

        score = 0

<<<<<<< HEAD
        symbol_text = str(
            symbol or ""
        ).strip().lower()

        headline = str(
            article.get("Headline") or ""
        ).strip().lower()

        description = str(
            article.get("Description") or ""
        ).strip().lower()

        provider = str(
            article.get("Provider") or ""
        ).strip()

        if symbol_text and symbol_text in headline:
            score += 40

        if symbol_text and symbol_text in description:
            score += 20

        KEYWORDS = {
=======
        symbol = symbol.lower()

        headline = article.get(
            "Headline",
            "",
        ).lower()

        description = article.get(
            "Description",
            "",
        ).lower()

        provider = article.get(
            "Provider",
            "",
        )

        if symbol in headline:
            score += 40

        if symbol in description:
            score += 20

        KEYWORDS = {

>>>>>>> 263a17d ("13/08/2026")
            "results": 25,
            "earnings": 25,
            "profit": 20,
            "loss": 20,
            "dividend": 18,
            "buyback": 18,
            "bonus": 15,
            "split": 15,
            "merger": 15,
            "acquisition": 15,
            "order": 12,
            "contract": 12,
            "guidance": 10,
            "stock": 8,
            "share": 8,
            "nse": 6,
            "bse": 6,
<<<<<<< HEAD
=======

>>>>>>> 263a17d ("13/08/2026")
        }

        text = f"{headline} {description}"

        for word, weight in KEYWORDS.items():

            if word in text:
<<<<<<< HEAD

=======
>>>>>>> 263a17d ("13/08/2026")
                score += weight

        if provider == "GoogleNews":
            score += 5

        if provider == "NewsAPIClient":
            score += 3

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
# BUILD FINAL NEWS OBJECT
###############################################################################

    def _build_news(
        self,
        symbol: str,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build final news object.
        """

        if not articles:

            return {

                "Symbol": symbol,

                "Top Headline": None,

                "Headline Link": None,

                "Description": None,

                "Source": None,

                "Published": None,

                "Recent News": [],

            }

        top = articles[0]

        recent_news = []

        for article in articles:

            headline = article.get("Headline")

            if headline and headline not in recent_news:

                recent_news.append(headline)

            if len(recent_news) >= 5:
                break

        return {

            "Symbol":

                symbol,

            "Top Headline":

                top.get("Headline"),

            "Headline Link":

                top.get("Headline Link"),

            "Description":

                top.get("Description"),

            "Source":

                top.get("Source"),

            "Published":

                top.get("Published"),

            "Recent News":

                recent_news,

        }

###############################################################################
# COMPLETE PROCESSING PIPELINE
###############################################################################

    def _process_news(
        self,
        symbol: str,
        provider_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Complete processing pipeline.

        Provider Results
              │
              ▼
        Flatten Articles
              │
              ▼
        Remove Duplicates
              │
              ▼
        Rank Articles
              │
              ▼
        Final News Object
        """

        articles = self._flatten(
<<<<<<< HEAD
            provider_results,
        )

        articles = self._filter_recent_articles(
            articles,
            days=NEWS_LOOKBACK_DAYS,
        )

        logger.info(
            "[NEWS MANAGER] %s | "
            "Articles within last %d days: %d",
            symbol,
            NEWS_LOOKBACK_DAYS,
            len(articles),
        )

       
        articles = self._deduplicate(
            articles,
        )

        articles = self._rank_articles(
            articles,
            symbol,
=======

            provider_results,

        )

        articles = self._deduplicate(

            articles,

        )

        articles = self._rank_articles(

            articles,

            symbol,

>>>>>>> 263a17d ("13/08/2026")
        )

        return self._build_news(

            symbol,

            articles,

        )

    

    def load_news_universe(
        self,
        csv_path: Path,
    ) -> List[Dict[str, str]]:
        """
        Load the full news-scanning universe from CSV.
        """

        if not csv_path.exists():

            raise FileNotFoundError(
                f"News universe file not found: {csv_path}"
            )

        df = pd.read_csv(
            csv_path
        )

        symbol_column = next(
            (
                column
                for column in (
                    "Symbol",
                    "SYMBOL",
                    "Ticker",
                    "TICKER",
                    "symbol",
                    "ticker",
                )
                if column in df.columns
            ),
            None,
        )

        if symbol_column is None:

            raise ValueError(
                "News universe CSV must contain "
                "Symbol or Ticker column."
            )

        company_column = next(
            (
                column
                for column in (
                    "Company",
                    "COMPANY",
                    "Company Name",
                    "company",
                    "company_name",
                )
                if column in df.columns
            ),
            None,
        )

        stocks: list[Dict[str, str]] = []

        for _, row in df.iterrows():

            symbol = str(
                row.get(symbol_column, "")
            ).strip().upper()

            if not symbol:
                continue

            if symbol == "NAN":
                continue

            company = ""

            if company_column:

                company = str(
                    row.get(
                        company_column,
                        "",
                    )
                ).strip()

                if company.lower() == "nan":
                    company = ""

            stocks.append(
                {
                    "Symbol": symbol,
                    "Company": company,
                }
            )

        #######################################################################
        # DEDUP SYMBOLS
        #######################################################################

        before_deduplication = len(
            stocks
        )

        unique: Dict[
            str,
            Dict[str, str],
        ] = {}

        for stock in stocks:

            symbol = stock["Symbol"]

            if symbol in unique:

                logger.debug(
                    "[NEWS UNIVERSE] "
                    "Duplicate symbol ignored: %s",
                    symbol,
                )

            unique[
                symbol
            ] = stock

        stocks = list(
            unique.values()
        )

        duplicates_removed = (
            before_deduplication
            - len(stocks)
        )

        logger.info(
            "[NEWS UNIVERSE] "
            "Loaded=%d | Unique=%d | "
            "DuplicatesRemoved=%d | File=%s",
            before_deduplication,
            len(stocks),
            duplicates_removed,
            csv_path,
        )

        return stocks



    def scan_news_universe(
        self,
        csv_path: Path,
    ) -> pd.DataFrame:
        """
        Scan the full CSV universe using Marketaux.

        Google News remains the provider for the normal
        40-stock market report.
        """

        stocks = self.load_news_universe(
            csv_path
        )

        if not stocks:

            logger.warning(
                "[NEWS UNIVERSE] "
                "No valid symbols found."
            )

            return pd.DataFrame()

        if self.universe_provider is None:

            logger.error(
                "[NEWS UNIVERSE] "
                "Marketaux provider unavailable."
            )

            return pd.DataFrame()

        logger.info(
            "[NEWS UNIVERSE] "
            "Starting Marketaux scan for %d symbols.",
            len(stocks),
        )

        rows = (
            self.universe_provider.fetch_many(
                stocks
            )
        )

        if not rows:

            logger.warning(
                "[NEWS UNIVERSE] "
                "Marketaux returned no data."
            )

            return pd.DataFrame()

        news_df = pd.DataFrame(
            rows
        )

        news_df.sort_values(
            by="Symbol",
            inplace=True,
        )

        news_df.reset_index(
            drop=True,
            inplace=True,
        )

        logger.info(
            "[NEWS UNIVERSE] "
            "Completed Marketaux scan | "
            "Symbols=%d",
            len(news_df),
        )

        return news_df
    

###############################################################################
# PUBLIC API
###############################################################################

###############################################################################
# PUBLIC API
###############################################################################

    def fetch(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch and process news for one stock
        using all configured market-report providers.
        """

        symbol = (
            str(symbol)
            .strip()
            .upper()
        )

        if not symbol:
            raise ValueError(
                "Symbol cannot be empty."
            )

        provider_results = (
            self._collect_news(
                symbol,
                company,
            )
        )

        return self._process_news(
            symbol,
            provider_results,
        )

    def fetch_many(
        self,
        stocks: List[Dict[str, str]],
    ) -> pd.DataFrame:
        """
        Fetch and process news for multiple stocks.
        """

        if not stocks:

            return pd.DataFrame(
                columns=OUTPUT_COLUMNS
            )

        news_map = (
            self._collect_news_many(
                stocks
            )
        )

        rows: List[
            Dict[str, Any]
        ] = []

        for stock in stocks:

            symbol = (
                str(
                    stock.get(
                        "Symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            if not symbol:
                continue

            provider_results = (
                news_map.get(
                    symbol,
                    [],
                )
            )

            result = self._process_news(
                symbol,
                provider_results,
            )

            rows.append(
                result
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
            keep="first",
            inplace=True,
        )

        df.sort_values(
            by="Symbol",
            inplace=True,
        )

        df.reset_index(
            drop=True,
            inplace=True,
        )

        logger.info(
            "[NEWS MANAGER] "
            "Completed news processing for %d stocks.",
            len(df),
        )

        return df

###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge processed news into market report dataframe.
        """

        if report_df.empty:

            logger.warning(

                "[NEWS MANAGER] Empty report dataframe."

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

            stocks,

        )

        if news_df.empty:

            logger.warning(

                "[NEWS MANAGER] No news available."

            )

            return report_df

        merged = report_df.merge(

            news_df,

            on="Symbol",

            how="left",

            suffixes=("", "_News"),

        )

        logger.info(

            "[NEWS MANAGER] Report merged successfully."

        )

        return merged


###############################################################################
# CLOSE
###############################################################################

    def close(
        self,
    ) -> None:
        """
        Close all configured news providers.
        """

        for provider in self.providers:

            try:

                close_method = getattr(
                    provider,
                    "close",
                    None,
                )

                if callable(close_method):

                    close_method()

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "Failed to close %s: %s",
                    provider.__class__.__name__,
                    ex,
                )

        logger.info(
            "[NEWS MANAGER] Closed."
        )

        if self.universe_provider is not None:

            try:

                self.universe_provider.close()

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "Failed to close Marketaux: %s",
                    ex,
                )

###############################################################################

    def health_check(self) -> Dict[str, Any]:
        """
        Return provider health information.
        """

        status = {

            "timestamp": self.timestamp,

            "provider_count": self.provider_count,

            "providers": self.list_providers(),

        }

        return status