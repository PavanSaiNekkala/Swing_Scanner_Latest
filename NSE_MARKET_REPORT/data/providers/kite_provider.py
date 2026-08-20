from __future__ import annotations

import pandas as pd

from .base import MarketDataProvider


class KiteProvider(MarketDataProvider):

    def fetch_quotes(
        self,
    ) -> pd.DataFrame:

        raise NotImplementedError

    def fetch_ohlc(
        self,
    ) -> pd.DataFrame:

        raise NotImplementedError

    def health(
        self,
    ) -> dict:

        return {
            "provider": "Kite",
            "status": "NOT_IMPLEMENTED",
        }