from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import requests

from config.config import (
    MARKET,
    NEWS_LOOKBACK_DAYS,
)
from config.config import (
    MAX_NEWS_PER_STOCK,
)
from config.logging_config import logger
from config.timezone import IST
from config.timezone import now_ist


###############################################################################
# CONFIGURATION
###############################################################################

MARKETAUX_API_URL = (
    "https://api.marketaux.com/v1/news/all"
)

DEFAULT_TIMEOUT = 30

DEFAULT_RETRIES = 3

DEFAULT_BACKOFF = 2

MARKETAUX_BATCH_SIZE = 20

MARKETAUX_MAX_WORKERS = 1

MARKETAUX_LANGUAGE = "en"

MARKETAUX_COUNTRY = "in"


###############################################################################
# EXCEPTIONS
###############################################################################

class MarketauxNewsError(Exception):
    """Base Marketaux news exception."""


class MarketauxAuthenticationError(
    MarketauxNewsError,
):
    """Raised when the API token is invalid."""


class MarketauxConnectionError(
    MarketauxNewsError,
):
    """Raised when Marketaux cannot be reached."""


class MarketauxRateLimitError(
    MarketauxNewsError,
):
    """Raised when Marketaux rate limit is reached."""


###############################################################################
# PROVIDER
###############################################################################

