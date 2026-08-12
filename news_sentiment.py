"""
===============================================================================
news_sentiment.py

Institutional Grade News Sentiment Engine
Version : 2.0
Python  : 3.11+

Public API (implemented later)

    fetch_news_score(...)

===============================================================================
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import random
import re
import threading
import time
import urllib.parse
import urllib.request

import xml.etree.ElementTree as ET

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

try:
    import yfinance as yf

    HAVE_YFINANCE = True
except Exception:
    HAVE_YFINANCE = False

try:
    import streamlit as st
except Exception:
    st = None


################################################################################
# Logging
################################################################################

LOGGER_NAME: Final = "news_sentiment"

logger = logging.getLogger(LOGGER_NAME)

if not logger.handlers:

    handler = logging.StreamHandler()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)

logger.setLevel(logging.INFO)

################################################################################
# Configuration
################################################################################


@dataclass(slots=True, frozen=True)
class Config:

    GOOGLE_MAX_ITEMS: int = 10

    LOOKBACK_DAYS: int = 3

    HTTP_TIMEOUT: int = 15

    CACHE_TTL: int = 3600

    MAX_RETRIES: int = 4

    BACKOFF: float = 1.5

    MAX_HEADLINES: int = 30

    RELEVANCE_THRESHOLD: float = 0.50


CONFIG = Config()

################################################################################
# Enums
################################################################################


class Source(str, Enum):

    YFINANCE = "yfinance"

    GOOGLE = "google"


class Sentiment(str, Enum):

    POSITIVE = "positive"

    NEGATIVE = "negative"

    NEUTRAL = "neutral"


################################################################################
# Dataclasses
################################################################################


@dataclass(slots=True)
class NewsArticle:

    title: str

    source: Source

    published: dt.datetime | None

    score: float = 0.0

    matched_terms: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SentimentResult:

    score: float

    confidence: float

    sentiment: Sentiment

    top_headline: str | None

    top_score: float

    matched_terms: list[str]

    articles: list[NewsArticle]


################################################################################
# Exceptions
################################################################################


class NewsSentimentError(Exception):
    """Base exception."""


class FetchError(NewsSentimentError):
    """Fetching failed."""


class ParseError(NewsSentimentError):
    """Parsing failed."""


################################################################################
# Retry Decorator
################################################################################


def retry(func):

    def wrapper(*args, **kwargs):

        last_exception = None

        for attempt in range(CONFIG.MAX_RETRIES):

            try:
                return func(*args, **kwargs)

            except Exception as exc:

                last_exception = exc

                delay = (
                    CONFIG.BACKOFF ** attempt
                ) + random.uniform(0.0, 0.30)

                logger.warning(
                    "%s failed (%s/%s). Retrying in %.2fs",
                    func.__name__,
                    attempt + 1,
                    CONFIG.MAX_RETRIES,
                    delay,
                )

                time.sleep(delay)

        raise FetchError(str(last_exception))

    return wrapper


################################################################################
# Thread-safe Cache
################################################################################

_cache: dict[str, tuple[float, Any]] = {}

_cache_lock = threading.RLock()


def cache_get(key: str):

    now = time.time()

    with _cache_lock:

        item = _cache.get(key)

        if item is None:
            return None

        expires, value = item

        if expires < now:

            _cache.pop(key, None)

            return None

        return value


def cache_put(key: str, value: Any):

    with _cache_lock:

        _cache[key] = (
            time.time() + CONFIG.CACHE_TTL,
            value,
        )


################################################################################
# Headline Deduplication
################################################################################


def normalize_title(title: str) -> str:
    """
    Normalize a headline for duplicate detection.
    """

    title = title.lower()

    title = re.sub(r"\s+", " ", title)

    title = re.sub(r"[^\w\s]", "", title)

    return title.strip()


################################################################################
# Utility Functions
################################################################################


def is_recent(
    published: dt.datetime | None,
    lookback_days: int,
) -> bool:

    if published is None:
        return True

    cutoff = (
        dt.datetime.now()
        - dt.timedelta(days=lookback_days)
    )

    return published.replace(
        tzinfo=None
    ) >= cutoff


def compress_score(raw_score: float) -> float:
    """
    Compress arbitrary sentiment into [-1,+1].
    """

    return math.tanh(raw_score / 4.0)


################################################################################
# RECENCY WEIGHT
################################################################################

def _recency_weight(
    published: dt.datetime | None,
) -> float:
    """
    Exponential decay.

    Today      -> 1.00

    1 day      -> 0.72

    2 days     -> 0.52

    3 days     -> 0.37

    Older      -> smaller impact
    """

    if published is None:
        return 0.60

    age_days = max(
        (
            dt.datetime.now()
            - published.replace(tzinfo=None)
        ).total_seconds()
        / 86400.0,
        0.0,
    )

    return math.exp(
        -0.33 * age_days
    )


################################################################################
# Positive Lexicon
################################################################################

POSITIVE_TERMS: Final = {

    r"\bupgrade[sd]?\b": 3,

    r"\bbuy call\b": 2,

    r"\boutperform\b": 2,

    r"\bbeats? estimates?\b": 4,

    r"\brecord profit\b": 3,

    r"\bprofit rises?\b": 3,

    r"\bwins? order\b": 4,

    r"\bbags? contract\b": 4,

    r"\bbuyback\b": 3,

    r"\bbonus issue\b": 2,

    r"\bdividend\b": 2,

    r"\bexpansion\b": 1,

    r"\bnew plant\b": 2,

    r"\b52 week high\b": 2,

    r"\bupper circuit\b": 3,
}

################################################################################
# Negative Lexicon
################################################################################

NEGATIVE_TERMS: Final = {

    r"\bdowngrade[sd]?\b": -3,

    r"\bsell rating\b": -2,

    r"\bsebi probe\b": -5,

    r"\bpenalty\b": -2,

    r"\bfraud\b": -5,

    r"\bauditor resigns?\b": -5,

    r"\bdefault\b": -4,

    r"\binsolvency\b": -4,

    r"\bbankruptcy\b": -5,

    r"\bprofit falls?\b": -3,

    r"\bmisses? estimates?\b": -3,

    r"\blower circuit\b": -3,

    r"\bcrash(es|ed)?\b": -3,

    r"\bscandal\b": -4,
}

################################################################################
# COMPILED REGEX PATTERNS
################################################################################

POSITIVE_PATTERNS: Final = [
    (
        re.compile(pattern, re.IGNORECASE),
        weight,
    )
    for pattern, weight in POSITIVE_TERMS.items()
]

NEGATIVE_PATTERNS: Final = [
    (
        re.compile(pattern, re.IGNORECASE),
        weight,
    )
    for pattern, weight in NEGATIVE_TERMS.items()
]

################################################################################
# HTTP UTILITIES
################################################################################


@retry
def _download_text(url: str) -> str:
    """
    Download text with retry and caching.
    """

    cached = cache_get(url)

    if cached is not None:
        logger.debug("Cache hit: %s", url)
        return cached

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64)"
            )
        },
    )

    start = time.perf_counter()

    with urllib.request.urlopen(
        req,
        timeout=CONFIG.HTTP_TIMEOUT,
    ) as response:

        text = response.read().decode(
            "utf-8",
            errors="replace",
        )

    latency = (
        time.perf_counter() - start
    ) * 1000

    logger.info(
        "Downloaded %s (%.0f ms)",
        url,
        latency,
    )

    cache_put(url, text)

    return text


################################################################################
# Yahoo Finance Provider
################################################################################


def _fetch_yfinance_news(
    ticker: str,
) -> list[NewsArticle]:

    if not HAVE_YFINANCE:
        return []

    try:

        raw_news = yf.Ticker(ticker).news

    except Exception as exc:

        logger.warning(
            "Yahoo fetch failed: %s",
            exc,
        )

        return []

    articles: list[NewsArticle] = []

    for item in raw_news or []:

        content = item.get("content", item)

        title = (
            content.get("title")
            or item.get("title")
            or ""
        ).strip()

        if not title:
            continue

        published = None

        ts = (
            content.get("pubDate")
            or item.get("providerPublishTime")
        )

        if isinstance(ts, str):

            try:

                published = dt.datetime.fromisoformat(
                    ts.replace(
                        "Z",
                        "+00:00",
                    )
                )

            except Exception:
                pass

        elif isinstance(
            ts,
            (int, float),
        ):

            try:

                published = dt.datetime.fromtimestamp(
                    float(ts)
                )

            except Exception:
                pass

        articles.append(
            NewsArticle(
                title=title,
                source=Source.YFINANCE,
                published=published,
            )
        )

    logger.info(
        "Yahoo articles: %d",
        len(articles),
    )

    return articles


################################################################################
# Google News RSS Provider
################################################################################


def _google_news_url(
    query: str,
    days: int,
) -> str:

    query = urllib.parse.quote(
        f"{query} when:{days}d"
    )

    return (
        "https://news.google.com/rss/search?"
        f"q={query}"
        "&hl=en-IN"
        "&gl=IN"
        "&ceid=IN:en"
    )



def _fetch_google_news(query: str, max_items: int = 10, days: int = 3) -> list:
    """
    Fetch Google News RSS using a proper XML parser.
    """

    q = urllib.parse.quote(f"{query} when:{int(days)}d")

    url = (
        "https://news.google.com/rss/search"
        f"?q={q}"
        "&hl=en-IN"
        "&gl=IN"
        "&ceid=IN:en"
    )

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            },
        )

        xml_data = urllib.request.urlopen(
            req,
            timeout=15,
        ).read()

        root = ET.fromstring(xml_data)

    except Exception:
        return []

    out = []

    for item in root.findall(".//item")[:max_items]:

        title = item.findtext("title", "").strip()

        pub_dt = None

        pub = item.findtext("pubDate")

        if pub:

            try:

                pub_dt = dt.datetime.strptime(
                    pub,
                    "%a, %d %b %Y %H:%M:%S %Z",
                )

            except Exception:
                pass

        out.append(
            {
                "title": title,
                "date": pub_dt,
                "source": "google",
            }
        )

    return out


################################################################################
# Relevance Filter
################################################################################


def _build_keywords(
    ticker: str,
    company_name: str | None,
) -> list[str]:

    keywords = [
        ticker.replace(".NS", "")
        .replace(".BO", "")
        .upper()
        .lower()
    ]

    if company_name:

        stop_words = {
            "ltd",
            "limited",
            "company",
            "corp",
            "corporation",
            "co",
            "the",
            "of",
            "and",
            "&",
        }

        for word in company_name.split():

            word = (
                word.lower()
                .strip(",.()")
            )

            if (
                len(word) >= 3
                and word not in stop_words
            ):
                keywords.append(word)

    return keywords


def _is_relevant(
    title: str,
    keywords: list[str],
) -> bool:

    title = title.lower()

    return any(
        keyword in title
        for keyword in keywords
    )


################################################################################
# Deduplication
################################################################################


def _deduplicate(
    articles: list[NewsArticle],
) -> list[NewsArticle]:

    seen: set[str] = set()

    unique: list[NewsArticle] = []

    for article in articles:

        key = normalize_title(
            article.title
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(article)

    return unique


################################################################################
# Provider Aggregator
################################################################################


def _fetch_news(
    ticker: str,
    company_name: str | None,
    lookback_days: int,
) -> list[NewsArticle]:

    query = (
        company_name
        if company_name
        else ticker.replace(
            ".NS",
            "",
        )
    )

    yahoo_news = _fetch_yfinance_news(
        ticker,
    )

    google_news = _fetch_google_news(
        f"{query} stock NSE",
        lookback_days,
    )

    keywords = _build_keywords(
        ticker,
        company_name,
    )

    filtered = []

    for article in (
        yahoo_news + google_news
    ):

        if not is_recent(
            article.published,
            lookback_days,
        ):
            continue

        if (
            article.source
            == Source.GOOGLE
            and not _is_relevant(
                article.title,
                keywords,
            )
        ):
            continue

        filtered.append(article)

    filtered = _deduplicate(
        filtered
    )

    filtered.sort(
        key=lambda x:
        x.published
        or dt.datetime.min,
        reverse=True,
    )

    logger.info(
        "Final news articles: %d",
        len(filtered),
    )

    return filtered[
        : CONFIG.MAX_HEADLINES
    ]

################################################################################
# SENTIMENT ENGINE
################################################################################

def _score_headline(
    title: str,
) -> tuple[float, list[str]]:

    if not title:
        return 0.0, []

    score = 0.0

    matched = []

    for regex, weight in POSITIVE_PATTERNS:

        m = regex.search(title)

        if m:

            score += weight

            matched.append(
                m.group(0).lower()
            )

    for regex, weight in NEGATIVE_PATTERNS:

        m = regex.search(title)

        if m:

            score += weight

            matched.append(
                m.group(0).lower()
            )

    return score, matched


################################################################################
# CONFIDENCE MODEL
################################################################################

def _confidence(
    articles: list[NewsArticle],
) -> float:
    """
    Estimate confidence based on

        • article count
        • score agreement

    Returns [0,1]
    """

    if not articles:
        return 0.0

    scores = [
        a.score
        for a in articles
    ]

    magnitude = (
        sum(abs(s) for s in scores)
        / len(scores)
    )

    coverage = min(
        len(articles) / 10,
        1.0,
    )

    agreement = abs(
        sum(scores)
    ) / (
        sum(abs(s) for s in scores)
        + 1e-9
    )

    confidence = (
        0.45 * coverage
        + 0.30 * agreement
        + 0.25 * min(
            magnitude / 5,
            1.0,
        )
    )

    return round(
        min(confidence, 1.0),
        3,
    )


################################################################################
# AGGREGATION
################################################################################

def _aggregate(
    articles: list[NewsArticle],
) -> SentimentResult:

    if not articles:

        return SentimentResult(
            score=0.0,
            confidence=0.0,
            sentiment=Sentiment.NEUTRAL,
            top_headline=None,
            top_score=0.0,
            matched_terms=[],
            articles=[],
        )

    for article in articles:

        score, matched = _score_headline(
            article.title
        )

        article.score = score

        article.matched_terms = matched

    weighted_score = 0.0

    total_weight = 0.0

    for article in articles:

        w = _recency_weight(
            article.published
        )

        weighted_score += (
            article.score * w
        )

        total_weight += w

    raw = (
        weighted_score / total_weight
        if total_weight
        else 0.0
    )

    final_score = round(
        compress_score(raw),
        3,
    )

    if final_score >= 0.30:

        sentiment = Sentiment.POSITIVE

    elif final_score <= -0.30:

        sentiment = Sentiment.NEGATIVE

    else:

        sentiment = Sentiment.NEUTRAL

    top = max(
        articles,
        key=lambda a: abs(a.score),
    )

    matched = sorted(
        {
            term
            for article in articles
            for term in article.matched_terms
        }
    )

    return SentimentResult(

        score=final_score,

        confidence=_confidence(
            articles,
        ),

        sentiment=sentiment,

        top_headline=top.title,

        top_score=top.score,

        matched_terms=matched,

        articles=articles,
    )


################################################################################
# PUBLIC API
################################################################################

def fetch_news_score(
    ticker_yahoo: str,
    company_name: str | None = None,
    lookback_days: int = CONFIG.LOOKBACK_DAYS,
) -> dict:
    """
    Public API.

    Signature intentionally matches the original module.

    Returns

    {
        score,
        n_articles,
        top_headline,
        top_impact,
        matched_terms,
        sources,
        all_headlines
    }
    """

    logger.info(
        "Processing news for %s",
        ticker_yahoo,
    )

    articles = _fetch_news(
        ticker=ticker_yahoo,
        company_name=company_name,
        lookback_days=lookback_days,
    )

    result = _aggregate(
        articles
    )

    source_counts = {
        "yfinance": 0,
        "google": 0,
    }

    for article in articles:

        if article.source == Source.YFINANCE:

            source_counts["yfinance"] += 1

        elif article.source == Source.GOOGLE:

            source_counts["google"] += 1

    return {

        "score": result.score,

        "confidence": result.confidence,

        "sentiment": result.sentiment.value,

        "n_articles": len(articles),

        "top_headline": result.top_headline,

        "top_impact": result.top_score,

        "matched_terms": result.matched_terms,

        "sources": source_counts,

        "all_headlines": [

            {
                "title": article.title,
                "date": article.published,
                "source": article.source.value,
                "score": article.score,
            }

            for article in articles

        ],
    }


################################################################################
# STREAMLIT CACHE
################################################################################

if st is not None:

    fetch_news_score = st.cache_data(
        ttl=CONFIG.CACHE_TTL,
        show_spinner=False,
    )(fetch_news_score)


################################################################################
# SELF TEST
################################################################################

if __name__ == "__main__":

    result = fetch_news_score(
        ticker_yahoo="RELIANCE.NS",
        company_name="Reliance Industries",
    )

    print()

    print("=" * 80)

    print("Sentiment Summary")

    print("=" * 80)

    print(f"Score       : {result['score']}")
    print(f"Confidence  : {result['confidence']}")
    print(f"Sentiment   : {result['sentiment']}")
    print(f"Articles    : {result['n_articles']}")
    print(f"Top Headline: {result['top_headline']}")
    print()

    print("Matched Terms")

    print("----------------")

    for term in result["matched_terms"]:

        print(term)

    print()

    print("Headlines")

    print("----------------")

    for article in result["all_headlines"]:

        print(
            f"[{article['source']}] "
            f"{article['score']:>5}  "
            f"{article['title']}"
        )