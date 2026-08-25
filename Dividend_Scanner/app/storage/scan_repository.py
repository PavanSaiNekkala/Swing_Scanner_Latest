"""
Scan Repository

Aggregates all storage classes.
"""

from __future__ import annotations

from app.storage.company_store import CompanyStore
from app.storage.dividend_store import DividendStore
from app.storage.market_store import MarketStore
from app.storage.news_store import NewsStore
from app.storage.scan_result_store import ScanResultStore


class ScanRepository:

    def __init__(
        self,
    ) -> None:

        # Company Master
        self.company: CompanyStore = CompanyStore()

        # Dividend History
        self.dividend: DividendStore = DividendStore()

        # Historical Market Data
        self.market: MarketStore = MarketStore()

        # News Articles
        self.news: NewsStore = NewsStore()

        # Final Scan Results
        self.scan_result: ScanResultStore = ScanResultStore()