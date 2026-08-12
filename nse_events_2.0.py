"""
================================================================================
nse_events.py

Institutional Grade NSE Corporate Event Engine
Version : 2.0
Python  : 3.11+

Public API (implemented in later layers)

    fetch_upcoming_events(...)
    event_risk(...)

================================================================================
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import random
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

try:
    from curl_cffi import requests as curl_requests

    HAVE_CURL = True
except Exception:
    HAVE_CURL = False

try:
    import streamlit as st
except Exception:
    st = None

try:
    from governance_fetcher import (
        _make_session,
        _prime_nse,
    )

    HAVE_GOV_HELPERS = True
except Exception:
    HAVE_GOV_HELPERS = False

################################################################################
# Logging
################################################################################

LOGGER_NAME: Final = "nse_events"

logger = logging.getLogger(LOGGER_NAME)

if not logger.handlers:
    handler = logging.StreamHandler()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    handler.setFormatter(formatter)

    logger.addHandler(handler)

logger.setLevel(logging.INFO)

################################################################################
# Configuration
################################################################################


@dataclass(slots=True, frozen=True)
class Config:
    """Runtime configuration."""

    BASE_URL: str = "https://www.nseindia.com"

    ANNOUNCEMENT_API: str = (
        "https://www.nseindia.com/api/corporate-announcements"
    )

    CORPORATE_ACTION_API: str = (
        "https://www.nseindia.com/api/corporates-corporateActions"
    )

    HTTP_TIMEOUT: int = 15

    MAX_RETRIES: int = 4

    RETRY_BACKOFF: float = 1.50

    CACHE_TTL: int = 1800

    LOOKBACK_DAYS: int = 14

    LOOKAHEAD_DAYS: int = 30

    DEFAULT_SESSION_WINDOW: int = 5


CONFIG = Config()

################################################################################
# Event Types
################################################################################


class EventType(str, Enum):
    RESULTS = "RESULTS"

    BOARD_MTG = "BOARD_MTG"

    AGM = "AGM"

    DIVIDEND = "DIVIDEND"

    SPLIT = "SPLIT"

    BONUS = "BONUS"

    BUYBACK = "BUYBACK"

    RIGHTS = "RIGHTS"

    SCHEME = "SCHEME"

    OTHER = "OTHER"


################################################################################
# Risk Levels
################################################################################


class RiskLevel(str, Enum):
    LOW = "LOW"

    MEDIUM = "MEDIUM"

    HIGH = "HIGH"

    BLOCK = "BLOCK"


################################################################################
# Data Models
################################################################################


@dataclass(slots=True)
class CorporateEvent:
    symbol: str

    event_type: EventType

    date: dt.date

    subject: str

    source: str

    risk: RiskLevel = RiskLevel.LOW


@dataclass(slots=True)
class EventRiskResult:
    blocked: bool

    event_type: EventType | None

    days_until: int | None

    subject: str | None

    upcoming: list[CorporateEvent] = field(default_factory=list)


################################################################################
# Exception Hierarchy
################################################################################


class NSEEventsError(Exception):
    """Base exception."""


class SessionError(NSEEventsError):
    """Session creation failed."""


class RequestError(NSEEventsError):
    """HTTP request failed."""


class InvalidResponse(NSEEventsError):
    """Unexpected payload."""


################################################################################
# Thread-safe Singleton Session Manager
################################################################################


class SessionManager:
    """
    Thread-safe lazy singleton.

    Reuses the governance_fetcher session.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):

        if cls._instance is None:

            with cls._lock:

                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._session = None
                    cls._instance._primed = False

        return cls._instance

    def session(self):

        if not HAVE_CURL:
            raise SessionError("curl_cffi not installed")

        if not HAVE_GOV_HELPERS:
            raise SessionError("governance_fetcher unavailable")

        if self._session is None:

            self._session = _make_session()

        if not self._primed:

            _prime_nse(self._session)

            self._primed = True

        return self._session


################################################################################
# Retry Decorator
################################################################################


