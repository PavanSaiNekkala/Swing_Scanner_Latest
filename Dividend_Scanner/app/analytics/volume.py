"""
Volume Analytics

Volume calculations around ex-dividend events.
"""

from __future__ import annotations

from typing import Optional


class VolumeAnalytics:

    # ---------------------------------------------------------
    # Percentage Change
    # ---------------------------------------------------------

    @staticmethod
    def percentage_change(

        previous: int | None,

        current: int | None,

    ) -> Optional[float]:

        if (

            previous is None

            or current is None

            or previous <= 0

        ):

            return None

        return round(

            (

                current

                - previous

            )

            / previous

            * 100,

            2,

        )

    # ---------------------------------------------------------
    # Average Volume
    # ---------------------------------------------------------

    @staticmethod
    def average_volume(

        volumes: list[int | None],

    ) -> Optional[float]:

        valid = [

            volume

            for volume in volumes

            if volume is not None

        ]

        if not valid:

            return None

        return round(

            sum(valid)

            / len(valid),

            2,

        )

    # ---------------------------------------------------------
    # Volume Spike
    # ---------------------------------------------------------

    @classmethod
    def volume_spike(

        cls,

        average_volume: float | None,

        current_volume: int | None,

    ) -> Optional[float]:

        if (

            average_volume is None

            or average_volume <= 0

            or current_volume is None

        ):

            return None

        return round(

            (

                current_volume

                - average_volume

            )

            / average_volume

            * 100,

            2,

        )

    # ---------------------------------------------------------
    # Volume Ratio
    # ---------------------------------------------------------

    @staticmethod
    def volume_ratio(

        current_volume: int | None,

        average_volume: float | None,

    ) -> Optional[float]:

        if (

            current_volume is None

            or average_volume is None

            or average_volume <= 0

        ):

            return None

        return round(

            current_volume

            / average_volume,

            2,

        )

    # ---------------------------------------------------------
    # Simple Volume Score
    # ---------------------------------------------------------

    @classmethod
    def score(

        cls,

        average_volume: float | None,

        current_volume: int | None,

    ) -> float:

        spike = cls.volume_spike(

            average_volume,

            current_volume,

        )

        if spike is None:

            return 0.0

        if spike >= 100:

            return 10.0

        if spike >= 50:

            return 8.0

        if spike >= 25:

            return 6.0

        if spike >= 10:

            return 4.0

        return 2.0