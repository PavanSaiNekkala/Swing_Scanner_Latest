"""
news/news_manager.py

Central News Management Service for NSE Market Report.

Responsibilities
----------------
- Load configured normal-report news providers.
- Manage Marketaux as the full-universe provider.
- Fetch news from multiple providers.
- Apply 15-day filtering.
- Flatten provider responses.
- Remove duplicate articles.
- Rank articles by relevance.
- Build final per-symbol news records.
- Merge news into the market report.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed

from datetime import datetime
from datetime import timedelta

from pathlib import Path

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import pandas as pd

from config.config import ENABLED_NEWS_PROVIDERS
from config.config import MARKETAUX_API_KEY
from config.config import MAX_WORKERS
from config.config import NEWS_LOOKBACK_DAYS

from config.logging_config import logger

from config.timezone import IST
from config.timezone import now_ist

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

    Normal market-report flow
    -------------------------
        Google News
              |
              v
        NewsAPI
              |
              v
        Collect provider results
              |
              v
        Flatten articles
              |
              v
        15-day filter
              |
              v
        Deduplicate
              |
              v
        Relevance ranking
              |
              v
        Final news dataset

    Full-universe flow
    ------------------
        news_universe.csv
              |
              v
        MarketauxNews
              |
              v
        Full universe dataset
    """

    def __init__(self) -> None:

        logger.info(
            "[NEWS MANAGER] Initializing..."
        )

        self.timestamp = now_ist()

        #######################################################################
        # NORMAL MARKET-REPORT PROVIDERS
        #######################################################################

        self.providers = (
            self._load_providers()
        )

        #######################################################################
        # FULL NEWS UNIVERSE PROVIDER
        #######################################################################

        self.universe_provider = None

        if MARKETAUX_API_KEY:

            try:

                self.universe_provider = (
                    MarketauxNews(
                        MARKETAUX_API_KEY
                    )
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

        else:

            logger.warning(
                "[NEWS MANAGER] "
                "MARKETAUX_API_KEY not configured. "
                "Full news-universe scan disabled."
            )

        logger.info(
            "[NEWS MANAGER] %d provider(s) loaded.",
            len(self.providers),
        )

    ###########################################################################
    # PROVIDER LOADING
    ###########################################################################

    @staticmethod
    def _load_providers() -> List[Any]:
        """
        Load configured normal-report providers.
        """

        providers: List[Any] = []

        #######################################################################
        # GOOGLE NEWS
        #######################################################################

        if "google" in ENABLED_NEWS_PROVIDERS:

            try:

                providers.append(
                    GoogleNews()
                )

                logger.info(
                    "[NEWS MANAGER] "
                    "Google News enabled."
                )

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "Google News initialization failed: %s",
                    ex,
                )

        #######################################################################
        # NEWSAPI
        #######################################################################

        if "newsapi" in ENABLED_NEWS_PROVIDERS:

            try:

                providers.append(
                    NewsAPIClient()
                )

                logger.info(
                    "[NEWS MANAGER] "
                    "NewsAPI enabled."
                )

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "NewsAPI initialization failed: %s",
                    ex,
                )

        if not providers:

            logger.warning(
                "[NEWS MANAGER] "
                "No normal news providers available."
            )

        return providers

    ###########################################################################
    # PROVIDER INFORMATION
    ###########################################################################

    @property
    def provider_count(self) -> int:
        """
        Number of active normal-report providers.
        """

        return len(
            self.providers
        )

    def list_providers(
        self,
    ) -> List[str]:
        """
        Return active provider class names.
        """

        return [
            provider.__class__.__name__
            for provider in self.providers
        ]

    ###########################################################################
    # REFRESH
    ###########################################################################

    def refresh(self) -> None:
        """
        Refresh timestamp and all normal providers.
        """

        self.timestamp = now_ist()

        for provider in self.providers:

            try:

                refresh_method = getattr(
                    provider,
                    "refresh",
                    None,
                )

                if callable(
                    refresh_method
                ):

                    refresh_method()

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "Provider refresh failed: %s",
                    ex,
                )

        logger.info(
            "[NEWS MANAGER] Providers refreshed."
        )

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
        Fetch news from one provider.
        """

        try:

            provider_name = (
                provider.__class__.__name__
            )

            logger.info(
                "[NEWS MANAGER] %s -> %s",
                provider_name,
                symbol,
            )

            result = provider.fetch(
                symbol=symbol,
                company=company,
            )

            if result:

                result["Provider"] = (
                    provider_name
                )

                return result

        except Exception as ex:

            logger.exception(
                "[NEWS MANAGER] "
                "%s failed : %s",
                provider.__class__.__name__,
                ex,
            )

        return None


###############################################################################
# FETCH ALL PROVIDERS FOR ONE STOCK
###############################################################################

    def _collect_news(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect news from every enabled normal-report provider.
        """

        if not self.providers:

            return []

        results: List[
            Dict[str, Any]
        ] = []

        worker_count = min(
            MAX_WORKERS,
            len(self.providers),
        )

        with ThreadPoolExecutor(
            max_workers=worker_count,
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

            for future in as_completed(
                futures
            ):

                result = (
                    future.result()
                )

                if result:

                    results.append(
                        result
                    )

        logger.info(
            "[NEWS MANAGER] "
            "%d provider(s) returned news for %s",
            len(results),
            symbol,
        )

        return results


###############################################################################
# FETCH MANY STOCKS
###############################################################################

    def _collect_news_many(
        self,
        stocks: List[Dict[str, str]],
    ) -> Dict[
        str,
        List[Dict[str, Any]],
    ]:
        """
        Collect provider news for multiple stocks.
        """

        news_map: Dict[
            str,
            List[Dict[str, Any]],
        ] = {}

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
                ):
                    stock["Symbol"]

                for stock in stocks

            }

            for future in as_completed(
                futures
            ):

                symbol = futures[
                    future
                ]

                try:

                    news_map[
                        symbol
                    ] = future.result()

                except Exception as ex:

                    logger.exception(
                        "[NEWS MANAGER] "
                        "News collection failed for %s: %s",
                        symbol,
                        ex,
                    )

                    news_map[
                        symbol
                    ] = []

        logger.info(
            "[NEWS MANAGER] "
            "News collected for %d stocks.",
            len(news_map),
        )

        return news_map


