"""
Google News Provider

Responsibilities
----------------
- Retrieve Google News RSS articles
- Normalize provider responses
- Map articles into NewsArticle domain models
- Filter articles by ticker/company

This provider performs NO:
- AI summarization
- Deduplication
- Ranking

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

from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser

from config.logging_config import get_logger

from market.models import (
    NewsArticle,
    StockIdentity,
)

logger = get_logger(__name__)


###############################################################################
# Google News Provider
###############################################################################


class GoogleNewsProvider:
    """
    Retrieves news from Google News RSS.
    """

    provider_name = "Google News"

    provider_id = "google_news"

    enabled = True

    BASE_URL = (
        "https://news.google.com/rss/search?"
        "q={query}"
        "&hl=en-IN"
        "&gl=IN"
        "&ceid=IN:en"
    )

    def __init__(
        self,
        timeout: int = 20,
    ) -> None:

        self.timeout = timeout

        logger.info(
            "%s initialized.",
            self.provider_name,
        )

###############################################################################
# RSS URL
###############################################################################

    def build_url(
        self,
        stock: StockIdentity,
    ) -> str:
        """
        Build Google News RSS URL.
        """

        query = quote(
            f'"{stock.company_name}" OR {stock.ticker}'
        )

        return self.BASE_URL.format(
            query=query,
        )

###############################################################################
# Parsing
###############################################################################

    @staticmethod
    def parse_datetime(
        value: str | None,
    ) -> datetime:
        """
        Convert RSS timestamp.
        """

        if not value:

            return datetime.utcnow()

        try:

            return parsedate_to_datetime(
                value,
            )

        except Exception:

            return datetime.utcnow()

###############################################################################
# Fetch
###############################################################################

    def fetch(
        self,
        stock: StockIdentity,
        limit: int = 10,
    ) -> list[NewsArticle]:
        """
        Fetch news for one stock.
        """

        if not self.enabled:

            return []

        url = self.build_url(
            stock,
        )

        logger.info(
            "Fetching %s | %s",
            self.provider_name,
            stock.ticker,
        )

        feed = feedparser.parse(
            url,
        )

        articles: list[
            NewsArticle
        ] = []

        for entry in feed.entries[:limit]:

            articles.append(

                NewsArticle(

                    ticker=stock.ticker,

                    title=entry.get(
                        "title",
                        "",
                    ),

                    source=(
                        entry.get(
                            "source",
                            {},
                        ).get(
                            "title",
                            self.provider_name,
                        )
                        if isinstance(
                            entry.get(
                                "source",
                            ),
                            dict,
                        )
                        else self.provider_name
                    ),

                    url=entry.get(
                        "link",
                        "",
                    ),

                    published_at=self.parse_datetime(
                        entry.get(
                            "published",
                        )
                    ),

                    summary=entry.get(
                        "summary",
                        "",
                    ),

                )

            )

        logger.info(
            "%s -> %d articles",
            stock.ticker,
            len(articles),
        )

        return articles


###############################################################################
# Factory
###############################################################################


def build_google_news_provider(
    timeout: int = 20,
) -> GoogleNewsProvider:
    """
    Factory for GoogleNewsProvider.
    """

    provider = GoogleNewsProvider(
        timeout=timeout,
    )

    logger.info(
        "GoogleNewsProvider created."
    )

    return provider