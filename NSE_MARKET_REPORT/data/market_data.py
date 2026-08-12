from config.settings import MARKET_PROVIDER

from data.providers.mock_provider import MockProvider
from data.providers.nse_provider import NSEProvider


class MarketData:

    def __init__(self):

        providers = {
            "mock": MockProvider,
            "nse": NSEProvider,
        }

        provider_cls = providers.get(MARKET_PROVIDER.lower())

        if provider_cls is None:
            raise ValueError(
                f"Unknown MARKET_PROVIDER: {MARKET_PROVIDER}"
            )

        self.provider = provider_cls()

    def fetch_top_gainers(self):
        return self.provider.fetch_top_gainers()

    def fetch_top_losers(self):
        return self.provider.fetch_top_losers()

    def fetch_market_report(self):
        return self.provider.fetch_market_report()

    def fetch_quotes(self):
        return self.provider.fetch_quotes()

    def fetch_ohlc(self):
        return self.provider.fetch_ohlc()

    def health_check(self):
        health = self.provider.health()
        health["component"] = "MarketData"
        return health