"""
Institutional News Deduplicator

Responsibilities
----------------
- Remove duplicate news articles
- Remove near-duplicate headlines
- Keep highest-quality articles
- Preserve publication ordering

This module intentionally DOES NOT:
    - Fetch news
    - Rank news
    - Summarize news
    - Export reports

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

import re
import time

from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from difflib import SequenceMatcher

from config.logging_config import get_logger

from market.models import (
    NewsArticle,
    NewsReport,
    StockNews,
)

from news.ranker import (
    NewsRanker,
    build_news_ranker,
)

from news.summarizer import (
    NewsSummarizer,
    build_news_summarizer,
)

logger = get_logger(__name__)

###############################################################################
# Configuration
###############################################################################

FUZZY_MATCH_THRESHOLD = 0.90

###############################################################################
# Provider Quality Ranking
###############################################################################

PROVIDER_PRIORITY = {

    "Reuters": 100,

    "Bloomberg": 95,

    "CNBC": 90,

    "Moneycontrol": 85,

    "Economic Times": 80,

    "Business Standard": 75,

    "Mint": 70,

    "Livemint": 70,

    "Yahoo Finance": 65,

    "Google News": 60,

    "Unknown": 0,

}

###############################################################################
# Base Interface
###############################################################################


class Deduplicator(ABC):
    """
    Base deduplicator interface.
    """

    @abstractmethod
    def deduplicate(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Remove duplicate articles.
        """


###############################################################################
# News Deduplicator
###############################################################################


class NewsDeduplicator(
    Deduplicator,
):
    """
    Production-grade news deduplicator.
    """

    def __init__(
        self,
    ) -> None:

        self.statistics = defaultdict(int)

        self.start_time = 0.0

        logger.info(
            "NewsDeduplicator initialized."
        )

###############################################################################
# Statistics
###############################################################################

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

    def elapsed(
        self,
    ) -> float:

        return round(

            time.perf_counter()

            - self.start_time,

            2,

        )

###############################################################################
# Headline Normalization
###############################################################################

    @staticmethod
    def normalize_title(
        title: str,
    ) -> str:
        """
        Normalize headlines before comparison.
        """

        title = title.lower()

        title = re.sub(
            r"[^\w\s]",
            " ",
            title,
        )

        title = re.sub(
            r"\s+",
            " ",
            title,
        )

        return title.strip()

###############################################################################
# URL Normalization
###############################################################################

    @staticmethod
    def normalize_url(
        url: str,
    ) -> str:
        """
        Normalize URLs.
        """

        if not url:

            return ""

        return (

            url.strip()

            .lower()

            .replace(
                "https://",
                "",
            )

            .replace(
                "http://",
                "",
            )

            .rstrip("/")

        )

###############################################################################
# Similarity
###############################################################################

    @staticmethod
    def similarity(
        left: str,
        right: str,
    ) -> float:
        """
        Headline similarity.
        """

        return SequenceMatcher(

            None,

            left,

            right,

        ).ratio()

###############################################################################
# Provider Ranking
###############################################################################

    @staticmethod
    def provider_score(
        provider: str,
    ) -> int:
        """
        Provider quality score.
        """

        return PROVIDER_PRIORITY.get(

            provider,

            0,

        )

###############################################################################
# Better Article
###############################################################################

    def better_article(
        self,
        first: NewsArticle,
        second: NewsArticle,
    ) -> NewsArticle:
        """
        Return the better article.
        """

        first_score = self.provider_score(
            first.source,
        )

        second_score = self.provider_score(
            second.source,
        )

        if first_score > second_score:

            return first

        if second_score > first_score:

            return second

        if first.published_at >= second.published_at:

            return first

        return second


