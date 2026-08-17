"""
Institutional News Summarizer

Responsibilities
----------------
- Generate institutional-quality summaries
- Summarize Top 5 ranked articles per stock
- Produce investment-ready insights
- Support multiple AI providers
- Validate AI responses

This module intentionally DOES NOT:
    - Fetch news
    - Rank news
    - Deduplicate news
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

import json
import time

from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from typing import Any

from config.logging_config import get_logger
from config.settings import settings

from market.models import (
    NewsArticle,
    NewsReport,
    StockNews,
)

logger = get_logger(__name__)

###############################################################################
# Configuration
###############################################################################

MAX_INPUT_ARTICLES = 5

MAX_RETRIES = 3

###############################################################################
# AI Interface
###############################################################################

class AIClient(ABC):
    """
    Abstract AI provider.
    """

    @abstractmethod
    def summarize(
        self,
        prompt: str,
    ) -> str:
        """
        Execute LLM request.
        """


###############################################################################
# AI Interface
###############################################################################

class AIClient(ABC):
    """
    Abstract AI provider.
    """

    @abstractmethod
    def summarize(
        self,
        prompt: str,
    ) -> str:
        """
        Execute LLM request.
        """


###############################################################################
# Default AI Client
###############################################################################

class DefaultAIClient(AIClient):
    """
    Default AI client.

    Replace this implementation with OpenAI,
    Gemini or Ollama later.
    """

    def summarize(
        self,
        prompt: str,
    ) -> str:

        return json.dumps(
            {
                "executive_summary":
                    "AI summarization is not configured.",
                "sentiment":
                    "Neutral",
                "bullish_points": [],
                "bearish_points": [],
                "key_events": [],
                "confidence": 0,
            }
        )



###############################################################################
# Prompt Builder
###############################################################################


class PromptBuilder:
    """
    Builds prompts for institutional summarization.
    """

    SYSTEM_PROMPT = """
You are a senior equity research analyst.

Your job is to summarize company-specific financial news.

Rules

- Do not hallucinate.
- Use only supplied information.
- Focus on investment implications.
- Keep the summary factual.
- Use professional institutional language.

Return JSON only.
"""

    @classmethod
    def build(
        cls,
        stock: StockNews,
    ) -> str:

        news_blocks: list[str] = []

        for index, article in enumerate(
            stock.articles[:MAX_INPUT_ARTICLES],
            start=1,
        ):

            news_blocks.append(
                f"""
Article {index}

Headline:
{article.title}

Source:
{article.source}

Summary:
{article.summary}
"""
            )

        prompt = f"""
{cls.SYSTEM_PROMPT}

Ticker:
{stock.ticker}

Company:
{stock.company_name}

Articles

{"".join(news_blocks)}

Return JSON

{{
    "executive_summary": "...",
    "sentiment": "...",
    "bullish_points": [],
    "bearish_points": [],
    "key_events": [],
    "confidence": 0
}}
"""

        return prompt.strip()

###############################################################################
# Response Validator
###############################################################################


class ResponseValidator:
    """
    Validates AI output.
    """

    REQUIRED_FIELDS = {

        "executive_summary",

        "sentiment",

        "bullish_points",

        "bearish_points",

        "key_events",

        "confidence",

    }

    @classmethod
    def validate(
        cls,
        response: dict[str, Any],
    ) -> bool:

        return cls.REQUIRED_FIELDS.issubset(
            response.keys(),
        )

###############################################################################
# News Summarizer
###############################################################################


class NewsSummarizer:
    """
    Institutional AI summarizer.
    """

    def __init__(
        self,
        client: AIClient,
    ) -> None:

        self.client = client

        self.statistics = defaultdict(int)

        self.start_time = 0.0

        logger.info(
            "NewsSummarizer initialized."
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
# JSON Parsing
###############################################################################

    @staticmethod
    def parse_response(
        response: str,
    ) -> dict[str, Any]:
        """
        Parse AI JSON response.
        """

        return json.loads(
            response,
        )

###############################################################################
# Prompt Generation
###############################################################################

    def build_prompt(
        self,
        stock: StockNews,
    ) -> str:
        """
        Generate prompt for one stock.
        """

        return PromptBuilder.build(
            stock,
        )

###############################################################################
# AI Invocation
###############################################################################

    def call_ai(
        self,
        prompt: str,
    ) -> dict[str, Any]:
        """
        Execute AI request with retry logic.
        """

        last_exception: Exception | None = None

        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):

            try:

                logger.debug(
                    "AI request attempt %d/%d",
                    attempt,
                    MAX_RETRIES,
                )

                raw_response = self.client.summarize(
                    prompt,
                )

                parsed = self.parse_response(
                    raw_response,
                )

                if not ResponseValidator.validate(
                    parsed,
                ):

                    raise ValueError(
                        "AI returned an invalid JSON structure."
                    )

                self.increment(
                    "successful_requests",
                )

                return parsed

            except Exception as exc:

                last_exception = exc

                self.increment(
                    "failed_requests",
                )

                logger.warning(
                    "AI request failed (%d/%d): %s",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )

                time.sleep(
                    attempt,
                )

        raise RuntimeError(
            "AI summarization failed after retries."
        ) from last_exception


###############################################################################
# Default Fallback Summary
###############################################################################

    @staticmethod
    def fallback_summary(
        stock: StockNews,
    ) -> dict[str, Any]:
        """
        Fallback response if AI fails.
        """

        return {

            "executive_summary": (
                "Automatic AI summary could not "
                "be generated for this stock."
            ),

            "sentiment": "Neutral",

            "bullish_points": [],

            "bearish_points": [],

            "key_events": [

                article.title

                for article in stock.articles[:3]

            ],

            "confidence": 0,

        }


###############################################################################
# Apply Summary
###############################################################################

    @staticmethod
    def apply_summary(
        stock: StockNews,
        summary: dict[str, Any],
    ) -> StockNews:
        """
        Attach AI summary to StockNews.
        """

        print("=" * 80)
        print(type(stock))
        print(stock)
        print(stock.__class__)
        print(stock.__class__.__module__)
        print(stock.__class__.__name__)
        print(stock.__class__.__slots__)
        print(stock.__class__.__dataclass_fields__.keys())
        print(hasattr(stock, "bullish_points"))
        print("=" * 80)

        stock.executive_summary = summary.get(
            "executive_summary",
            "",
        )

        stock.sentiment = summary.get(
            "sentiment",
            "Neutral",
        )

        logger.info(type(stock))
        logger.info(stock.__dict__ if hasattr(stock, "__dict__") else stock)
        logger.info(getattr(stock, "__slots__", None))
        logger.info(dir(stock))

        stock.bullish_points = summary.get(
            "bullish_points",
            [],
        )

        stock.bearish_points = summary.get(
            "bearish_points",
            [],
        )

        stock.key_events = summary.get(
            "key_events",
            [],
        )

        stock.confidence = summary.get(
            "confidence",
            0,
        )

        return stock


###############################################################################
# Summarize One Stock
###############################################################################

    def summarize_stock(
        self,
        stock: StockNews,
    ) -> StockNews:
        """
        Generate AI summary for one stock.
        """

        logger.info(
            "Summarizing %s",
            stock.ticker,
        )

        prompt = self.build_prompt(
            stock,
        )

        try:

            summary = self.call_ai(
                prompt,
            )

        except Exception:

            logger.exception(
                "AI summarization failed for %s",
                stock.ticker,
            )

            summary = self.fallback_summary(
                stock,
            )

            self.increment(
                "fallback_used",
            )

        summarized = self.apply_summary(
            stock,
            summary,
        )

        self.increment(
            "stocks_summarized",
        )

        return summarized


###############################################################################
# Batch Summarization
###############################################################################

    def summarize_many(
        self,
        stocks: list[StockNews],
    ) -> list[StockNews]:
        """
        Summarize multiple stocks sequentially.

        (Parallel execution can be introduced later
        with provider-specific rate limiting.)
        """

        logger.info(
            "Summarizing %d stocks.",
            len(stocks),
        )

        summarized: list[
            StockNews
        ] = []

        for stock in stocks:

            try:

                summarized.append(
                    self.summarize_stock(
                        stock,
                    )
                )

            except Exception:

                logger.exception(
                    "Failed summarizing %s",
                    stock.ticker,
                )

                self.increment(
                    "failed_stocks",
                )

        return summarized

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
        Build summarized NewsReport.
        """

        summarized = NewsReport()

        summarized.gainers_news = gainers

        summarized.losers_news = losers

        summarized.total_articles = sum(
            len(stock.articles)
            for stock in gainers + losers
        )

        return summarized

