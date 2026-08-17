"""
Institutional News Collector

Responsibilities
----------------
- Collect financial news for selected stocks
- Support multiple news providers
- Normalize provider responses
- Execute provider calls concurrently
- Return domain models only

This module intentionally DOES NOT:
    - Deduplicate news
    - Rank news
    - Summarize news
    - Export reports

Those responsibilities belong to later pipeline stages.

Author
------
Pavan Sai Nekkala

Project
-------
NEWS_REPORT

Python
------
3.12+
"""

from __future__ import annotations

import concurrent.futures
import logging
import time

from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from typing import Any

from config.settings import settings
from config.logging_config import get_logger

from market.models import (
    MarketReport,
    MarketStock,
    NewsArticle,
    NewsReport,
    StockNews,
)

from data.providers.google_news_provider import (
    GoogleNewsProvider,
)

from data.providers.yahoo_news_provider import (
    YahooNewsProvider,
)

logger = get_logger(__name__)

###############################################################################
# Constants
###############################################################################

MAX_NEWS_PER_STOCK = 5

LOOKBACK_DAYS = 7

DEFAULT_TIMEOUT = 20

###############################################################################
# Provider Interface
###############################################################################


class NewsProvider(ABC):
    """
    Base interface for every news provider.

    Every provider must normalize its output into NewsArticle objects.
    """

    provider_name: str

    @abstractmethod
    def fetch(
        self,
        ticker: str,
        company_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[NewsArticle]:
        """
        Fetch news articles for one stock.
        """


###############################################################################
# Base Provider
###############################################################################


class BaseNewsProvider(
    NewsProvider,
):
    """
    Shared functionality for all providers.
    """

    provider_name = "BASE"

    def __init__(
        self,
    ) -> None:

        self.timeout = DEFAULT_TIMEOUT

    @staticmethod
    def normalize_text(
        value: str | None,
    ) -> str:

        if value is None:

            return ""

        return value.strip()

    @staticmethod
    def normalize_url(
        value: str | None,
    ) -> str:

        if value is None:

            return ""

        return value.strip()


###############################################################################
# News Collector
###############################################################################


class NewsCollector:
    """
    Collect news from every configured provider.

    Workflow

        MarketReport
              │
              ▼
        Extract Stocks
              │
              ▼
      Execute Providers
              │
              ▼
      Normalize Articles
              │
              ▼
         NewsReport
    """

    def __init__(
        self,
        providers: list[NewsProvider],
    ) -> None:

        self.providers = providers

        self.max_workers = (
            settings.thread_pool.max_workers
        )

        self.start_time = None

        self.statistics = defaultdict(int)

        logger.info(
            "NewsCollector initialized."
        )

        logger.info(
            "Providers : %d",
            len(self.providers),
        )

        logger.info(
            "Workers   : %d",
            self.max_workers,
        )

    ###########################################################################
    # Metrics
    ###########################################################################

    def reset_statistics(
        self,
    ) -> None:

        self.statistics.clear()

        self.start_time = time.perf_counter()

    def increment(
        self,
        metric: str,
        value: int = 1,
    ) -> None:

        self.statistics[metric] += value

    def elapsed_seconds(
        self,
    ) -> float:

        if self.start_time is None:

            return 0.0

        return round(

            time.perf_counter()

            - self.start_time,

            2,

        )

    ###########################################################################
    # Provider Management
    ###########################################################################

    def provider_names(
        self,
    ) -> list[str]:

        return [

            provider.provider_name

            for provider in self.providers

        ]

    def log_provider_summary(
        self,
    ) -> None:

        logger.info(
            "Registered News Providers:"
        )

        for provider in self.providers:

            logger.info(
                " • %s",
                provider.provider_name,
            )

    ###########################################################################
    # Utility
    ###########################################################################

    @staticmethod
    def date_window(
        lookback_days: int = LOOKBACK_DAYS,
    ) -> tuple[datetime, datetime]:

        end_date = datetime.utcnow()

        start_date = end_date - timedelta(
            days=lookback_days,
        )

        return (
            start_date,
            end_date,
        )

    @staticmethod
    def extract_market_stocks(
        report: MarketReport,
    ) -> list[MarketStock]:
        """
        Merge gainers and losers into a single list.
        """

        stocks: list[
            MarketStock
        ] = []

        stocks.extend(
            report.gainers.stocks
        )

        stocks.extend(
            report.losers.stocks
        )

        return stocks


###############################################################################
# Single Stock Collection
###############################################################################

    def collect_stock_news(
        self,
        stock: MarketStock,
    ) -> StockNews:
        """
        Collect news for a single stock from every configured provider.
        """

        start_date, end_date = self.date_window()

        articles: list[NewsArticle] = []

        logger.info(
            "Collecting news | %s",
            stock.identity.ticker,
        )

        for provider in self.providers:

            try:

                provider_articles = provider.fetch(
                    ticker=stock.identity.ticker,
                    company_name=stock.identity.company_name,
                    start_date=start_date,
                    end_date=end_date,
                )

                articles.extend(
                    provider_articles
                )

                self.increment(
                    "provider_success",
                )

                self.increment(
                    "articles_downloaded",
                    len(provider_articles),
                )

                logger.debug(
                    "%s -> %d articles",
                    provider.provider_name,
                    len(provider_articles),
                )

            except Exception:

                self.increment(
                    "provider_failures",
                )

                logger.exception(
                    "Provider failed | %s | %s",
                    provider.provider_name,
                    stock.identity.ticker,
                )

        articles = self.limit_articles(
            articles,
        )

        return StockNews(
            ticker=stock.identity.ticker,
            company_name=stock.identity.company_name,
            articles=articles,

            executive_summary="",
            sentiment="Neutral",
            bullish_points=[],
            bearish_points=[],
            key_events=[],
            confidence=0.0,
            rank_score=0.0,        
        )

###############################################################################
# Batch Collection
###############################################################################

    def collect_many(
        self,
        stocks: list[MarketStock],
    ) -> list[StockNews]:
        """
        Collect news concurrently.
        """

        logger.info(
            "Collecting news for %d stocks.",
            len(stocks),
        )

        results: list[
            StockNews
        ] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="NewsCollector",
        ) as executor:

            futures = {

                executor.submit(
                    self.collect_stock_news,
                    stock,
                ): stock

                for stock in stocks

            }

            completed = 0

            for future in concurrent.futures.as_completed(
                futures,
            ):

                stock = futures[
                    future
                ]

                completed += 1

                try:

                    result = future.result()

                    results.append(
                        result,
                    )

                    self.increment(
                        "stocks_processed",
                    )

                except Exception:

                    self.increment(
                        "stocks_failed",
                    )

                    logger.exception(
                        "News collection failed | %s",
                        stock.identity.ticker,
                    )

                logger.info(
                    "Progress %d/%d",
                    completed,
                    len(stocks),
                )

        return results

