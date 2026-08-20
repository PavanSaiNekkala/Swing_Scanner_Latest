from abc import ABC
from abc import abstractmethod

import pandas as pd


class MarketDataProvider(ABC):

    @abstractmethod
    def fetch_quotes(
        self,
        symbols: list[str] | None = None,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def fetch_ohlc(
        self,
        symbol: str,
        *,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def fetch_top_gainers(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def fetch_top_losers(
        self,
        *,
        symbols: list[str] | None = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def health(
        self,
    ) -> dict:
        raise NotImplementedError