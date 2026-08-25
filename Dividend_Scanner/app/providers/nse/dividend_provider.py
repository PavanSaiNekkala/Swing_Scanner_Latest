"""
NSE Dividend Provider

Fetches corporate actions from NSE using nselib.

Responsibilities
----------------
- Fetch corporate actions
- Filter dividend events
- Populate:
    * Ex Date
    * Record Date
    * Dividend Type
- Return Dividend models
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from typing import List

from loguru import logger
from nselib.capital_market import corporate_actions_for_equity

from app.models.dividend import Dividend
from app.providers.base_provider import BaseProvider


def parse_date(
    value: str | None,
):

    if value is None:
        return None

    value = str(value).strip()

    if value in (
        "",
        "-",
        "--",
        "NA",
        "N/A",
    ):
        return None

    try:

        return datetime.strptime(
            value,
            "%d-%b-%Y",
        ).date()

    except ValueError:

        logger.warning(
            "Unable to parse NSE date: {}",
            value,
        )

        return None


class DividendProvider(
    BaseProvider,
):

    PROVIDER = "NSE"

    LOOKBACK_YEARS = 15

    def get_dividends(

        self,

        symbol: str,

    ) -> List[Dividend]:

        try:

            today = datetime.today()

            start = today - timedelta(

                days=365 * self.LOOKBACK_YEARS,

            )

            df = corporate_actions_for_equity(

                from_date=start.strftime(

                    "%d-%m-%Y",

                ),

                to_date=today.strftime(

                    "%d-%m-%Y",

                ),

            )

            if df.empty:

                return []


            df = df.loc[
                df["symbol"].str.upper() == symbol.upper()
            ]

            if df.empty:

                return []

            df = df.loc[
                df["subject"]
                .fillna("")
                .str.contains(
                    "Dividend",
                    case=False,
                    regex=False,
                )
            ]

            if df.empty:

                return []

            dividends: List[Dividend] = []

            for _, row in df.iterrows():

                ex_date = parse_date(
                    row.get("exDate"),
                )

                # If the logged columns show "recordDate",
                # replace "recDate" below with "recordDate".
                record_date = parse_date(
                    row.get("recDate"),
                )

                payment_date = parse_date(
                    row.get("paymentDate"),
                )

                dividends.append(

                    Dividend(

                        symbol=symbol,

                        ex_date=ex_date,

                        record_date=record_date,

                        payment_date=payment_date,

                        amount=None,

                        dividend_type=row.get(
                            "subject",
                        ),

                        currency=None,

                    )

                )

            dividends.sort(

                key=lambda d: (

                    d.ex_date

                    or datetime.min.date()

                ),

                reverse=True,

            )

            return dividends

        except Exception as ex:

            logger.exception(

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

            corporate_actions_for_equity(

                from_date="01-01-2025",

                to_date="02-01-2025",

            )

            return True

        except Exception as ex:

            logger.exception(

                ex,

            )

            return False