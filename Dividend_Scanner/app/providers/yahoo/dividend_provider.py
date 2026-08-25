"""
Yahoo Dividend Provider

Fetches raw dividend history from Yahoo Finance.

Responsibilities
----------------
- Fetch dividend history
- Return raw dividend events
- No analytics
- No scoring
- No yield calculation
"""

from __future__ import annotations

from typing import List

import pandas as pd
import yfinance as yf

from app.models.dividend import Dividend
from app.providers.base_provider import BaseProvider


class DividendProvider(
    BaseProvider,
):

    PROVIDER = "Yahoo Finance"

    # ---------------------------------------------------------
    # Public
    # ---------------------------------------------------------

    def get_dividends(
        self,
        symbol: str,
    ) -> List[Dividend]:

        try:

            ticker = yf.Ticker(
                self.normalize_symbol(symbol)
            )

            history = ticker.dividends

            if history is None or history.empty:

                return []

            dividends: List[Dividend] = []

            currency = None

            try:

                currency = ticker.fast_info.get(
                    "currency",
                )

            except Exception:

                pass

            for ex_date, amount in history.items():

                if pd.isna(
                    amount,
                ):

                    continue

                dividends.append(

                    Dividend(

                        symbol=symbol,

                        ex_date=ex_date.date(),

                        amount=float(
                            amount,
                        ),

                        currency=currency,

                    )

                )

            dividends.sort(

                key=lambda row: row.ex_date,

                reverse=True,

            )

            return dividends

        except Exception as ex:

            self.logger.exception(
                ex,
            )

            return []

    # ---------------------------------------------------------
    # Health
    # ---------------------------------------------------------

    def health_check(
        self,
    ) -> bool:

        try:

            yf.Ticker(
                "^NSEI",
            ).dividends

            return True

        except Exception:

            return False