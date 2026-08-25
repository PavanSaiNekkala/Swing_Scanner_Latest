"""
Return Analytics

Calculates percentage returns over various windows.
"""

from __future__ import annotations

from typing import Optional


class ReturnAnalytics:

    # ---------------------------------------------------------
    # Percentage Return
    # ---------------------------------------------------------

    @staticmethod
    def percentage_return(

        start_price: float | None,

        end_price: float | None,

    ) -> Optional[float]:

        if (

            start_price is None

            or end_price is None

            or start_price <= 0

        ):

            return None

        return round(

            (

                end_price

                - start_price

            )

            / start_price

            * 100,

            2,

        )

    # ---------------------------------------------------------
    # Cumulative Return
    # ---------------------------------------------------------

    @classmethod
    def cumulative_return(

        cls,

        prices: list[float | None],

    ) -> Optional[float]:

        valid_prices = [

            price

            for price in prices

            if price is not None

        ]

        if len(

            valid_prices

        ) < 2:

            return None

        return cls.percentage_return(

            valid_prices[0],

            valid_prices[-1],

        )

    # ---------------------------------------------------------
    # Price Difference
    # ---------------------------------------------------------

    @staticmethod
    def price_change(

        start_price: float | None,

        end_price: float | None,

    ) -> Optional[float]:

        if (

            start_price is None

            or end_price is None

        ):

            return None

        return round(

            end_price

            - start_price,

            2,

        )

    # ---------------------------------------------------------
    # Annualized Return
    # ---------------------------------------------------------

    @staticmethod
    def annualized_return(

        start_price: float | None,

        end_price: float | None,

        years: float,

    ) -> Optional[float]:

        if (

            start_price is None

            or end_price is None

            or start_price <= 0

            or years <= 0

        ):

            return None

        return round(

            (

                (

                    end_price

                    / start_price

                )

                ** (

                    1 / years

                )

                - 1

            )

            * 100,

            2,

        )