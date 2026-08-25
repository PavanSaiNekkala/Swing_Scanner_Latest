"""
OHLC Window Analytics

Calculates trading-day windows around a dividend ex-date.
Builds D-3 ... D+3 market window and analytics.
"""

from __future__ import annotations

from datetime import date
from typing import Dict
from typing import List
from typing import Any

import exchange_calendars as xcals
import pandas as pd
from exchange_calendars.errors import DateOutOfBounds

from app.analytics.returns import ReturnAnalytics
from app.analytics.volume import VolumeAnalytics
from app.models.market import MarketData


class OHLCWindow:

    WINDOW_BEFORE = 3
    WINDOW_AFTER = 3
    WINDOW_SIZE = WINDOW_BEFORE + WINDOW_AFTER + 1

    def __init__(
        self,
        exchange: str = "XBOM",
    ) -> None:

        try:

            self.calendar = xcals.get_calendar(
                exchange,
            )

        except Exception:

            self.calendar = xcals.get_calendar(
                "XBOM",
            )

    # ---------------------------------------------------------
    # Trading Window
    # ---------------------------------------------------------

    def trading_days(
        self,
        ex_date: date,
        before: int = WINDOW_BEFORE,
        after: int = WINDOW_AFTER,
    ) -> List[date]:

        ex = pd.Timestamp(
            ex_date,
        )

        try:

            sessions = self.calendar.sessions_in_range(

                ex - pd.Timedelta(days=30),

                ex + pd.Timedelta(days=30),

            )

        except DateOutOfBounds:

            return []

        sessions = list(
            sessions,
        )

        if ex not in sessions:

            ex = self.calendar.date_to_session(

                ex,

                direction="next",

            )

        index = sessions.index(
            ex,
        )

        window = sessions[
            index - before:
            index + after + 1
        ]

        return [

            day.date()

            for day in window

        ]

    # ---------------------------------------------------------
    # Date Range
    # ---------------------------------------------------------

    def date_range(
        self,
        ex_date: date,
        before: int = WINDOW_BEFORE,
        after: int = WINDOW_AFTER,
    ) -> tuple[date, date]:

        window = self.trading_days(

            ex_date,

            before,

            after,

        )

        if not window:

            return (

                ex_date,

                ex_date,

            )

        return (

            window[0],

            window[-1],

        )

    # ---------------------------------------------------------
    # Build Complete Window
    # ---------------------------------------------------------

    def build_window(
        self,
        ex_date: date,
        history: List[MarketData],
    ) -> Dict[str, Any]:

        trading_days = self.trading_days(
            ex_date,
        )

        if len(trading_days) != self.WINDOW_SIZE:

            return {}

        history_map = {

            row.trading_date: row

            for row in history

        }

        prices: List[float | None] = []

        volumes: List[int | None] = []

        for day in trading_days:

            candle = history_map.get(
                day,
            )

            if candle:

                prices.append(
                    candle.close,
                )

                volumes.append(
                    candle.volume,
                )

            else:

                prices.append(
                    None,
                )

                volumes.append(
                    None,
                )

        if None in prices:

            return {}

        returns = self.calculate_window_returns(
            prices,
        )

        return {

            # -------------------------------------------------
            # Trading Dates
            # -------------------------------------------------

            "d_minus_3_date": trading_days[0],
            "d_minus_2_date": trading_days[1],
            "d_minus_1_date": trading_days[2],
            "d0_date": trading_days[3],
            "d_plus_1_date": trading_days[4],
            "d_plus_2_date": trading_days[5],
            "d_plus_3_date": trading_days[6],

            # -------------------------------------------------
            # ScanResult field names
            # -------------------------------------------------

            "d3_close": prices[0],
            "d2_close": prices[1],
            "d1_close": prices[2],
            "d0_close": prices[3],
            "p1_close": prices[4],
            "p2_close": prices[5],
            "p3_close": prices[6],

            # -------------------------------------------------
            # Returns
            # -------------------------------------------------

            "window_return": returns.get(
                "window_return",
            ),

            "d3_to_d0_return": returns.get(
                "d3_to_d0",
            ),

            "d2_to_d0_return": returns.get(
                "d2_to_d0",
            ),

            "d1_to_d0_return": returns.get(
                "d1_to_d0",
            ),

            "d0_to_p1_return": returns.get(
                "d0_to_p1",
            ),

            "d0_to_p2_return": returns.get(
                "d0_to_p2",
            ),

            "d0_to_p3_return": returns.get(
                "d0_to_p3",
            ),

            # -------------------------------------------------
            # Volume
            # -------------------------------------------------

            "previous_volume": volumes[2],

            "ex_day_volume": volumes[3],

            "average_volume": VolumeAnalytics.average_volume(
                [
                    volume
                    for volume in volumes
                    if volume is not None
                ],
            ),

            "volume_change": self.calculate_volume_change(
                volumes[2],
                volumes[3],
            ),

        }

    # ---------------------------------------------------------
    # Returns
    # ---------------------------------------------------------

    @staticmethod
    def calculate_window_returns(
        closes: List[float],
    ) -> Dict[str, float | None]:

        if len(closes) != 7:

            return {}

        return {

            "d3_to_d0":

                ReturnAnalytics.percentage_return(

                    closes[0],

                    closes[3],

                ),

            "d2_to_d0":

                ReturnAnalytics.percentage_return(

                    closes[1],

                    closes[3],

                ),

            "d1_to_d0":

                ReturnAnalytics.percentage_return(

                    closes[2],

                    closes[3],

                ),

            "d0_to_p1":

                ReturnAnalytics.percentage_return(

                    closes[3],

                    closes[4],

                ),

            "d0_to_p2":

                ReturnAnalytics.percentage_return(

                    closes[3],

                    closes[5],

                ),

            "d0_to_p3":

                ReturnAnalytics.percentage_return(

                    closes[3],

                    closes[6],

                ),

            "window_return":

                ReturnAnalytics.cumulative_return(

                    closes,

                ),

        }

    # ---------------------------------------------------------
    # Volume
    # ---------------------------------------------------------

    @staticmethod
    def calculate_volume_change(

        previous_volume: int | None,

        current_volume: int | None,

    ) -> float | None:

        return VolumeAnalytics.percentage_change(

            previous_volume,

            current_volume,

        )