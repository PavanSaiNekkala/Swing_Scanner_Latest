"""
Domain models for the market layer.

This module defines the core business entities shared across the
NEWS_REPORT application.

Domain models are intentionally independent of infrastructure,
external APIs, pandas, yfinance, Excel exporters, AI providers,
or persistence frameworks.

Responsibilities
----------------
- Business entities
- Enumerations
- Domain validation
- Serialization
- Shared interfaces

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

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field

from datetime import datetime

from decimal import Decimal

from enum import StrEnum

from typing import Any

###############################################################################
# Enumerations
###############################################################################


class MarketDirection(StrEnum):
    """
    Daily market movement.
    """

    GAINER = "GAINER"

    LOSER = "LOSER"

    UNCHANGED = "UNCHANGED"


class MarketExchange(StrEnum):
    """
    Supported exchanges.
    """

    NSE = "NSE"

    BSE = "BSE"


###############################################################################
# Base Domain Model
###############################################################################


@dataclass(slots=True)
class BaseModel:
    """
    Base class for all domain models.

    Provides serialization helpers shared across
    the application.
    """

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Convert model into dictionary.
        """

        return asdict(
            self,
        )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ):
        """
        Create model from dictionary.
        """

        return cls(
            **data,
        )


###############################################################################
# Stock Identity
###############################################################################


@dataclass(slots=True)
class StockIdentity(BaseModel):
    """
    Immutable stock identity.

    Represents the static identity of an NSE-listed
    company irrespective of market data.
    """

    ticker: str

    company_name: str

    sector: str

    category: str

    exchange: MarketExchange = (
        MarketExchange.NSE
    )

    ###########################################################################
    # Validation
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        self.ticker = (
            self.ticker.upper().strip()
        )

        self.company_name = (
            self.company_name.strip()
        )

        self.sector = (
            self.sector.strip()
        )

        self.category = (
            self.category.strip()
        )

        if not self.ticker:

            raise ValueError(
                "Ticker cannot be empty."
            )

    ###########################################################################
    # Convenience Properties
    ###########################################################################

    @property
    def yahoo_symbol(
        self,
    ) -> str:
        """
        Yahoo Finance symbol.
        """

        return f"{self.ticker}.NS"

    @property
    def display_name(
        self,
    ) -> str:
        """
        Human-readable display.
        """

        return (
            f"{self.company_name}"
            f" ({self.ticker})"
        )


###############################################################################
# Market Snapshot
###############################################################################


@dataclass(slots=True)
class MarketSnapshot(BaseModel):
    """
    Represents a single trading session for a stock.

    This object contains only calculated market values
    and is independent of the data provider.
    """

    previous_close: Decimal

    current_price: Decimal

    day_return_percent: Decimal

    volume: int

    market_cap: int | None = None

    timestamp: datetime = field(
        default_factory=datetime.utcnow,
    )

    ###########################################################################
    # Validation
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        if self.volume < 0:

            raise ValueError(
                "Volume cannot be negative."
            )

    ###########################################################################
    # Derived Properties
    ###########################################################################

    @property
    def price_change(
        self,
    ) -> Decimal:
        """
        Absolute price change.
        """

        return (
            self.current_price
            - self.previous_close
        )

    @property
    def direction(
        self,
    ) -> MarketDirection:
        """
        Market movement direction.
        """

        if self.day_return_percent > 0:

            return MarketDirection.GAINER

        if self.day_return_percent < 0:

            return MarketDirection.LOSER

        return MarketDirection.UNCHANGED

    @property
    def is_gainer(
        self,
    ) -> bool:
        """
        Whether the stock gained today.
        """

        return (
            self.direction
            is MarketDirection.GAINER
        )

    @property
    def is_loser(
        self,
    ) -> bool:
        """
        Whether the stock lost today.
        """

        return (
            self.direction
            is MarketDirection.LOSER
        )


###############################################################################
# Market Stock
###############################################################################


