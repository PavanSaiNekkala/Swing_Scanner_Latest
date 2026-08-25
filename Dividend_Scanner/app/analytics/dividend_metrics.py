"""
Dividend Metrics

Dividend-specific analytics.
"""

from __future__ import annotations

from collections import Counter
from datetime import date


class DividendMetrics:

    @staticmethod
    def years_since_first_dividend(
        first_dividend: date,
        today: date,
    ) -> int:

        return today.year - first_dividend.year


    @staticmethod
    def annual_dividend(
        dividends,
        today: date,
    ) -> float:

        one_year_ago = date(

            today.year - 1,

            today.month,

            today.day,

        )

        annual_amount = sum(

            dividend.amount

            for dividend in dividends

            if (

                dividend.amount is not None

                and dividend.ex_date is not None

                and dividend.ex_date >= one_year_ago

            )

        )

        return round(

            annual_amount,

            2,

        )


    @staticmethod
    def average_dividend(
        dividends,
        today: date,
    ) -> float:

        one_year_ago = date(

            today.year - 1,

            today.month,

            today.day,

        )

        recent = [

            dividend.amount

            for dividend in dividends

            if (

                dividend.amount is not None

                and dividend.ex_date is not None

                and dividend.ex_date >= one_year_ago

            )

        ]

        if not recent:

            return 0.0

        return round(

            sum(recent) / len(recent),

            2,

        )
        

    @staticmethod
    def latest_dividend(
        amounts: list[float],
    ) -> float:

        if not amounts:
            return 0.0

        return amounts[0]

    @staticmethod
    def dividend_yield(
        annual_dividend: float,
        current_price: float,
    ) -> float:

        if current_price <= 0:
            return 0.0

        return round(
            annual_dividend / current_price * 100,
            2,
        )

    @staticmethod
    def dividend_growth(
        previous: float,
        current: float,
    ) -> float:

        if previous <= 0:
            return 0.0

        return round(
            (current - previous) / previous * 100,
            2,
        )

    @staticmethod
    def dividend_frequency(
        ex_dates: list[date],
    ) -> str:

        if len(ex_dates) < 2:
            return "Unknown"

        counts = Counter(d.year for d in ex_dates)

        average = round(
            sum(counts.values()) / len(counts),
        )

        mapping = {
            1: "Annual",
            2: "Semi Annual",
            4: "Quarterly",
            12: "Monthly",
        }

        return mapping.get(
            average,
            f"{average}x / Year",
        )