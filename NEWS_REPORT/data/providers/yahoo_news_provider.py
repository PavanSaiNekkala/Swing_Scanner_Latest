"""
Yahoo Finance News Provider

Responsibilities
----------------
- Retrieve Yahoo Finance news
- Normalize provider responses
- Map articles into NewsArticle domain models

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

import yfinance as yf

from config.logging_config import get_logger

from market.models import (
    NewsArticle,
    StockIdentity,
)

logger = get_logger(__name__)

###############################################################################
# Yahoo Finance News Provider
###############################################################################


class YahooNewsProvider:
    """
    Retrieves news from Yahoo Finance.
    """

    provider_name = "Yahoo Finance"

    provider_id = "yahoo_finance"

    enabled = True

    def __init__(
        self,
    ) -> None:

        logger.info(
            "%s initialized.",
            self.provider_name,
        )

###############################################################################
# Helpers
###############################################################################

    @staticmethod
    def parse_timestamp(
        timestamp: int | None,
    ) -> datetime:
        """
        Convert Yahoo timestamp into datetime.
        """

        if not timestamp:

            return datetime.utcnow()

        return datetime.fromtimestamp(
            timestamp,
        )

###############################################################################
# Fetch
###############################################################################

    def fetch(
        self,
        stock: StockIdentity,
        limit: int = 10,
    ) -> list[NewsArticle]:
        """
        Fetch Yahoo Finance news.
        """

        if not self.enabled:

            return []

        logger.info(
            "Fetching %s | %s",
            self.provider_name,
            stock.ticker,
        )

        ticker = yf.Ticker(
            f"{stock.ticker}.NS",
        )

        raw_news = getattr(
            ticker,
            "news",
            [],
        )

        articles: list[
            NewsArticle
        ] = []

        for item in raw_news[:limit]:

            content = item.get(
                "content",
                {},
            )

            provider = content.get(
                "provider",
                {},
            )

            articles.append(

                NewsArticle(

                    ticker=stock.ticker,

                    title=content.get(
                        "title",
                        "",
                    ),

                    source=provider.get(
                        "displayName",
                        self.provider_name,
                    ),

                    url=content.get(
                        "canonicalUrl",
                        {},
                    ).get(
                        "url",
                        "",
                    ),

                    published_at=self.parse_timestamp(
                        content.get(
                            "pubDate",
                        )
                    ),

                    summary=content.get(
                        "summary",
                        "",
                    ),

                    author=provider.get(
                        "displayName",
                    ),

                    image_url=content.get(
                        "thumbnail",
                        {},
                    ).get(
                        "originalUrl",
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


def build_yahoo_news_provider(
) -> YahooNewsProvider:
    """
    Factory for YahooNewsProvider.
    """

    provider = YahooNewsProvider()

    logger.info(
        "YahooNewsProvider created."
    )

    return provider