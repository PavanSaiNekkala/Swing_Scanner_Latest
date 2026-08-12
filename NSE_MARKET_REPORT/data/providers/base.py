from abc import ABC, abstractmethod
import pandas as pd


class MarketProvider(ABC):

    @abstractmethod
    def fetch_quotes(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def fetch_ohlc(self) -> pd.DataFrame:
        pass

    @abstractmethod
    def health(self) -> dict:
        pass