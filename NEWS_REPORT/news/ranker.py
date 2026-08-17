"""
Institutional News Ranker

Responsibilities
----------------
- Rank deduplicated news articles
- Score financial relevance
- Score provider quality
- Score publication recency
- Score headline quality
- Produce ranked news for downstream AI summarization

This module intentionally DOES NOT:
    - Fetch news
    - Deduplicate news
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

import math
import re
import time

from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime
from datetime import timezone

from config.logging_config import get_logger

from market.models import (
    NewsArticle,
    NewsReport,
    StockNews,
)

logger = get_logger(__name__)

###############################################################################
# Ranking Configuration
###############################################################################

MAX_ARTICLES_PER_STOCK = 5

###############################################################################
# Score Weights
###############################################################################

PROVIDER_WEIGHT = 30.0
RECENCY_WEIGHT = 30.0
KEYWORD_WEIGHT = 25.0
HEADLINE_WEIGHT = 10.0
CONTENT_WEIGHT = 5.0

###############################################################################
# Provider Scores
###############################################################################

PROVIDER_SCORE = {

    "Reuters": 100,

    "Bloomberg": 98,

    "CNBC": 95,

    "Moneycontrol": 92,

    "Economic Times": 90,

    "Business Standard": 88,

    "Mint": 86,

    "Livemint": 86,

    "Yahoo Finance": 84,

    "Google News": 82,

    "MarketWatch": 80,

    "NSE": 100,

    "BSE": 98,

    "Unknown": 50,

}

###############################################################################
# Financial Keywords
###############################################################################

KEYWORD_SCORE = {

    "results": 100,
    "earnings": 100,
    "quarterly": 98,
    "q1": 96,
    "q2": 96,
    "q3": 96,
    "q4": 96,
    "profit": 95,
    "loss": 95,
    "revenue": 94,
    "ebitda": 93,
    "guidance": 92,
    "dividend": 90,
    "buyback": 90,
    "bonus": 90,
    "split": 90,
    "merger": 96,
    "acquisition": 96,
    "order": 94,
    "contract": 94,
    "approval": 92,
    "fii": 90,
    "dii": 90,
    "pledge": 88,
    "stake": 88,
    "investment": 88,
    "capex": 88,
    "expansion": 86,
    "plant": 86,
    "factory": 86,
    "ipo": 84,
    "listing": 84,
    "board": 82,
    "management": 82,
    "ceo": 82,
    "md": 80,
    "director": 80,
    "regulation": 90,
    "sebi": 90,
    "nclt": 88,
    "supreme court": 86,
    "high court": 84,

}

###############################################################################
# Abstract Interface
###############################################################################


class Ranker(ABC):
    """
    Abstract ranking interface.
    """

    @abstractmethod
    def rank(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Rank a NewsReport.
        """


###############################################################################
# News Ranker
###############################################################################