def retry(func):
    """
    Exponential backoff retry decorator.
    """

    def wrapper(*args, **kwargs):

        last_exception = None

        for attempt in range(CONFIG.MAX_RETRIES):

            try:

                return func(*args, **kwargs)

            except Exception as exc:

                last_exception = exc

                delay = (
                    CONFIG.RETRY_BACKOFF**attempt
                ) + random.uniform(0.0, 0.30)

                logger.warning(
                    "%s failed (%s/%s). Retrying in %.2fs",
                    func.__name__,
                    attempt + 1,
                    CONFIG.MAX_RETRIES,
                    delay,
                )

                time.sleep(delay)

        raise RequestError(str(last_exception))

    return wrapper


################################################################################
# Regex Classifier
################################################################################

EVENT_PATTERNS: Final = [
    (
        EventType.RESULTS,
        re.compile(
            r"\b("
            r"quarterly results|"
            r"financial results|"
            r"annual results|"
            r"earnings|"
            r"q[1-4]\s*results"
            r")\b",
            re.I,
        ),
    ),
    (
        EventType.BOARD_MTG,
        re.compile(
            r"\b(board meeting|meeting of the board)\b",
            re.I,
        ),
    ),
    (
        EventType.AGM,
        re.compile(
            r"\b(agm|annual general meeting|egm)\b",
            re.I,
        ),
    ),
    (
        EventType.DIVIDEND,
        re.compile(r"\b(dividend)\b", re.I),
    ),
    (
        EventType.SPLIT,
        re.compile(r"\b(stock split|share split)\b", re.I),
    ),
    (
        EventType.BONUS,
        re.compile(r"\bbonus\b", re.I),
    ),
    (
        EventType.BUYBACK,
        re.compile(r"\bbuy.?back\b", re.I),
    ),
    (
        EventType.RIGHTS,
        re.compile(r"\brights issue\b", re.I),
    ),
    (
        EventType.SCHEME,
        re.compile(
            r"\b("
            r"merger|"
            r"demerger|"
            r"scheme of arrangement|"
            r"amalgamation"
            r")\b",
            re.I,
        ),
    ),
]

HARD_BLOCK_EVENTS: Final = frozenset(
    {
        EventType.RESULTS,
        EventType.BOARD_MTG,
        EventType.AGM,
        EventType.DIVIDEND,
        EventType.SPLIT,
        EventType.BONUS,
        EventType.BUYBACK,
        EventType.RIGHTS,
        EventType.SCHEME,
    }
)

################################################################################
# Utility Functions
################################################################################


def parse_nse_date(value: str | None) -> dt.date | None:
    """
    Parse NSE date formats.

    Supported:

        24-Jul-2026

        24-Jul-2026 13:40:11
    """

    if not value:
        return None

    try:
        return dt.datetime.strptime(
            value.split()[0],
            "%d-%b-%Y",
        ).date()

    except Exception:

        return None


def classify_event(text: str) -> EventType:
    """
    Determine event type from announcement text.
    """

    if not text:
        return EventType.OTHER

    for event_type, pattern in EVENT_PATTERNS:

        if pattern.search(text):
            return event_type

    return EventType.OTHER


################################################################################
# END OF FOUNDATION LAYER
################################################################################

################################################################################
# HTTP ENGINE
################################################################################

_json_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.RLock()


def _cache_get(key: str) -> Any | None:
    """
    Thread-safe TTL cache lookup.
    """
    now = time.time()

    with _cache_lock:

        item = _json_cache.get(key)

        if item is None:
            return None

        expires, value = item

        if expires < now:
            _json_cache.pop(key, None)
            return None

        return value


def _cache_put(key: str, value: Any) -> None:
    """
    Store object in TTL cache.
    """
    with _cache_lock:

        _json_cache[key] = (
            time.time() + CONFIG.CACHE_TTL,
            value,
        )


################################################################################
# Request Helpers
################################################################################


def _build_headers() -> dict[str, str]:
    """
    Common headers.

    curl_cffi already impersonates Chrome, but explicit Accept headers
    improve reliability when NSE changes edge filtering.
    """

    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-IN,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.nseindia.com/",
    }