###############################################################################
# Duplicate Removal by URL
###############################################################################

    def remove_duplicate_urls(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Remove duplicate URLs.
        """

        unique: dict[str, NewsArticle] = {}

        for article in articles:

            url = self.normalize_url(
                article.url,
            )

            if not url:

                unique[
                    f"missing-{id(article)}"
                ] = article

                continue

            if url not in unique:

                unique[url] = article

                continue

            unique[url] = self.better_article(
                unique[url],
                article,
            )

            self.increment(
                "duplicate_urls",
            )

        return list(
            unique.values()
        )

###############################################################################
# Duplicate Removal by Exact Title
###############################################################################

    def remove_duplicate_titles(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Remove duplicate normalized titles.
        """

        unique: dict[str, NewsArticle] = {}

        for article in articles:

            title = self.normalize_title(
                article.title,
            )

            if title not in unique:

                unique[title] = article

                continue

            unique[title] = self.better_article(
                unique[title],
                article,
            )

            self.increment(
                "duplicate_titles",
            )

        return list(
            unique.values()
        )

###############################################################################
# Fuzzy Duplicate Removal
###############################################################################

    def remove_fuzzy_duplicates(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Remove near-identical headlines.
        """

        results: list[
            NewsArticle
        ] = []

        for article in articles:

            duplicate = False

            normalized = self.normalize_title(
                article.title,
            )

            for index, existing in enumerate(results):

                similarity = self.similarity(
                    normalized,
                    self.normalize_title(
                        existing.title,
                    ),
                )

                if similarity >= FUZZY_MATCH_THRESHOLD:

                    results[index] = self.better_article(
                        existing,
                        article,
                    )

                    duplicate = True

                    self.increment(
                        "duplicate_fuzzy",
                    )

                    break

            if not duplicate:

                results.append(
                    article,
                )

        return results

###############################################################################
# Sorting
###############################################################################

    @staticmethod
    def sort_articles(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Latest article first.
        """

        return sorted(
            articles,
            key=lambda article: article.published_at,
            reverse=True,
        )

###############################################################################
# Per-Stock Cleanup
###############################################################################

    def process_stock(
        self,
        stock: StockNews,
    ) -> StockNews:
        """
        Deduplicate one stock's news.
        """

        articles = stock.articles

        before = len(
            articles,
        )

        articles = self.remove_duplicate_urls(
            articles,
        )

        articles = self.remove_duplicate_titles(
            articles,
        )

        articles = self.remove_fuzzy_duplicates(
            articles,
        )

        articles = self.sort_articles(
            articles,
        )

        after = len(
            articles,
        )

        self.increment(
            "removed_articles",
            before - after,
        )

        self.increment(
            "processed_stocks",
        )

        logger.debug(
            "%-12s %3d -> %3d articles",
            stock.ticker,
            before,
            after,
        )

        return StockNews(
            ticker=stock.ticker,
            company_name=stock.company_name,
            articles=articles,

            executive_summary=stock.executive_summary,
            sentiment=stock.sentiment,
            bullish_points=stock.bullish_points,
            bearish_points=stock.bearish_points,
            key_events=stock.key_events,
            confidence=stock.confidence,
            rank_score=stock.rank_score,
        )

###############################################################################
# Batch Processing
###############################################################################

    def process_many(
        self,
        stocks: list[StockNews],
    ) -> list[StockNews]:
        """
        Deduplicate news for multiple stocks.
        """

        logger.info(
            "Deduplicating %d stock news collections.",
            len(stocks),
        )

        cleaned: list[StockNews] = []

        for stock in stocks:

            try:

                cleaned.append(
                    self.process_stock(
                        stock,
                    )
                )

            except Exception:

                self.increment(
                    "failed_stocks",
                )

                logger.exception(
                    "Deduplication failed | %s",
                    stock.ticker,
                )

        return cleaned

###############################################################################
# Report Builder
###############################################################################

    def build_report(
        self,
        report: NewsReport,
        gainers: list[StockNews],
        losers: list[StockNews],
    ) -> NewsReport:
        """
        Build a new deduplicated NewsReport.
        """

        cleaned = NewsReport()

        cleaned.gainers_news = gainers

        cleaned.losers_news = losers

        cleaned.total_articles = sum(
            len(stock.articles)
            for stock in gainers + losers
        )

        return cleaned

###############################################################################
# Public Pipeline
###############################################################################

    def deduplicate(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Execute the complete deduplication pipeline.
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "Starting News Deduplication Pipeline"
        )

        logger.info(
            "=" * 80
        )

        self.reset_statistics()

        #######################################################################
        # Process Top Gainers
        #######################################################################

        gainers = self.process_many(
            report.gainers_news,
        )

        #######################################################################
        # Process Top Losers
        #######################################################################

        losers = self.process_many(
            report.losers_news,
        )

        #######################################################################
        # Build Final Report
        #######################################################################

        cleaned_report = self.build_report(
            report=report,
            gainers=gainers,
            losers=losers,
        )

        #######################################################################
        # Statistics
        #######################################################################

        self.log_statistics(
            cleaned_report,
        )

        logger.info(
            "=" * 80
        )

        logger.info(
            "News Deduplication Completed"
        )

        logger.info(
            "=" * 80
        )

        return cleaned_report

###############################################################################
# Statistics
###############################################################################

    def log_statistics(
        self,
        report: NewsReport,
    ) -> None:
        """
        Log deduplication metrics.
        """

        logger.info(
            "Execution Summary"
        )

        logger.info(
            "-" * 80
        )

        logger.info(
            "Processed Stocks     : %d",
            self.statistics.get(
                "processed_stocks",
                0,
            ),
        )

        logger.info(
            "Failed Stocks        : %d",
            self.statistics.get(
                "failed_stocks",
                0,
            ),
        )

        logger.info(
            "Duplicate URLs       : %d",
            self.statistics.get(
                "duplicate_urls",
                0,
            ),
        )

        logger.info(
            "Duplicate Titles     : %d",
            self.statistics.get(
                "duplicate_titles",
                0,
            ),
        )

        logger.info(
            "Fuzzy Duplicates     : %d",
            self.statistics.get(
                "duplicate_fuzzy",
                0,
            ),
        )

        logger.info(
            "Articles Removed     : %d",
            self.statistics.get(
                "removed_articles",
                0,
            ),
        )

        logger.info(
            "Remaining Articles   : %d",
            report.total_articles,
        )

        logger.info(
            "Execution Time       : %.2f sec",
            self.elapsed(),
        )


###############################################################################
# Factory
###############################################################################


def build_news_deduplicator() -> NewsDeduplicator:
    """
    Factory for NewsDeduplicator.
    """

    deduplicator = NewsDeduplicator()

    logger.info(
        "NewsDeduplicator created."
    )

    return deduplicator