class NewsRanker(
    Ranker,
):
    """
    Institutional news ranking engine.
    """

    def __init__(
        self,
    ) -> None:

        self.statistics = defaultdict(int)

        self.start_time = 0.0

        logger.info(
            "NewsRanker initialized."
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
# Provider Score
###############################################################################

    @staticmethod
    def provider_score(
        provider: str,
    ) -> float:
        """
        Provider credibility score.
        """

        raw = PROVIDER_SCORE.get(
            provider,
            PROVIDER_SCORE["Unknown"],
        )

        return (
            raw / 100
        ) * PROVIDER_WEIGHT

###############################################################################
# Keyword Score
###############################################################################

    @staticmethod
    def keyword_score(
        article: NewsArticle,
    ) -> float:
        """
        Financial relevance score.
        """

        headline = article.title.lower()

        score = 0.0

        for keyword, weight in KEYWORD_SCORE.items():

            if keyword in headline:

                score = max(
                    score,
                    weight,
                )

        return (
            score / 100
        ) * KEYWORD_WEIGHT

###############################################################################
# Headline Quality
###############################################################################

    @staticmethod
    def headline_score(
        article: NewsArticle,
    ) -> float:
        """
        Score headline quality.
        """

        headline = article.title.strip()

        words = re.findall(
            r"\w+",
            headline,
        )

        if len(words) < 4:

            return 2.0

        if len(words) > 18:

            return 6.0

        return HEADLINE_WEIGHT

###############################################################################
# Content Quality
###############################################################################

    @staticmethod
    def content_score(
        article: NewsArticle,
    ) -> float:
        """
        Score article completeness.
        """

        body = getattr(
            article,
            "summary",
            "",
        )

        if not body:

            return 1.0

        words = len(
            body.split()
        )

        if words >= 150:

            return CONTENT_WEIGHT

        return min(
            CONTENT_WEIGHT,
            words / 150 * CONTENT_WEIGHT,
        )

###############################################################################
# Recency Score
###############################################################################

    @staticmethod
    def recency_score(
        article: NewsArticle,
    ) -> float:
        """
        Score article freshness.

        Latest news receives the highest score.
        Older news decays exponentially.
        """

        now = datetime.now(
            timezone.utc,
        )

        published = article.published_at

        if published.tzinfo is None:

            published = published.replace(
                tzinfo=timezone.utc,
            )

        hours = max(
            0.0,
            (
                now - published
            ).total_seconds()
            / 3600,
        )

        decay = math.exp(
            -hours / 72,
        )

        return (
            decay
            * RECENCY_WEIGHT
        )

###############################################################################
# Composite Score
###############################################################################

    def calculate_score(
        self,
        article: NewsArticle,
    ) -> float:
        """
        Calculate overall ranking score.
        """

        provider = self.provider_score(
            article.source,
        )

        recency = self.recency_score(
            article,
        )

        keyword = self.keyword_score(
            article,
        )

        headline = self.headline_score(
            article,
        )

        content = self.content_score(
            article,
        )

        score = (
            provider
            + recency
            + keyword
            + headline
            + content
        )

        return round(
            score,
            2,
        )

###############################################################################
# Score Articles
###############################################################################

    def score_articles(
        self,
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Assign ranking scores.
        """

        for article in articles:

            article.rank_score = (
                self.calculate_score(
                    article,
                )
            )

            self.increment(
                "articles_scored",
            )

        return articles

###############################################################################
# Sort Articles
###############################################################################

    @staticmethod
    def sort_articles(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Highest score first.
        """

        return sorted(
            articles,
            key=lambda article: (
                article.rank_score,
                article.published_at,
            ),
            reverse=True,
        )

###############################################################################
# Limit Articles
###############################################################################

    @staticmethod
    def limit_articles(
        articles: list[NewsArticle],
    ) -> list[NewsArticle]:
        """
        Keep only highest-ranked articles.
        """

        return articles[
            :MAX_ARTICLES_PER_STOCK
        ]

###############################################################################
# Rank One Stock
###############################################################################

    def rank_stock(
        self,
        stock: StockNews,
    ) -> StockNews:
        """
        Rank articles belonging to a single stock.
        """

        logger.debug(
            "Ranking %s (%d articles)",
            stock.ticker,
            len(stock.articles),
        )

        articles = self.score_articles(
            stock.articles,
        )

        articles = self.sort_articles(
            articles,
        )

        articles = self.limit_articles(
            articles,
        )

        self.increment(
            "stocks_ranked",
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
# Batch Ranking
###############################################################################

    def process_many(
        self,
        stocks: list[StockNews],
    ) -> list[StockNews]:
        """
        Rank multiple stocks.
        """

        logger.info(
            "Ranking %d stocks.",
            len(stocks),
        )

        ranked: list[
            StockNews
        ] = []

        for stock in stocks:

            try:

                ranked.append(
                    self.rank_stock(
                        stock,
                    )
                )

            except Exception:

                self.increment(
                    "failed_stocks",
                )

                logger.exception(
                    "Ranking failed | %s",
                    stock.ticker,
                )

        return ranked


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
        Build ranked NewsReport.
        """

        ranked = NewsReport()

        ranked.gainers_news = gainers

        ranked.losers_news = losers

        ranked.total_articles = sum(
            len(stock.articles)
            for stock in gainers + losers
        )

        return ranked

###############################################################################
# Public Pipeline
###############################################################################

    def rank(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Rank all collected news.

        Workflow
        --------
            NewsReport
                 │
                 ▼
          Rank Gainers
                 │
                 ▼
          Rank Losers
                 │
                 ▼
         Build Ranked Report
                 │
                 ▼
              Return
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "Starting News Ranking Pipeline"
        )

        logger.info(
            "=" * 80
        )

        self.reset_statistics()

        #######################################################################
        # Rank Top Gainers
        #######################################################################

        logger.info(
            "Ranking %d gainers.",
            len(
                report.gainers_news
            ),
        )

        ranked_gainers = self.process_many(
            report.gainers_news,
        )

        #######################################################################
        # Rank Top Losers
        #######################################################################

        logger.info(
            "Ranking %d losers.",
            len(
                report.losers_news
            ),
        )

        ranked_losers = self.process_many(
            report.losers_news,
        )

        #######################################################################
        # Build Final Report
        #######################################################################

        ranked_report = self.build_report(
            report=report,
            gainers=ranked_gainers,
            losers=ranked_losers,
        )

        #######################################################################
        # Statistics
        #######################################################################

        self.log_statistics(
            ranked_report,
        )

        logger.info(
            "=" * 80
        )

        logger.info(
            "News Ranking Completed"
        )

        logger.info(
            "=" * 80
        )

        return ranked_report

###############################################################################
# Statistics
###############################################################################

    def log_statistics(
        self,
        report: NewsReport,
    ) -> None:
        """
        Log ranking statistics.
        """

        logger.info(
            "Execution Summary"
        )

        logger.info(
            "-" * 80
        )

        logger.info(
            "Stocks Ranked        : %d",
            self.statistics.get(
                "stocks_ranked",
                0,
            ),
        )

        logger.info(
            "Stocks Failed        : %d",
            self.statistics.get(
                "failed_stocks",
                0,
            ),
        )

        logger.info(
            "Articles Ranked      : %d",
            self.statistics.get(
                "articles_scored",
                0,
            ),
        )

        logger.info(
            "Final Articles       : %d",
            report.total_articles,
        )

        logger.info(
            "Execution Time       : %.2f sec",
            self.elapsed(),
        )


###############################################################################
# Factory
###############################################################################

def build_news_ranker() -> NewsRanker:
    """
    Factory for NewsRanker.
    """

    ranker = NewsRanker()

    logger.info(
        "NewsRanker created."
    )

    return ranker