@retry
def _http_get_json(url: str) -> Any:
    """
    Production HTTP GET.

    Features

    - retry
    - validation
    - structured logging
    - TTL cache
    """

    cached = _cache_get(url)

    if cached is not None:
        logger.debug("Cache hit: %s", url)
        return cached

    session = SessionManager().session()

    start = time.perf_counter()

    response = session.get(
        url,
        timeout=CONFIG.HTTP_TIMEOUT,
        headers=_build_headers(),
    )

    latency = (time.perf_counter() - start) * 1000

    logger.info(
        "GET %s status=%s latency=%.0fms",
        url,
        response.status_code,
        latency,
    )

    if response.status_code != 200:
        raise RequestError(
            f"HTTP {response.status_code}"
        )

    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    if "json" not in content_type:
        raise InvalidResponse(
            f"Unexpected content-type {content_type}"
        )

    try:
        payload = response.json()

    except Exception:

        try:
            payload = json.loads(response.text)

        except Exception as exc:
            raise InvalidResponse(
                "Unable to decode JSON"
            ) from exc

    _cache_put(url, payload)

    return payload


################################################################################
# URL Builders
################################################################################


def _announcement_url(
    ticker: str,
    lookback_days: int,
) -> str:

    today = dt.date.today()

    start = (
        today - dt.timedelta(days=lookback_days)
    ).strftime("%d-%m-%Y")

    end = today.strftime("%d-%m-%Y")

    return (
        f"{CONFIG.ANNOUNCEMENT_API}"
        f"?index=equities"
        f"&symbol={ticker}"
        f"&from_date={start}"
        f"&to_date={end}"
    )


def _corporate_action_url(
    ticker: str,
) -> str:

    return (
        f"{CONFIG.CORPORATE_ACTION_API}"
        f"?index=equities"
        f"&symbol={ticker}"
    )


################################################################################
# Payload Parsing
################################################################################


def _parse_announcements(
    ticker: str,
    payload: Any,
) -> list[CorporateEvent]:
    """
    Convert announcement payload into CorporateEvent objects.
    """

    if not isinstance(payload, list):
        return []

    events: list[CorporateEvent] = []

    for row in payload:

        if not isinstance(row, dict):
            continue

        event_date = parse_nse_date(
            row.get("an_dt")
        )

        if event_date is None:
            continue

        subject = (
            f"{row.get('desc','')} | "
            f"{row.get('attchmntText','')}"
        ).strip()

        event_type = classify_event(subject)

        events.append(
            CorporateEvent(
                symbol=ticker.upper(),
                event_type=event_type,
                date=event_date,
                subject=subject[:250],
                source="ANNOUNCEMENT",
                risk=(
                    RiskLevel.BLOCK
                    if event_type in HARD_BLOCK_EVENTS
                    else RiskLevel.LOW
                ),
            )
        )

    events.sort(key=lambda x: x.date)

    return events


def _parse_corporate_actions(
    ticker: str,
    payload: Any,
) -> list[CorporateEvent]:

    if not isinstance(payload, list):
        return []

    events: list[CorporateEvent] = []

    for row in payload:

        if not isinstance(row, dict):
            continue

        event_date = (
            parse_nse_date(row.get("exDate"))
            or parse_nse_date(row.get("recDate"))
        )

        if event_date is None:
            continue

        subject = (
            str(row.get("subject") or "")
            .strip()
        )

        event_type = classify_event(subject)

        events.append(
            CorporateEvent(
                symbol=ticker.upper(),
                event_type=event_type,
                date=event_date,
                subject=subject[:250],
                source="CORPORATE_ACTION",
                risk=(
                    RiskLevel.BLOCK
                    if event_type in HARD_BLOCK_EVENTS
                    else RiskLevel.LOW
                ),
            )
        )

    events.sort(key=lambda x: x.date)

    return events


################################################################################
# Fetch Engine
################################################################################


def _fetch_announcements(
    ticker: str,
    lookback_days: int,
) -> list[CorporateEvent]:
    """
    Retrieve announcement feed.
    """

    payload = _http_get_json(
        _announcement_url(
            ticker,
            lookback_days,
        )
    )

    return _parse_announcements(
        ticker,
        payload,
    )


def _fetch_corporate_actions(
    ticker: str,
) -> list[CorporateEvent]:
    """
    Retrieve corporate actions.
    """

    payload = _http_get_json(
        _corporate_action_url(
            ticker,
        )
    )

    return _parse_corporate_actions(
        ticker,
        payload,
    )

################################################################################
# EVENT HELPERS
################################################################################