###############################################################################
# FLATTEN PROVIDER RESULTS
###############################################################################

    @staticmethod
    def _flatten(
        provider_results: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Convert provider-level results into
        a unified article list.
        """

        articles: List[
            Dict[str, Any]
        ] = []

        for provider in provider_results:

            if not provider:
                continue

            recent_news = (
                provider.get(
                    "Recent News",
                    [],
                )
                or []
            )

            if not isinstance(
                recent_news,
                list,
            ):

                recent_news = [
                    recent_news
                ]

            for headline in recent_news:

                if not headline:
                    continue

                articles.append(
                    {
                        "Symbol": (
                            provider.get(
                                "Symbol"
                            )
                        ),

                        "Headline": str(
                            headline
                        ).strip(),

                        "Top Headline": (
                            provider.get(
                                "Top Headline"
                            )
                        ),

                        "Description": (
                            provider.get(
                                "Description"
                            )
                        ),

                        "Headline Link": (
                            provider.get(
                                "Headline Link"
                            )
                        ),

                        "Published": (
                            provider.get(
                                "Published"
                            )
                        ),

                        "Source": (
                            provider.get(
                                "Source"
                            )
                        ),

                        "Provider": (
                            provider.get(
                                "Provider"
                            )
                        ),
                    }
                )

        return articles


###############################################################################
# 15-DAY FILTER
###############################################################################

    @staticmethod
    def _filter_recent_articles(
        articles: List[
            Dict[str, Any]
        ],
        days: int,
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Keep only articles published within
        the configured lookback window.

        All timestamps are normalized to IST.
        """

        if not articles:

            return []

        cutoff = (
            now_ist()
            - timedelta(
                days=days
            )
        )

        filtered: List[
            Dict[str, Any]
        ] = []

        for article in articles:

            published = (
                article.get(
                    "Published"
                )
            )

            if not published:
                continue

            try:

                if isinstance(
                    published,
                    datetime,
                ):

                    published_dt = (
                        published
                    )

                else:

                    published_text = (
                        str(
                            published
                        ).strip()
                    )

                    published_dt = (
                        datetime.fromisoformat(
                            published_text.replace(
                                "Z",
                                "+00:00",
                            )
                        )
                    )

                if published_dt.tzinfo is None:

                    published_dt = (
                        published_dt.replace(
                            tzinfo=IST
                        )
                    )

                else:

                    published_dt = (
                        published_dt.astimezone(
                            IST
                        )
                    )

                if published_dt >= cutoff:

                    article[
                        "Published"
                    ] = published_dt

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
                    article.get(
                        "Headline"
                    ),
                    ex,
                )

        return filtered


