"""
Google News RSS Provider

Fetches dividend-related news from Google News RSS.
"""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from typing import List

import feedparser
import requests
from bs4 import BeautifulSoup

from app.models.company import Company
from app.models.news import NewsArticle
from app.providers.base_provider import BaseProvider


class GoogleRSSProvider(
    BaseProvider,
):

    PROVIDER = "Google RSS"

    RSS_URL = (
        "https://news.google.com/rss/search?"
        "q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    )

    USER_AGENT = (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/138.0 Safari/537.36"
    )

    KEYWORDS = [

        "dividend",

        "interim dividend",

        "final dividend",

        "special dividend",

        "cash dividend",

        "record date",

        "ex-dividend",

        "ex dividend",

        "board recommends dividend",

        "board approves dividend",

        "payout",

    ]

    # ---------------------------------------------------------
    # Public
    # ---------------------------------------------------------

    def get_news(
        self,
        company: Company,
    ) -> List[NewsArticle]:

        try:

            company_name = (
                company.company_name
                or company.symbol
            )

            query = quote_plus(

                f"{company_name} dividend"

            )

            url = self.RSS_URL.format(
                query=query
            )


            response = requests.get(

                url,

                headers={
                    "User-Agent":
                    self.USER_AGENT
                },

                timeout=15,

            )

            response.raise_for_status()

            feed = feedparser.parse(
                response.content
            )

            articles: List[
                NewsArticle
            ] = []

            seen = set()

            for entry in feed.entries:

                headline = (
                    entry.get("title")
                    or ""
                ).strip()

                summary = self._clean_html(

                    entry.get("summary")
                    or ""

                )

                text = (

                    headline
                    + " "
                    + summary

                ).lower()

                if not any(

                    keyword in text

                    for keyword
                    in self.KEYWORDS

                ):

                    continue

                if (

                    company_name.lower()

                    not in text

                ):

                    continue

                url = (
                    entry.get("link")
                    or ""
                ).strip()

                if (

                    not url

                    or url in seen

                ):

                    continue

                seen.add(
                    url
                )

                articles.append(

                    NewsArticle(

                        symbol=company.symbol,

                        ticker=company.symbol,

                        stock=company.symbol,

                        company_name=company_name,

                        headline=headline,

                        summary=summary,

                        source=(

                            entry.source.get(
                                "title"
                            )

                            if hasattr(
                                entry,
                                "source",
                            )

                            else None

                        ),

                        url=url,

                        published_at=self._parse_date(

                            entry.get(
                                "published"
                            )

                        ),

                        category="Dividend",

                        provider=self.PROVIDER,

                    )

                )

            articles.sort(

                key=lambda x:
                x.published_at,

                reverse=True,

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

        try:

            requests.get(

                "https://news.google.com",

                timeout=5,

            )

            return True

        except Exception:

            return False

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _clean_html(
        text: str,
    ) -> str:

        if not text:

            return ""

        return BeautifulSoup(

            text,

            "html.parser",

        ).get_text(

            " ",

            strip=True,

        )

    @staticmethod
    def _parse_date(
        value: str | None,
    ) -> datetime:

        if not value:

            return datetime.utcnow()

        try:

            dt = parsedate_to_datetime(
                value
            )

            if dt.tzinfo:

                dt = dt.replace(
                    tzinfo=None
                )

            return dt

        except Exception:

            return datetime.utcnow()