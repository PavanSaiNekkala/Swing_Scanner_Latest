"""
Institutional News Pipeline

Responsibilities
----------------
- Orchestrate the complete news workflow
- Coordinate all news services
- Produce a fully summarized NewsReport
- Measure execution statistics

Workflow
--------
MarketReport
        │
        ▼
NewsCollector
        │
        ▼
NewsDeduplicator
        │
        ▼
NewsRanker
        │
        ▼
NewsSummarizer
        │
        ▼
NewsReport

This module intentionally DOES NOT:
    - Fetch APIs directly
    - Call AI models
    - Rank news
    - Remove duplicates
    - Export Excel

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

import time

from collections import defaultdict

from config.logging_config import get_logger

from market.models import (
    MarketReport,
    NewsReport,
)

from news.collector import (
    NewsCollector,
)

from news.deduplicator import (
    NewsDeduplicator,
    build_news_deduplicator,
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
# News Pipeline
###############################################################################


class NewsPipeline:
    """
    Institutional orchestration layer.

    Coordinates all news modules without implementing
    business logic.
    """

    def __init__(
        self,
        collector: NewsCollector,
        deduplicator: NewsDeduplicator,
        ranker: NewsRanker,
        summarizer: NewsSummarizer,
    ) -> None:

        self.collector = collector

        self.deduplicator = deduplicator

        self.ranker = ranker

        self.summarizer = summarizer

        self.statistics = defaultdict(int)

        self.start_time = 0.0

        logger.info(
            "NewsPipeline initialized."
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
# Collection Stage
###############################################################################

    def collect_news(
        self,
        market_report: MarketReport,
    ) -> NewsReport:
        """
        Execute news collection.
        """

        logger.info(
            "Stage 1/4 : Collecting news."
        )

        report = self.collector.collect(
            market_report,
        )

        self.increment(
            "collection_runs",
        )

        return report

###############################################################################
# Deduplication Stage
###############################################################################

    def deduplicate_news(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Execute news deduplication.
        """

        logger.info(
            "Stage 2/4 : Deduplicating news."
        )

        report = self.deduplicator.deduplicate(
            report,
        )

        self.increment(
            "deduplication_runs",
        )

        return report

###############################################################################
# Ranking Stage
###############################################################################

    def rank_news(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Execute article ranking.
        """

        logger.info(
            "Stage 3/4 : Ranking news."
        )

        report = self.ranker.rank(
            report,
        )

        self.increment(
            "ranking_runs",
        )

        return report

###############################################################################
# Summarization Stage
###############################################################################

    def summarize_news(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Execute AI summarization.
        """

        logger.info(
            "Stage 4/4 : Summarizing news."
        )

        report = self.summarizer.summarize(
            report,
        )

        self.increment(
            "summarization_runs",
        )

        return report


###############################################################################
# Execute Pipeline
###############################################################################

    def execute(
        self,
        market_report: MarketReport,
    ) -> NewsReport:
        """
        Execute the complete institutional news pipeline.

        Workflow
        --------
            MarketReport
                  │
                  ▼
           Collect News
                  │
                  ▼
         Deduplicate News
                  │
                  ▼
            Rank Articles
                  │
                  ▼
         Summarize Articles
                  │
                  ▼
             Final NewsReport
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "Starting News Pipeline"
        )

        logger.info(
            "=" * 80
        )

        self.reset_statistics()

        try:

            ###################################################################
            # Stage 1
            ###################################################################

            report = self.collect_news(
                market_report,
            )

            ###################################################################
            # Stage 2
            ###################################################################

            report = self.deduplicate_news(
                report,
            )

            ###################################################################
            # Stage 3
            ###################################################################

            report = self.rank_news(
                report,
            )

            ###################################################################
            # Stage 4
            ###################################################################

            report = self.summarize_news(
                report,
            )

            self.increment(
                "successful_runs",
            )

            self.log_statistics(
                report,
            )

            logger.info(
                "=" * 80
            )

            logger.info(
                "News Pipeline Completed Successfully"
            )

            logger.info(
                "=" * 80
            )

            return report

        except Exception:

            self.increment(
                "failed_runs",
            )

            logger.exception(
                "News pipeline failed."
            )

            raise

###############################################################################
# Statistics
###############################################################################

    def log_statistics(
        self,
        report: NewsReport,
    ) -> None:
        """
        Log execution statistics.
        """

        gainers = len(
            report.gainers_news
        )

        losers = len(
            report.losers_news
        )

        total_articles = report.total_articles

        logger.info(
            "Execution Summary"
        )

        logger.info(
            "-" * 80
        )

        logger.info(
            "Collection Runs      : %d",
            self.statistics.get(
                "collection_runs",
                0,
            ),
        )

        logger.info(
            "Deduplication Runs   : %d",
            self.statistics.get(
                "deduplication_runs",
                0,
            ),
        )

        logger.info(
            "Ranking Runs         : %d",
            self.statistics.get(
                "ranking_runs",
                0,
            ),
        )

        logger.info(
            "Summarization Runs   : %d",
            self.statistics.get(
                "summarization_runs",
                0,
            ),
        )

        logger.info(
            "Successful Runs      : %d",
            self.statistics.get(
                "successful_runs",
                0,
            ),
        )

        logger.info(
            "Failed Runs          : %d",
            self.statistics.get(
                "failed_runs",
                0,
            ),
        )

        logger.info(
            "Top Gainers          : %d",
            gainers,
        )

        logger.info(
            "Top Losers           : %d",
            losers,
        )

        logger.info(
            "Total Articles       : %d",
            total_articles,
        )

        logger.info(
            "Execution Time       : %.2f sec",
            self.elapsed(),
        )


###############################################################################
# Factory
###############################################################################

def build_news_pipeline(
    collector: NewsCollector,
) -> NewsPipeline:
    """
    Factory for NewsPipeline.
    """

    pipeline = NewsPipeline(
        collector=collector,
        deduplicator=build_news_deduplicator(),
        ranker=build_news_ranker(),
        summarizer=build_news_summarizer(),
    )

    logger.info(
        "NewsPipeline created."
    )

    return pipeline