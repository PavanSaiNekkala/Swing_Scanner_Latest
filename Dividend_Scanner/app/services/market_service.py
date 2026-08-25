"""
Market Service
"""

from __future__ import annotations

from datetime import date
from datetime import timedelta

from app.database.tables import MarketTable
from app.providers.yahoo.market_provider import MarketProvider
from app.services.base_service import BaseService


class MarketService(BaseService):

    def __init__(self):
        super().__init__()
        self.provider = MarketProvider()

    def get(
        self,
        symbol: str,
    ):

        cached = self.cache.get(
            "market",
            symbol,
        )

        if cached:
            return cached

        rows = self.repo.market.get(
            symbol,
        )

        if rows:

            self.cache.set(
                "market",
                symbol,
                rows,
            )

            return rows

        history = self.provider.get_history(

            symbol=symbol,

            start=date.today() - timedelta(days=365),

            end=date.today(),

        )

        if not history:

            return []

        tables = [

            MarketTable(

                symbol=row.symbol,

                trading_date=row.trading_date,

                open=row.open,

                high=row.high,

                low=row.low,

                close=row.close,

                adj_close=row.adj_close,

                volume=row.volume,

            )

            for row in history

        ]

        self.repo.market.save_many(

            tables,

        )

        self.cache.set(

            "market",

            symbol,

            history,

        )

        return history