class MarketauxNews:
    """
    Marketaux provider for the full NSE news universe.

    Google News remains responsible for the normal
    40-stock market report.

    Marketaux is responsible for the CSV universe scan.
    """

    def __init__(
        self,
        api_token: Optional[str],
    ) -> None:

        if not api_token:

            raise MarketauxAuthenticationError(
                "MARKETAUX_API_KEY is not configured."
            )

        self.api_token = api_token

        self.timestamp = now_ist()

        self.session = requests.Session()

        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": (
                    "NSE-Market-Report/"
                    "1.0"
                ),
            }
        )

        logger.info(
            "[MARKETAUX] Provider initialized."
        )

    ###########################################################################
    # DATE RANGE
    ###########################################################################

    @staticmethod
    def _date_range() -> tuple[str, str]:
        """
        Return UTC-compatible ISO date strings for
        the configured news lookback window.
        """

        now = now_ist()

        start = (
            now
            - timedelta(
                days=NEWS_LOOKBACK_DAYS
            )
        )

        return (
            start.astimezone(IST).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            now.astimezone(IST).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        )

    ###########################################################################
    # REQUEST
    ###########################################################################

    def _request(
        self,
        symbols: List[str],
    ) -> Dict[str, Any]:

        if not symbols:
            return {
                "data": [],
            }

        published_after, published_before = (
            self._date_range()
        )

        params = {
            "api_token": self.api_token,

            "symbols": ",".join(
                symbols
            ),

            "countries": MARKETAUX_COUNTRY,

            "entity_types": "equity",

            "filter_entities": "true",

            "group_similar": "true",

            "language": MARKETAUX_LANGUAGE,

            "published_after":
                published_after,

            "published_before":
                published_before,

            "limit":
                MAX_NEWS_PER_STOCK * len(symbols),

        }

        logger.info(
            "[MARKETAUX] Requesting "
            "%d symbols.",
            len(symbols),
        )

        for attempt in range(
            1,
            DEFAULT_RETRIES + 1,
        ):

            try:

                response = self.session.get(
                    MARKETAUX_API_URL,
                    params=params,
                    timeout=DEFAULT_TIMEOUT,
                )

                if response.status_code == 401:

                    raise MarketauxAuthenticationError(
                        "Invalid Marketaux API token."
                    )

                if response.status_code == 429:

                    raise MarketauxRateLimitError(
                        "Marketaux rate limit reached."
                    )

                if response.status_code >= 500:

                    raise MarketauxConnectionError(
                        f"Marketaux server error: "
                        f"{response.status_code}"
                    )

                response.raise_for_status()

                payload = response.json()

                if not isinstance(
                    payload,
                    dict,
                ):

                    raise MarketauxNewsError(
                        "Invalid Marketaux response."
                    )

                return payload

            except (
                MarketauxAuthenticationError,
                MarketauxRateLimitError,
            ):

                raise

            except (
                requests.Timeout,
                requests.ConnectionError,
                MarketauxConnectionError,
            ) as ex:

                logger.warning(
                    "[MARKETAUX] Request failed "
                    "(%d/%d): %s",
                    attempt,
                    DEFAULT_RETRIES,
                    ex,
                )

                if (
                    attempt
                    < DEFAULT_RETRIES
                ):

                    wait_seconds = (
                        DEFAULT_BACKOFF
                        ** attempt
                    )

                    import time

                    time.sleep(
                        wait_seconds
                    )

            except Exception as ex:

                logger.exception(
                    "[MARKETAUX] "
                    "Unexpected request error."
                )

                if (
                    attempt
                    >= DEFAULT_RETRIES
                ):

                    raise

        raise MarketauxConnectionError(
            "Unable to retrieve Marketaux news."
        )

    ###########################################################################
    # ARTICLE PARSING
    ###########################################################################

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> Optional[datetime]:

        if not value:
            return None

        try:

            parsed = datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            )

            if parsed.tzinfo is None:

                parsed = parsed.replace(
                    tzinfo=IST
                )

            else:

                parsed = parsed.astimezone(
                    IST
                )

            return parsed

        except (
            ValueError,
            TypeError,
        ):

            return None

    ###########################################################################
    # CONVERT ARTICLE
    ###########################################################################

    @staticmethod
    def _convert_article(
        article: Dict[str, Any],
    ) -> Dict[str, Any]:

        published = (
            MarketauxNews._parse_datetime(
                article.get(
                    "published_at"
                )
            )
        )

        entities = (
            article.get(
                "entities"
            )
            or []
        )

        return {
            "UUID":
                article.get(
                    "uuid"
                ),

            "Headline":
                article.get(
                    "title"
                ),

            "Description":
                article.get(
                    "description"
                ),

            "Snippet":
                article.get(
                    "snippet"
                ),

            "Headline Link":
                article.get(
                    "url"
                ),

            "Source":
                article.get(
                    "source"
                ),

            "Published":
                published,

            "Entities":
                entities,

            "Sentiment":
                article.get(
                    "sentiment_avg"
                ),
        }

    ###########################################################################
    # EXPAND BY SYMBOL
    ###########################################################################

    @staticmethod
    def _expand_articles(
        articles: List[Dict[str, Any]],
        requested_symbols: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:

        symbol_set = {
            symbol.strip().upper()
            for symbol in requested_symbols
        }

        news_map: Dict[
            str,
            List[Dict[str, Any]],
        ] = {
            symbol: []
            for symbol in symbol_set
        }

        cutoff = (
            now_ist()
            - timedelta(
                days=NEWS_LOOKBACK_DAYS
            )
        )

        for raw_article in articles:

            article = (
                MarketauxNews._convert_article(
                    raw_article
                )
            )

            published = article.get(
                "Published"
            )

            if (
                published is None
                or published < cutoff
            ):
                continue

            article_symbols = set()

            for entity in (
                article.get(
                    "Entities"
                )
                or []
            ):

                symbol = str(
                    entity.get(
                        "symbol",
                        "",
                    )
                ).strip().upper()

                if symbol:

                    article_symbols.add(
                        symbol
                    )

            matched_symbols = (
                article_symbols
                & symbol_set
            )

            for symbol in matched_symbols:

                news_map[
                    symbol
                ].append(
                    article
                )

        return news_map

    ###########################################################################
    # DEDUPLICATION
    ###########################################################################

    @staticmethod
    def _deduplicate(
        articles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        seen = set()

        cleaned = []

        for article in articles:

            key = (
                str(
                    article.get(
                        "UUID"
                    )
                    or ""
                ),
                str(
                    article.get(
                        "Headline Link"
                    )
                    or ""
                ),
                str(
                    article.get(
                        "Headline"
                    )
                    or ""
                ).strip().lower(),
            )

            if key in seen:
                continue

            seen.add(key)

            cleaned.append(
                article
            )

        return cleaned

    ###########################################################################
    # RANKING
    ###########################################################################

    @staticmethod
    def _score(
        article: Dict[str, Any],
        symbol: str,
    ) -> float:

        headline = str(
            article.get(
                "Headline"
            )
            or ""
        ).lower()

        description = str(
            article.get(
                "Description"
            )
            or ""
        ).lower()

        symbol_text = (
            symbol.lower()
        )

        score = 0.0

        if symbol_text in headline:
            score += 40

        if symbol_text in description:
            score += 20

        keywords = {
            "results": 25,
            "earnings": 25,
            "profit": 20,
            "loss": 20,
            "dividend": 18,
            "buyback": 18,
            "order": 15,
            "contract": 15,
            "merger": 15,
            "acquisition": 15,
            "guidance": 10,
            "board": 10,
            "nse": 5,
            "bse": 5,
        }

        text = (
            f"{headline} {description}"
        )

        for word, weight in (
            keywords.items()
        ):

            if word in text:
                score += weight

        return score

    ###########################################################################
    # BUILD STOCK RESULT
    ###########################################################################

    def _build_stock_result(
        self,
        symbol: str,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        articles = self._deduplicate(
            articles
        )

        articles.sort(
            key=lambda article: (
                self._score(
                    article,
                    symbol,
                ),
                article.get(
                    "Published"
                )
                or datetime.min.replace(
                    tzinfo=IST
                ),
            ),
            reverse=True,
        )

        top_articles = articles[
            :MAX_NEWS_PER_STOCK
        ]

        if not top_articles:

            return {
                "Symbol": symbol,
                "Company": None,
                "Top Headline": None,
                "Headline Link": None,
                "Description": None,
                "Source": None,
                "Published": None,
                "Recent News": [],
                "News Count": 0,
                "Provider": "Marketaux",
            }

        top = top_articles[0]

        return {
            "Symbol": symbol,
            "Company": None,
            "Top Headline":
                top.get("Headline"),
            "Headline Link":
                top.get("Headline Link"),
            "Description":
                top.get("Description"),
            "Source":
                top.get("Source"),
            "Published":
                top.get("Published"),
            "Recent News": [
                article.get(
                    "Headline"
                )
                for article in top_articles
                if article.get(
                    "Headline"
                )
            ],
            "News Count":
                len(top_articles),
            "Provider": "Marketaux",
        }

    ###########################################################################
    # BATCH SCAN
    ###########################################################################

    def fetch_many(
        self,
        stocks: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:

        if not stocks:
            return []

        symbols = []

        for stock in stocks:

            symbol = str(
                stock.get(
                    "Symbol",
                    "",
                )
            ).strip().upper()

            if symbol:
                symbols.append(
                    symbol
                )

        symbols = list(
            dict.fromkeys(
                symbols
            )
        )

        results = []

        #######################################################################
        # BATCH REQUESTS
        #######################################################################

        for start in range(
            0,
            len(symbols),
            MARKETAUX_BATCH_SIZE,
        ):

            batch = symbols[
                start:
                start
                + MARKETAUX_BATCH_SIZE
            ]

            logger.info(
                "[MARKETAUX] "
                "Batch %d-%d / %d",
                start + 1,
                min(
                    start
                    + MARKETAUX_BATCH_SIZE,
                    len(symbols),
                ),
                len(symbols),
            )

            payload = self._request(
                batch
            )

            articles = (
                payload.get(
                    "data",
                    []
                )
                or []
            )

            news_map = (
                self._expand_articles(
                    articles,
                    batch,
                )
            )

            for symbol in batch:

                results.append(
                    self._build_stock_result(
                        symbol,
                        news_map.get(
                            symbol,
                            [],
                        ),
                    )
                )

        return results

    ###########################################################################
    # HEALTH
    ###########################################################################

    def health(self) -> Dict[str, Any]:

        return {
            "provider": "Marketaux",
            "status": "ready",
            "timestamp": now_ist(),
        }

    ###########################################################################
    # CLOSE
    ###########################################################################

    def close(self) -> None:

        self.session.close()

        logger.info(
            "[MARKETAUX] Provider closed."
        )