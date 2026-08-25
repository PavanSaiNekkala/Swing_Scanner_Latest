"""
Dividend Merger

Merges Yahoo dividend history with NSE corporate actions.
"""

from __future__ import annotations

from app.models.dividend import Dividend
from datetime import timedelta


class DividendMerger:

    @staticmethod
    def merge(

        yahoo: list[Dividend],

        nse: list[Dividend],

    ) -> list[Dividend]:

        if not yahoo:

            return nse

        if not nse:

            return yahoo

        merged: list[Dividend] = []

        for yahoo_dividend in yahoo:

            match = next(

                (

                    nse_dividend

                    for nse_dividend in nse

                    if (

                        nse_dividend.ex_date

                        and yahoo_dividend.ex_date

                        and abs(

                            (

                                nse_dividend.ex_date

                                - yahoo_dividend.ex_date

                            ).days

                        ) <= 1

                    )

                ),

                None,

            )



            if match:

                merged.append(

                    yahoo_dividend.model_copy(

                        update={

                            "record_date": (

                                match.record_date

                                or yahoo_dividend.record_date

                            ),

                            "payment_date": (

                                match.payment_date

                                or yahoo_dividend.payment_date

                            ),

                            "dividend_type": (

                                match.dividend_type

                                or yahoo_dividend.dividend_type

                            ),

                        },

                    )

                )

            else:

                merged.append(

                    yahoo_dividend,

                )

        return merged