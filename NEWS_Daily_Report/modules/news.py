"""
===============================================================================
File: news.py

Description:
    Fetches recent news for NSE stocks using Google News RSS
    and enriches report DataFrames.

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import List
from urllib.parse import quote

import feedparser
import pandas as pd

from modules.constants import (
    MarketColumns,
    NewsColumns,
    NEWS_LOOKBACK_DAYS,
    TOP_NEWS,
)

from modules.logger import logger
from modules.validators import validate_dataframe
from modules.datetime_utils import now_ist

###############################################################################
# Constants
###############################################################################

TOP_NEWS_COUNT = TOP_NEWS


###############################################################################
# News Service
###############################################################################


class NewsService:

    def __init__(self):

        self.cutoff = now_ist() - timedelta(
            days=NEWS_LOOKBACK_DAYS
        )

    ###########################################################################

    def fetch_news(
        self,
        symbol: str,
        company: str,
    ) -> List[dict]:
        """
        Fetch recent Google News articles.
        """

        query = (
            f'"{company}" OR "{symbol.replace(".NS", "")}" '
            "stock OR shares"
        )

        url = (
            "https://news.google.com/rss/search?"
            f"q={quote(query)}"
            "&hl=en-IN"
            "&gl=IN"
            "&ceid=IN:en"
        )

        try:

            feed = feedparser.parse(url)

            news = []

            for entry in feed.entries:

                try:

                    published = parsedate_to_datetime(
                        entry.published
                    )

                except Exception:

                    published = None

                news.append(
                    {
                        "title": entry.title.strip(),
                        "published": published,
                        "link": entry.link,
                    }
                )

            logger.info(
                "%s : %d Google News articles",
                symbol,
                len(news),
            )

            return news

        except Exception as exc:

            logger.warning(
                "Unable to fetch Google News for %s : %s",
                symbol,
                exc,
            )

            return []

    ###########################################################################

    def filter_recent(
        self,
        news: List[dict],
    ) -> List[dict]:
        """
        Keep only articles within lookback period.
        """

        recent = []

        for article in news:

            published = article.get("published")

            if published is None:
                continue

            if published.tzinfo is not None:

                cutoff = self.cutoff.replace(
                    tzinfo=published.tzinfo,
                )

            else:

                cutoff = self.cutoff

            if published >= cutoff:

                recent.append(article)

        return recent

    ###########################################################################

    def get_top_headline(
        self,
        news: List[dict],
    ) -> str:
        """
        Best headline according to Google relevance.
        """

        if not news:
            return ""

        return news[0]["title"]

    ###########################################################################

    def get_latest_news(
        self,
        news: List[dict],
    ) -> str:
        """
        Latest published article.
        """

        if not news:
            return ""

        latest = max(
            news,
            key=lambda x: x["published"],
        )

        return latest["title"]

    ###########################################################################

    def get_top_news(
        self,
        news: List[dict],
        exclude: str,
    ) -> list[str]:
        """
        Return Top 3 unique news excluding Top Headline.
        """

        headlines = []

        seen = {exclude.lower().strip()}

        #
        # Google RSS already ranks by relevance.
        #

        for article in news:

            title = article["title"].strip()

            if not title:
                continue

            key = title.lower()

            if key in seen:
                continue

            seen.add(key)

            headlines.append(title)

            if len(headlines) == TOP_NEWS_COUNT:
                break

        while len(headlines) < TOP_NEWS_COUNT:

            headlines.append("")

        return headlines

    ###########################################################################

    def enrich_dataframe(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:

        validate_dataframe(df)

        df = df.copy()

        df[NewsColumns.HEADLINE.value] = ""
        df[NewsColumns.LATEST.value] = ""

        for i in range(1, TOP_NEWS_COUNT + 1):

            df[f"News {i}"] = ""

        for idx in df.index:

            symbol = df.loc[
                idx,
                MarketColumns.SYMBOL.value,
            ]

            company = df.loc[
                idx,
                MarketColumns.COMPANY.value,
            ]

            logger.info(
                "Fetching Google News for %s (%s)",
                company,
                symbol,
            )

            all_news = self.fetch_news(
                symbol=symbol,
                company=company,
            )

            recent_news = self.filter_recent(
                all_news,
            )

            logger.info(
                "%s -> Total Articles = %d | Recent Articles = %d",
                symbol,
                len(all_news),
                len(recent_news),
            )

            #
            # If no articles are found within the lookback period,
            # fall back to the latest available Google News.
            #

            if not recent_news:

                logger.info(
                    "%s : No news found in last %d days. Using latest available articles.",
                    symbol,
                    NEWS_LOOKBACK_DAYS,
                )

                recent_news = all_news

            #
            # Still nothing? Skip this stock.
            #

            if not recent_news:

                logger.warning(
                    "%s : No Google News available.",
                    symbol,
                )

                continue

            #
            # Best headline (Google relevance)
            #

            top_headline = self.get_top_headline(
                recent_news,
            )

            #
            # Latest article
            #

            latest_news = self.get_latest_news(
                recent_news,
            )

            #
            # Top 3 unique news excluding headline
            #

            top_news = self.get_top_news(
                recent_news,
                exclude=top_headline,
            )

            #
            # Populate dataframe
            #

            df.loc[
                idx,
                NewsColumns.HEADLINE.value,
            ] = top_headline

            df.loc[
                idx,
                NewsColumns.LATEST.value,
            ] = latest_news

            for i, headline in enumerate(
                top_news,
                start=1,
            ):

                df.loc[
                    idx,
                    f"News {i}",
                ] = headline

        logger.info(
            "News enrichment completed for %d stocks.",
            len(df),
        )

        logger.info(
            "\n%s",
            df[
                [
                    "Symbol",
                    "Top Headline",
                    "News 1",
                ]
            ].head(5).to_string(),
        )

        return df


###############################################################################
# Public API
###############################################################################


def enrich_news(
    df: pd.DataFrame,
) -> pd.DataFrame:

    service = NewsService()

    return service.enrich_dataframe(df)