@dataclass(slots=True)
class MarketStock(BaseModel):
    """
    Complete representation of one NSE stock.

    Combines the static stock identity with
    today's market snapshot.
    """

    identity: StockIdentity

    snapshot: MarketSnapshot

    ###########################################################################
    # Convenience Properties
    ###########################################################################

    @property
    def ticker(
        self,
    ) -> str:

        return self.identity.ticker

    @property
    def company_name(
        self,
    ) -> str:

        return self.identity.company_name

    @property
    def sector(
        self,
    ) -> str:

        return self.identity.sector

    @property
    def category(
        self,
    ) -> str:

        return self.identity.category

    @property
    def return_percent(
        self,
    ) -> Decimal:

        return self.snapshot.day_return_percent

    @property
    def current_price(
        self,
    ) -> Decimal:

        return self.snapshot.current_price

    @property
    def previous_close(
        self,
    ) -> Decimal:

        return self.snapshot.previous_close

    @property
    def volume(
        self,
    ) -> int:

        return self.snapshot.volume

    @property
    def market_cap(
        self,
    ) -> int | None:

        return self.snapshot.market_cap

    @property
    def direction(
        self,
    ) -> MarketDirection:

        return self.snapshot.direction


###############################################################################
# Market Collection
###############################################################################


@dataclass(slots=True)
class MarketCollection(BaseModel):
    """
    Collection of MarketStock objects.

    Used as the base container throughout the
    Market Pipeline.
    """

    stocks: list[MarketStock] = field(
        default_factory=list,
    )

    ###########################################################################
    # Collection Interface
    ###########################################################################

    def __len__(
        self,
    ) -> int:

        return len(
            self.stocks,
        )

    def __iter__(
        self,
    ):

        return iter(
            self.stocks,
        )

    def __getitem__(
        self,
        index: int,
    ) -> MarketStock:

        return self.stocks[
            index
        ]

    ###########################################################################
    # Operations
    ###########################################################################

    def add(
        self,
        stock: MarketStock,
    ) -> None:
        """
        Add a stock.
        """

        self.stocks.append(
            stock,
        )

    def extend(
        self,
        stocks: list[MarketStock],
    ) -> None:
        """
        Add multiple stocks.
        """

        self.stocks.extend(
            stocks,
        )

    def clear(
        self,
    ) -> None:
        """
        Remove all stocks.
        """

        self.stocks.clear()

###############################################################################
# Market Ranking
###############################################################################


@dataclass(slots=True)
class MarketRanking(BaseModel):
    """
    Ranked collection of market stocks.

    Represents the output of the ranking stage,
    such as Top Gainers or Top Losers.
    """

    title: str

    stocks: list[MarketStock] = field(
        default_factory=list,
    )

    generated_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    ###########################################################################
    # Collection Interface
    ###########################################################################

    def __len__(
        self,
    ) -> int:

        return len(
            self.stocks,
        )

    def __iter__(
        self,
    ):

        return iter(
            self.stocks,
        )

    def __getitem__(
        self,
        index: int,
    ) -> MarketStock:

        return self.stocks[
            index
        ]

    ###########################################################################
    # Properties
    ###########################################################################

    @property
    def count(
        self,
    ) -> int:
        """
        Total ranked stocks.
        """

        return len(
            self.stocks,
        )

    @property
    def is_empty(
        self,
    ) -> bool:
        """
        Whether ranking is empty.
        """

        return (
            len(self.stocks) == 0
        )

    ###########################################################################
    # Operations
    ###########################################################################

    def add(
        self,
        stock: MarketStock,
    ) -> None:
        """
        Add a ranked stock.
        """

        self.stocks.append(
            stock,
        )

    def extend(
        self,
        stocks: list[MarketStock],
    ) -> None:
        """
        Add multiple ranked stocks.
        """

        self.stocks.extend(
            stocks,
        )

    def clear(
        self,
    ) -> None:
        """
        Remove all ranked stocks.
        """

        self.stocks.clear()


###############################################################################
# Market Report
###############################################################################


