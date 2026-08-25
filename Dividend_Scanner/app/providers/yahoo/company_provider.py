"""
Yahoo Company Provider

Fetches company profile information from Yahoo Finance.
"""

from __future__ import annotations

from typing import Optional

import yfinance as yf

from app.models.company import Company
from app.providers.base_provider import BaseProvider



class CompanyProvider(
    BaseProvider,
):

    PROVIDER = "Yahoo Finance"

    def fetch(
        self,
        symbol: str,
    ) -> Optional[Company]:

        return self.get_company(
            symbol,
        )

    def get_company(
        self,
        symbol: str,
    ) -> Optional[Company]:

        try:

            normalized_symbol = self.normalize_symbol(
                symbol
            )

            ticker = yf.Ticker(
                normalized_symbol
            )

            info = ticker.info

            if not info:

                return None

            return Company(

                symbol=symbol,

                ticker=normalized_symbol,

                company_name=info.get(
                    "longName",
                ),

                sector=info.get(
                    "sector",
                ),

                industry=info.get(
                    "industry",
                ),

                exchange=info.get(
                    "exchange",
                ),

                currency=info.get(
                    "currency",
                ),

                country=info.get(
                    "country",
                ),

                website=info.get(
                    "website",
                ),

                market_cap=info.get(
                    "marketCap",
                ),

                employees=info.get(
                    "fullTimeEmployees",
                ),

            )

        except Exception as ex:

            self.logger.exception(
                ex,
            )

            return None

    # ---------------------------------------------------------
    # Health
    # ---------------------------------------------------------

    def health_check(
        self,
    ) -> bool:

        try:

            yf.Ticker(
                "^NSEI"
            ).history(
                period="1d"
            )

            return True

        except Exception:

            return False