###############################################################################
# Filtering
###############################################################################

    @staticmethod
    def filter_last_week(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Keep only last LOOKBACK_DAYS.
        """

        cutoff = (
            datetime.utcnow()
            - timedelta(
                days=LOOKBACK_DAYS,
            )
        )

        return [

            article

            for article in articles

            if article.published_at >= cutoff

        ]

###############################################################################
# Sorting
###############################################################################

    @staticmethod
    def sort_articles(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Latest articles first.
        """

        return sorted(

            articles,

            key=lambda article: (
                article.published_at,
            ),

            reverse=True,

        )

###############################################################################
# Limiting
###############################################################################

    def limit_articles(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Keep latest MAX_NEWS_PER_STOCK.
        """

        articles = self.filter_last_week(
            articles,
        )

        articles = self.sort_articles(
            articles,
        )

        return articles[
            :MAX_NEWS_PER_STOCK
        ]

###############################################################################
# Report Builder
###############################################################################

    def build_report(
        self,
        gainers_news: list[StockNews],
        losers_news: list[StockNews],
    ) -> NewsReport:
        """
        Build NewsReport.
        """

        report = NewsReport()

        report.gainers_news = gainers_news

        report.losers_news = losers_news

        report.total_articles = sum(
            len(stock.articles)
            for stock in gainers_news + losers_news
        )

        return report

###############################################################################
# Pipeline Execution
###############################################################################

    def collect(
        self,
        market_report: MarketReport,
    ) -> NewsReport:
        """
        Collect news for the Top Gainers and Top Losers.

        Workflow
        --------
            MarketReport
                 │
                 ▼
          Collect Gainers
                 │
                 ▼
          Collect Losers
                 │
                 ▼
          Build NewsReport
                 │
                 ▼
              Return
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "Starting News Collection Pipeline"
        )

        logger.info(
            "=" * 80
        )

        self.reset_statistics()

        self.log_provider_summary()

        #######################################################################
        # Collect Top Gainers
        #######################################################################

        logger.info(
            "Collecting news for %d gainers.",
            len(
                market_report.top_gainers.stocks
            ),
        )

        gainers_news = self.collect_many(
            market_report.top_gainers.stocks,
        )

        #######################################################################
        # Collect Top Losers
        #######################################################################

        logger.info(
            "Collecting news for %d losers.",
            len(
                market_report.top_losers.stocks
            ),
        )

        losers_news = self.collect_many(
            market_report.top_losers.stocks,
        )

        #######################################################################
        # Build Final Report
        #######################################################################

        report = self.build_report(
            gainers_news=gainers_news,
            losers_news=losers_news,
        )

        #######################################################################
        # Statistics
        #######################################################################

        self.log_statistics(
            report,
        )

        logger.info(
            "=" * 80
        )

        logger.info(
            "News Collection Pipeline Completed"
        )

        logger.info(
            "=" * 80
        )

        return report

###############################################################################
# Statistics
###############################################################################

    def log_statistics(
        self,
        report: NewsReport,
    ) -> None:
        """
        Log execution summary.
        """

        logger.info(
            "Execution Summary"
        )

        logger.info(
            "-" * 80
        )

        logger.info(
            "Providers            : %d",
            len(
                self.providers
            ),
        )

        logger.info(
            "Stocks Processed     : %d",
            self.statistics.get(
                "stocks_processed",
                0,
            ),
        )

        logger.info(
            "Stocks Failed        : %d",
            self.statistics.get(
                "stocks_failed",
                0,
            ),
        )

        logger.info(
            "Providers Success    : %d",
            self.statistics.get(
                "provider_success",
                0,
            ),
        )

        logger.info(
            "Providers Failed     : %d",
            self.statistics.get(
                "provider_failures",
                0,
            ),
        )

        logger.info(
            "Articles Downloaded  : %d",
            self.statistics.get(
                "articles_downloaded",
                0,
            ),
        )

        logger.info(
            "Final Articles       : %d",
            report.total_articles,
        )

        logger.info(
            "Execution Time       : %.2f sec",
            self.elapsed_seconds(),
        )


###############################################################################
# Factory
###############################################################################

def build_news_collector() -> NewsCollector:
    """
    Factory for NewsCollector.

    Creates the default set of news providers.
    """

    providers = [
        GoogleNewsProvider(),
        YahooNewsProvider(),
    ]

    collector = NewsCollector(
        providers=providers,
    )

    logger.info(
        "NewsCollector created."
    )

    return collector