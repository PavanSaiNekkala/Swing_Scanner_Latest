from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)


class ConvictionCalculator:
    """
    Calculates conviction and final Rank Score.

    Formula:

    Rank Score =
        Confidence
        × RS Tilt
        × Freshness
        × Extension Penalty
        × Stage2 Boost
        × News Tilt
    """


    def __init__(
        self,
        config: InstitutionalMetricsConfig,
    ) -> None:

        self.config = config
        

    def calculate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        result = dataframe.copy()


        # -----------------------------------------------------
        # Confidence
        #
        # Historical edge quality:
        #
        # expectancy
        # × win rate
        # × sample reliability
        #
        # -----------------------------------------------------

        result[
            "Confidence"
        ] = self._confidence(
            result
        )


        # -----------------------------------------------------
        # Relative Strength Tilt
        #
        # RS > 0 rewards leaders
        # RS < 0 penalizes laggards
        #
        # bounded ±50%
        #
        # -----------------------------------------------------

        result[
            "RS Tilt"
        ] = self._rs_tilt(
            result
        )


        # -----------------------------------------------------
        # Stage 2 Boost
        #
        # Uses existing Stage-2 score
        #
        # 100 score => +15%
        # 0 score   => -15%
        #
        # -----------------------------------------------------

        result[
            "Stage2 Boost"
        ] = self._stage2_boost(
            result
        )


        # -----------------------------------------------------
        # Freshness
        #
        # Recent signals preferred
        #
        # -----------------------------------------------------

        result[
            "Freshness"
        ] = self._freshness(
            result
        )


        # -----------------------------------------------------
        # Extension Penalty
        #
        # Avoid late extended entries
        #
        # -----------------------------------------------------

        result[
            "Extension Penalty"
        ] = self._extension_penalty(
            result
        )


        # -----------------------------------------------------
        # News Tilt
        #
        # Optional.
        #
        # Defaults neutral when news unavailable.
        #
        # -----------------------------------------------------

        result[
            "News Tilt"
        ] = self._news_tilt(
            result
        )


        # -----------------------------------------------------
        # Final Conviction Rank Score
        # -----------------------------------------------------

        result[
            "Rank Score"
        ] = (

            result["Confidence"]

            *

            result["RS Tilt"]

            *

            result["Freshness"]

            *

            result["Extension Penalty"]

            *

            result["Stage2 Boost"]

            *

            result["News Tilt"]

        )


        return result



    # =========================================================
    # Confidence
    # =========================================================


    @staticmethod
    def _confidence(
        dataframe: pd.DataFrame,
    ) -> pd.Series:

        expectancy = (

            dataframe[
                "Expectancy%"
            ]
            .clip(
                lower=0
            )

        )


        win_rate = (

            dataframe[
                "Win%"
            ]
            /
            100.0

        )


        sample = (

            dataframe[
                "Trades"
            ]

            /

            (

                dataframe[
                    "Trades"
                ]

                +

                100

            )

        )


        score = (

            expectancy

            *

            win_rate

            *

            sample

            *

            10

        )


        return score.clip(
            lower=0,
            upper=100,
        )



    # =========================================================
    # Relative Strength Tilt
    # =========================================================


    @staticmethod
    def _rs_tilt(
        dataframe: pd.DataFrame,
    ) -> pd.Series:


        rs = (

            dataframe[
                "RS%"
            ]
            .fillna(
                0
            )

        )


        tilt = (

            1

            +

            (
                rs
                /
                100
            )

        )


        return tilt.clip(
            lower=0.5,
            upper=1.5,
        )



    # =========================================================
    # Stage 2 Boost
    # =========================================================


    @staticmethod
    def _stage2_boost(
        dataframe: pd.DataFrame,
    ) -> pd.Series:


        if (
            "Stage2 Score"
            not in dataframe.columns
        ):

            return pd.Series(
                1.0,
                index=dataframe.index,
            )


        score = (

            dataframe[
                "Stage2 Score"
            ]
            .fillna(
                50
            )

        )


        return (

            0.85

            +

            (

                score
                /
                100
            )
            *
            0.30

        )



    # =========================================================
    # Freshness
    # =========================================================


    @staticmethod
    def _freshness(
        dataframe: pd.DataFrame,
    ) -> pd.Series:


        if (
            "Signal Date"
            not in dataframe.columns
        ):

            return pd.Series(
                1.0,
                index=dataframe.index,
            )


        age = (

            pd.Timestamp.utcnow()

            -

            pd.to_datetime(
                dataframe[
                    "Signal Date"
                ],
                errors="coerce",
            )

        ).dt.days


        age = age.fillna(
            30
        )


        return (

            1

            -

            (
                age
                /
                60
            )

        ).clip(
            lower=0.5,
            upper=1.0,
        )



    # =========================================================
    # Extension Penalty
    # =========================================================


    @staticmethod
    def _extension_penalty(
        dataframe: pd.DataFrame,
    ) -> pd.Series:


        if (
            "Extension %"
            not in dataframe.columns
        ):

            return pd.Series(
                1.0,
                index=dataframe.index,
            )


        extension = (

            dataframe[
                "Extension %"
            ]
            .fillna(
                0
            )

        )


        penalty = (

            1

            -

            (
                extension
                /
                20
            )

        )


        return penalty.clip(
            lower=0.7,
            upper=1.1,
        )



    # =========================================================
    # News Tilt
    # =========================================================


    @staticmethod
    def _news_tilt(
        dataframe: pd.DataFrame,
    ) -> pd.Series:


        if (
            "News Score"
            not in dataframe.columns
        ):

            return pd.Series(
                1.0,
                index=dataframe.index,
            )


        score = (

            dataframe[
                "News Score"
            ]
            .fillna(
                50
            )

        )


        return (

            0.75

            +

            (

                score
                /
                100
            )
            *
            0.50

        )