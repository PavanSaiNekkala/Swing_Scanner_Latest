import pandas as pd
from .base import MarketProvider


class MockProvider(MarketProvider):

    def fetch_quotes(self):
        return pd.DataFrame([
            {
                "Symbol": "RELIANCE",
                "Company": "Reliance Industries",
                "CMP": 1520.5,
                "1 Day Change %": 2.35,
                "Volume": 1200000,
            },
            {
                "Symbol": "INFY",
                "Company": "Infosys",
                "CMP": 1822.4,
                "1 Day Change %": -1.24,
                "Volume": 800000,
            },
        ])

    def fetch_ohlc(self):
        return pd.DataFrame()

    def health(self):
        return {
            "provider": "Mock",
            "status": "healthy",
        }