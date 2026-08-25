"""
NewsAPI Provider

Fetches dividend-related news using NewsAPI.org.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List

from newsapi import NewsApiClient

from app.models.news import NewsArticle
from app.providers.base_provider import BaseProvider


class NewsAPIProvider(
    BaseProvider,
):

    PROVIDER = "NewsAPI"

    def __init__(self) -> None:

        super().__init__()

        api_key = os.getenv(
            "NEWSAPI_KEY"
        )

        self.client = (

            NewsApiClient(
                api_key=api_key
            )

            if api_key

            else None

        )

    # ---------------------------------------------------------
    # Public
    # ---------------------------------------------------------

    def get_news(
        self,
        company: str,
    ) -> List[NewsArticle]:

        if self.client is None:

            return []

        try:

            response = self.client.get_everything(

                q=f'"{company}" dividend',

                language="en",

                sort_by="publishedAt",

                page_size=10,

            )

            articles: List[
                NewsArticle
            ] = []

            for item in response.get(

                "articles",

                [],

            ):

                articles.append(

                    NewsArticle(

                        symbol=company,

                        ticker=company,

                        stock=company,

                        company_name=company,

                        headline=item.get(
                            "title"
                        ),

                        summary=item.get(
                            "description"
                        ),

                        source=item[
                            "source"
                        ].get(
                            "name"
                        ),

                        url=item.get(
                            "url"
                        ),

                        published_at=datetime.fromisoformat(

                            item[
                                "publishedAt"
                            ].replace(

                                "Z",

                                "+00:00",

                            )

                        ).replace(
                            tzinfo=None
                        ),

                        category="Dividend",

                        provider=self.PROVIDER,

                    )

                )

            return articles

        except Exception as ex:

            self.logger.exception(
                ex
            )

            return []

    # ---------------------------------------------------------
    # Health
    # ---------------------------------------------------------

    def health_check(
        self,
    ) -> bool:

        return self.client is not None