@dataclass(slots=True)
class MarketReport(BaseModel):
    """
    Final output of the Market Pipeline.

    Contains the ranked gainers and losers together
    with execution metadata.
    """

    top_gainers: MarketRanking = field(
        default_factory=lambda: MarketRanking(
            title="Top Gainers",
        ),
    )

    top_losers: MarketRanking = field(
        default_factory=lambda: MarketRanking(
            title="Top Losers",
        ),
    )

    universe_size: int = 0

    execution_time_seconds: float = 0.0

    generated_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    ###########################################################################
    # Properties
    ###########################################################################

    @property
    def total_ranked(
        self,
    ) -> int:
        """
        Total ranked stocks.
        """

        return (

            self.top_gainers.count

            +

            self.top_losers.count

        )

    @property
    def has_data(
        self,
    ) -> bool:
        """
        Whether rankings exist.
        """

        return self.total_ranked > 0

    ###########################################################################
    # Convenience
    ###########################################################################

    def all_ranked(
        self,
    ) -> list[MarketStock]:
        """
        Return all ranked stocks.
        """

        return [

            *self.top_gainers.stocks,

            *self.top_losers.stocks,

        ]

###############################################################################
# News Article
###############################################################################


@dataclass(slots=True)
class NewsArticle(BaseModel):
    """
    Normalized news article.

    Every news provider should convert its raw response
    into this domain model.
    """

    ticker: str

    title: str

    source: str

    url: str

    published_at: datetime

    summary: str = ""

    sentiment: str = "Neutral"

    relevance_score: float = 0.0

    author: str | None = None

    image_url: str | None = None

    ###########################################################################
    # Validation
    ###########################################################################

    def __post_init__(
        self,
    ) -> None:

        self.ticker = (
            self.ticker.upper().strip()
        )

        self.title = (
            self.title.strip()
        )

        self.source = (
            self.source.strip()
        )

        self.url = (
            self.url.strip()
        )

###############################################################################
# Stock News
###############################################################################

@dataclass(slots=True)
class StockNews(BaseModel):
    """
    News collected for one stock.

    This object represents the complete AI-ready
    information for a single company.
    """

    ticker: str

    company_name: str

    articles: list[NewsArticle] = field(
        default_factory=list,
    )

    ###########################################################################
    # AI Summary
    ###########################################################################

    executive_summary: str = ""

    sentiment: str = "Neutral"

    confidence: float = 0.0

    bullish_points: list[str] = field(
        default_factory=list,
    )

    bearish_points: list[str] = field(
        default_factory=list,
    )

    key_events: list[str] = field(
        default_factory=list,
    )

    ###########################################################################
    # Ranking
    ###########################################################################

    rank_score: float = 0.0

    ###########################################################################
    # Collection Interface
    ###########################################################################

    def __len__(self) -> int:
        return len(self.articles)

    def __iter__(self):
        return iter(self.articles)

    ###########################################################################
    # Properties
    ###########################################################################

    @property
    def article_count(self) -> int:
        return len(self.articles)

    ###########################################################################
    # Operations
    ###########################################################################

    def add(
        self,
        article: NewsArticle,
    ) -> None:
        self.articles.append(article)

    def extend(
        self,
        articles: list[NewsArticle],
    ) -> None:
        self.articles.extend(articles)


###############################################################################
# News Report
###############################################################################

@dataclass(slots=True)
class NewsReport(BaseModel):
    """
    Output of the News Pipeline.
    """

    gainers_news: list[StockNews] = field(
        default_factory=list,
    )

    losers_news: list[StockNews] = field(
        default_factory=list,
    )

    total_articles: int = 0

    generated_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    ###########################################################################
    # Convenience
    ###########################################################################

    @property
    def total_companies(
        self,
    ) -> int:
        """
        Total companies processed.
        """

        return (

            len(self.gainers_news)

            +

            len(self.losers_news)

        )

    def all_news(
        self,
    ) -> list[StockNews]:
        """
        Return news for all companies.
        """

        return [

            *self.gainers_news,

            *self.losers_news,

        ]

###############################################################################
# Application Report
###############################################################################


@dataclass(slots=True)
class ApplicationReport(BaseModel):
    """
    Root domain object.

    This is the final object passed into the
    reporting layer.
    """

    market: MarketReport

    news: NewsReport

    version: str = "1.0.0"

    created_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    ###########################################################################
    # Convenience
    ###########################################################################

    @property
    def generated_timestamp(
        self,
    ) -> str:
        """
        ISO formatted generation timestamp.
        """

        return self.created_at.isoformat()