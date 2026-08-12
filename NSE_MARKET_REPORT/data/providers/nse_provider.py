from data.nse_data import NSEData
from .base import MarketProvider


class NSEProvider(MarketProvider):

    def __init__(self):
        self.client = NSEData()

    def fetch_top_gainers(self):
        return self.client.fetch_top_gainers()

    def fetch_top_losers(self):
        return self.client.fetch_top_losers()

    def fetch_market_report(self):
        return self.client.fetch_market_report()

    def fetch_quotes(self):
        return self.fetch_market_report()

    def fetch_ohlc(self):
        raise NotImplementedError(
            "OHLC is currently handled by OHLCData."
        )

    def health(self):
        return self.client.health_check()

    def refresh(self):
        return self.client.refresh()

    def get_symbols(self):
        return self.client.get_symbols()