###############################################################################
# Public Pipeline
###############################################################################

    def summarize(
        self,
        report: NewsReport,
    ) -> NewsReport:
        """
        Execute the complete AI summarization pipeline.
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "Starting News Summarization Pipeline"
        )

        logger.info(
            "=" * 80
        )

        self.reset_statistics()

        #######################################################################
        # Summarize Gainers
        #######################################################################

        logger.info(
            "Summarizing %d gainers.",
            len(
                report.gainers_news,
            ),
        )

        summarized_gainers = self.summarize_many(
            report.gainers_news,
        )

        #######################################################################
        # Summarize Losers
        #######################################################################

        logger.info(
            "Summarizing %d losers.",
            len(
                report.losers_news,
            ),
        )

        summarized_losers = self.summarize_many(
            report.losers_news,
        )

        #######################################################################
        # Build Final Report
        #######################################################################

        summarized_report = self.build_report(
            report=report,
            gainers=summarized_gainers,
            losers=summarized_losers,
        )

        #######################################################################
        # Statistics
        #######################################################################

        self.log_statistics(
            summarized_report,
        )

        logger.info(
            "=" * 80
        )

        logger.info(
            "News Summarization Completed"
        )

        logger.info(
            "=" * 80
        )

        return summarized_report

###############################################################################
# Statistics
###############################################################################

    def log_statistics(
        self,
        report: NewsReport,
    ) -> None:
        """
        Log summarization statistics.
        """

        logger.info(
            "Execution Summary"
        )

        logger.info(
            "-" * 80
        )

        logger.info(
            "Stocks Summarized   : %d",
            self.statistics.get(
                "stocks_summarized",
                0,
            ),
        )

        logger.info(
            "Successful AI Calls : %d",
            self.statistics.get(
                "successful_requests",
                0,
            ),
        )

        logger.info(
            "Failed AI Calls     : %d",
            self.statistics.get(
                "failed_requests",
                0,
            ),
        )

        logger.info(
            "Fallbacks Used      : %d",
            self.statistics.get(
                "fallback_used",
                0,
            ),
        )

        logger.info(
            "Failed Stocks       : %d",
            self.statistics.get(
                "failed_stocks",
                0,
            ),
        )

        logger.info(
            "Total Articles      : %d",
            report.total_articles,
        )

        logger.info(
            "Execution Time      : %.2f sec",
            self.elapsed(),
        )


###############################################################################
# Factory
###############################################################################

def build_news_summarizer(
    client: AIClient | None = None,
) -> NewsSummarizer:
    """
    Factory for NewsSummarizer.
    """

    if client is None:

        client = DefaultAIClient()

    summarizer = NewsSummarizer(
        client=client,
    )

    logger.info(
        "NewsSummarizer created."
    )

    return summarizer