def _deduplicate_events(
    events: list[CorporateEvent],
) -> list[CorporateEvent]:
    """
    Remove duplicate events while preserving chronological order.

    Duplicate key:
        symbol + date + event_type
    """

    seen: set[tuple[str, dt.date, EventType]] = set()

    unique: list[CorporateEvent] = []

    for event in sorted(events, key=lambda e: e.date):

        key = (
            event.symbol,
            event.date,
            event.event_type,
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(event)

    return unique


def _filter_event_window(
    events: list[CorporateEvent],
    lookback_days: int,
    lookahead_days: int,
) -> list[CorporateEvent]:
    """
    Keep only events inside the configured time window.
    """

    today = dt.date.today()

    min_date = today - dt.timedelta(days=lookback_days)

    max_date = today + dt.timedelta(days=lookahead_days)

    return [
        event
        for event in events
        if min_date <= event.date <= max_date
    ]


################################################################################
# PUBLIC API
################################################################################


def fetch_upcoming_events(
    ticker: str,
    lookback_days: int = CONFIG.LOOKBACK_DAYS,
    lookahead_days: int = CONFIG.LOOKAHEAD_DAYS,
) -> list[dict]:
    """
    Fetch all relevant corporate events.

    Public API remains identical to the original implementation.

    Returns
    -------
    list[dict]

    Each dictionary contains

        date
        subject
        type
    """

    ticker = ticker.strip().upper()

    if not ticker:
        return []

    logger.info(
        "Fetching corporate events for %s",
        ticker,
    )

    announcements = _fetch_announcements(
        ticker,
        lookback_days,
    )

    actions = _fetch_corporate_actions(
        ticker,
    )

    events = announcements + actions

    events = _filter_event_window(
        events,
        lookback_days,
        lookahead_days,
    )

    events = _deduplicate_events(events)

    return [
        {
            "date": event.date,
            "subject": event.subject,
            "type": event.event_type.value,
        }
        for event in events
    ]


################################################################################
# STREAMLIT CACHE
################################################################################


_cached_events = fetch_upcoming_events

if st is not None:

    _cached_events = st.cache_data(
        ttl=CONFIG.CACHE_TTL,
        show_spinner=False,
    )(fetch_upcoming_events)


################################################################################
# RISK ENGINE
################################################################################


def _session_window(
    next_sessions: int,
) -> tuple[dt.date, dt.date]:
    """
    Approximate trading sessions with calendar days.

    5 sessions ≈ 7 calendar days.
    """

    today = dt.date.today()

    end = today + dt.timedelta(
        days=int(next_sessions * 1.4) + 1
    )

    return today, end


def event_risk(
    ticker: str,
    next_sessions: int = CONFIG.DEFAULT_SESSION_WINDOW,
) -> dict:
    """
    Evaluate upcoming corporate-event risk.

    Public API intentionally matches the original module.

    Returns

    {
        blocked,
        type,
        days_until,
        subject,
        all_upcoming
    }
    """

    ticker = ticker.strip().upper()

    try:

        raw_events = _cached_events(ticker)

    except Exception:

        logger.exception(
            "Unable to load events for %s",
            ticker,
        )

        raw_events = []

    today, window_end = _session_window(
        next_sessions,
    )

    upcoming = []

    for row in raw_events:

        event_date = row["date"]

        if today <= event_date <= window_end:

            upcoming.append(row)

    if not upcoming:

        return {
            "blocked": False,
            "type": None,
            "days_until": None,
            "subject": None,
            "all_upcoming": [],
        }

    upcoming.sort(
        key=lambda x: x["date"]
    )

    for event in upcoming:

        if (
            EventType(event["type"])
            in HARD_BLOCK_EVENTS
        ):

            logger.info(
                "Trade blocked: %s (%s)",
                ticker,
                event["type"],
            )

            return {
                "blocked": True,
                "type": event["type"],
                "days_until": (
                    event["date"] - today
                ).days,
                "subject": event["subject"][:120],
                "all_upcoming": upcoming,
            }

    first = upcoming[0]

    return {
        "blocked": False,
        "type": first["type"],
        "days_until": (
            first["date"] - today
        ).days,
        "subject": first["subject"][:120],
        "all_upcoming": upcoming,
    }


################################################################################
# SELF TEST
################################################################################

if __name__ == "__main__":

    symbol = "RELIANCE"

    print()

    print("Upcoming Events")

    print("----------------")

    events = fetch_upcoming_events(symbol)

    for item in events:

        print(item)

    print()

    print("Risk")

    print("----")

    print(
        event_risk(symbol)
    )