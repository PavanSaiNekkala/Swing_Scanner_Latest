from __future__ import annotations

import pandas as pd

from .base import MarketDataProvider


class MockProvider(MarketDataProvider):

    def fetch_quotes(
        self,
    ) -> pd.DataFrame:

        return pd.DataFrame()

    def fetch_ohlc(
        self,
    ) -> pd.DataFrame:

        return pd.DataFrame()

    def health(
        self,
    ) -> dict:

        return {
            "provider": "Mock",
            "status": "OK",
            "message": "Mock provider available.",
        }