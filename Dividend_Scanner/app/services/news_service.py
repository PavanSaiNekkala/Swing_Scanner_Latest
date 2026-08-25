"""
News Service
"""

from __future__ import annotations

from app.database.tables import NewsArticleTable
from app.providers.news.google_rss_provider import GoogleRSSProvider
from app.services.base_service import BaseService


class NewsService(BaseService):

    def __init__(
        self,
    ):
        super().__init__()

        self.provider = GoogleRSSProvider()

    def get(
        self,
        company,
    ):

        symbol = company.symbol

        cached = self.cache.get(
            "news",
            symbol,
        )

        if cached:
            return cached

        rows = self.repo.news.get(
            symbol,
        )

        if rows:

            self.cache.set(
                "news",
                symbol,
                rows,
            )

            return rows

        articles = self.provider.get_news(
            company,
        )

        if not articles:
            return []

        tables = []

        for article in articles:

            tables.append(

                NewsArticleTable(

                    symbol=article.symbol,

                    headline=article.headline,

                    summary=article.summary,

                    source=article.source,

                    provider=article.provider,

                    url=article.url,

                    published_at=article.published_at,

                    category=article.category,

                )

            )

        self.repo.news.save_many(
            tables,
        )

        self.cache.set(
            "news",
            symbol,
            articles,
        )

        return articles