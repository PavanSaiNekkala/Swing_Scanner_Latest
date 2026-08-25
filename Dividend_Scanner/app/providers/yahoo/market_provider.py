"""
Yahoo Market Provider

Fetches historical OHLCV market data from Yahoo Finance.
"""

from __future__ import annotations

from datetime import date
from typing import List

import yfinance as yf
import pandas as pd

from app.models.market import MarketData
from app.providers.base_provider import BaseProvider


class MarketProvider(BaseProvider):

    PROVIDER = "Yahoo Finance"

    # ---------------------------------------------------------
    # Public
    # ---------------------------------------------------------

    def get_history(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> List[MarketData]:

        try:

            yahoo_symbol = self.normalize_symbol(symbol)

            history = yf.download(

                tickers=yahoo_symbol,

                start=start,

                end=end,

                auto_adjust=False,

                progress=False,

            )

            if history is None or history.empty:
                return []

            history = history.reset_index()

            if isinstance(history.columns, pd.MultiIndex):

                history.columns = [
                    col[0]
                    for col in history.columns
                ]

            rows: List[MarketData] = []

            for _, row in history.iterrows():

                rows.append(

                    MarketData(

                        symbol=symbol,              # original symbol
                        ticker=yahoo_symbol,        # Yahoo symbol

                        trading_date=row["Date"].date(),

                        open=float(row["Open"]),

                        high=float(row["High"]),

                        low=float(row["Low"]),

                        close=float(row["Close"]),

                        adjusted_close=float(
                            row.get(
                                "Adj Close",
                                row["Close"],
                            )
                        ),

                        volume=int(row["Volume"]),

                        provider=self.PROVIDER,

                    )

                )

            return rows

        except Exception as ex:

            self.logger.exception(ex)

            return []

    # ---------------------------------------------------------
    # Health
    # ---------------------------------------------------------

    def health_check(self) -> bool:

        try:

            history = yf.download(

                "^NSEI",

                period="5d",

                progress=False,

            )

            return history is not None and not history.empty

        except Exception:

            return False