###############################################################################
# REMOVE DUPLICATES
###############################################################################

    @staticmethod
    def _deduplicate(
        articles: List[
            Dict[str, Any]
        ],
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Remove duplicate articles using
        normalized headline + URL.
        """

        seen = set()

        cleaned: List[
            Dict[str, Any]
        ] = []

        for article in articles:

            headline = str(
                article.get(
                    "Headline"
                )
                or ""
            ).strip().lower()

            link = str(
                article.get(
                    "Headline Link"
                )
                or ""
            ).strip()

            key = (
                headline,
                link,
            )

            if key in seen:

                continue

            seen.add(
                key
            )

            cleaned.append(
                article
            )

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
        Calculate article relevance score.
        """

        score = 0

        symbol_text = str(
            symbol or ""
        ).strip().lower()

        headline = str(
            article.get(
                "Headline"
            )
            or ""
        ).strip().lower()

        description = str(
            article.get(
                "Description"
            )
            or ""
        ).strip().lower()

        provider = str(
            article.get(
                "Provider"
            )
            or ""
        ).strip()

        if (
            symbol_text
            and symbol_text in headline
        ):

            score += 40

        if (
            symbol_text
            and symbol_text in description
        ):

            score += 20

        keywords = {

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

        }

        text = (
            f"{headline} {description}"
        )

        for word, weight in (
            keywords.items()
        ):

            if word in text:

                score += weight

        if provider == "GoogleNews":

            score += 5

        elif provider == "NewsAPIClient":

            score += 3

        return score


###############################################################################
# SORT ARTICLES
###############################################################################

    def _rank_articles(
        self,
        articles: List[
            Dict[str, Any]
        ],
        symbol: str,
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Sort articles by descending relevance.
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
        articles: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:
        """
        Build the final per-symbol news record.
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

        recent_news: List[str] = []

        for article in articles:

            headline = str(
                article.get(
                    "Headline"
                )
                or ""
            ).strip()

            if (
                headline
                and headline not in recent_news
            ):

                recent_news.append(
                    headline
                )

            if len(
                recent_news
            ) >= 5:

                break

        return {
            "Symbol": symbol,

            "Top Headline":
                top.get(
                    "Headline"
                ),

            "Headline Link":
                top.get(
                    "Headline Link"
                ),

            "Description":
                top.get(
                    "Description"
                ),

            "Source":
                top.get(
                    "Source"
                ),

            "Published":
                top.get(
                    "Published"
                ),

            "Recent News":
                recent_news,
        }


###############################################################################
# COMPLETE PROCESSING PIPELINE
###############################################################################

    def _process_news(
        self,
        symbol: str,
        provider_results: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:
        """
        Complete provider -> article -> report pipeline.
        """

        articles = self._flatten(
            provider_results
        )

        articles = (
            self._filter_recent_articles(
                articles,
                days=NEWS_LOOKBACK_DAYS,
            )
        )

        logger.info(
            "[NEWS MANAGER] %s | "
            "Articles within last %d days: %d",
            symbol,
            NEWS_LOOKBACK_DAYS,
            len(articles),
        )

        articles = self._deduplicate(
            articles
        )

        articles = self._rank_articles(
            articles,
            symbol,
        )

        return self._build_news(
            symbol,
            articles,
        )


###############################################################################
# NEWS UNIVERSE LOADER
###############################################################################

    def load_news_universe(
        self,
        csv_path: Path,
    ) -> List[
        Dict[str, str]
    ]:
        """
        Load the full news-scanning universe.
        """

        if not csv_path.exists():

            raise FileNotFoundError(
                f"News universe file not found: "
                f"{csv_path}"
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

        stocks: List[
            Dict[str, str]
        ] = []

        for _, row in df.iterrows():

            symbol = str(
                row.get(
                    symbol_column,
                    "",
                )
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

                if (
                    company.lower()
                    == "nan"
                ):

                    company = ""

            stocks.append(
                {
                    "Symbol": symbol,
                    "Company": company,
                }
            )

        #######################################################################
        # DEDUPLICATE UNIVERSE
        #######################################################################

        before_deduplication = len(
            stocks
        )

        unique: Dict[
            str,
            Dict[str, str],
        ] = {}

        for stock in stocks:

            symbol = stock[
                "Symbol"
            ]

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


###############################################################################
# FULL MARKET NEWS UNIVERSE SCAN
###############################################################################

    def scan_news_universe(
        self,
        csv_path: Path,
    ) -> pd.DataFrame:
        """
        Scan the full CSV universe using Marketaux.

        Google News is intentionally kept for the
        normal 40-stock market report.
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

        if "Symbol" in news_df.columns:

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
            "Completed Marketaux scan | Symbols=%d",
            len(news_df),
        )

        return news_df


###############################################################################
# PUBLIC FETCH API
###############################################################################

    def fetch(
        self,
        symbol: str,
        company: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch and process news for one stock.
        """

        symbol = str(
            symbol or ""
        ).strip().upper()

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


###############################################################################
# PUBLIC FETCH MANY API
###############################################################################

    def fetch_many(
        self,
        stocks: List[
            Dict[str, str]
        ],
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

            symbol = str(
                stock.get(
                    "Symbol",
                    "",
                )
            ).strip().upper()

            if not symbol:

                continue

            provider_results = (
                news_map.get(
                    symbol,
                    [],
                )
            )

            result = (
                self._process_news(
                    symbol,
                    provider_results,
                )
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
# MERGE WITH MARKET REPORT
###############################################################################

    def merge(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge processed news into the market report.
        """

        if report_df.empty:

            logger.warning(
                "[NEWS MANAGER] "
                "Empty report dataframe."
            )

            return report_df

        stocks: List[
            Dict[str, str]
        ] = []

        for _, row in report_df.iterrows():

            stocks.append(
                {
                    "Symbol": row[
                        "Symbol"
                    ],

                    "Company": row.get(
                        "Company"
                    ),
                }
            )

        news_df = self.fetch_many(
            stocks
        )

        if news_df.empty:

            logger.warning(
                "[NEWS MANAGER] "
                "No news available."
            )

            return report_df

        merged = report_df.merge(
            news_df,
            on="Symbol",
            how="left",
            suffixes=(
                "",
                "_News",
            ),
        )

        logger.info(
            "[NEWS MANAGER] "
            "Report merged successfully."
        )

        return merged


###############################################################################
# CLOSE
###############################################################################

    def close(
        self,
    ) -> None:
        """
        Close all configured providers.
        """

        #######################################################################
        # NORMAL PROVIDERS
        #######################################################################

        for provider in self.providers:

            try:

                close_method = getattr(
                    provider,
                    "close",
                    None,
                )

                if callable(
                    close_method
                ):

                    close_method()

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "Failed to close %s: %s",
                    provider.__class__.__name__,
                    ex,
                )

        #######################################################################
        # MARKET AUX
        #######################################################################

        if (
            self.universe_provider
            is not None
        ):

            try:

                close_method = getattr(
                    self.universe_provider,
                    "close",
                    None,
                )

                if callable(
                    close_method
                ):

                    close_method()

            except Exception as ex:

                logger.exception(
                    "[NEWS MANAGER] "
                    "Failed to close Marketaux: %s",
                    ex,
                )

        logger.info(
            "[NEWS MANAGER] Closed."
        )


###############################################################################
# HEALTH CHECK
###############################################################################

    def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Return news service health information.
        """

        return {
            "timestamp": self.timestamp,

            "provider_count":
                self.provider_count,

            "providers":
                self.list_providers(),

            "marketaux_enabled":
                self.universe_provider
                is not None,
        }
