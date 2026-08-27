from __future__ import annotations

import numpy as np
import pandas as pd


class DerivedMetricsCalculator:
    """
    Calculates deterministic institutional metrics
    from raw scanner fields.

    This module DOES NOT:
    - rank stocks
    - apply market-cap weights
    - calculate final Institutional Score
    - apply news/stage/RS adjustments
    """

    def calculate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        result = dataframe.copy()


        # -----------------------------------------------------
        # Numeric normalization
        # -----------------------------------------------------

        numeric_columns = [

            "Rank",
            "Exp/DAY%",
            "RS%",
            "Trades",
            "Win%",
            "Expectancy%",
            "Avg win%",
            "Avg loss%",
            "R:R",
            "Avg days",
            "Total return (sum)%",
            "CAGR%",
            "Max DD%",
            "Profit factor",
            "Recovery factor",
            "Max consec. losses",
            "Seq. trades",
            "Years",

        ]


        for column in numeric_columns:

            if column in result.columns:

                result[column] = pd.to_numeric(
                    result[column],
                    errors="coerce",
                )


        # -----------------------------------------------------
        # Backtest dates
        # -----------------------------------------------------

        result["BT from"] = pd.to_datetime(
            result["BT from"],
            errors="coerce",
        )


        result["BT to"] = pd.to_datetime(
            result["BT to"],
            errors="coerce",
        )


        # -----------------------------------------------------
        # Basic performance metrics
        # -----------------------------------------------------

        result["Loss %"] = (
            100.0
            -
            result["Win%"]
        )


        result["Trade Density"] = (

            result["Trades"]

            /

            result["Years"]
            .replace(
                0,
                np.nan,
            )

        )


        result[
            "Sequential Trade Density"
        ] = (

            result["Seq. trades"]

            /

            result["Years"]
            .replace(
                0,
                np.nan,
            )

        )


        # -----------------------------------------------------
        # Expected return
        # -----------------------------------------------------

        win_probability = (

            result["Win%"]

            /

            100.0

        )


        loss_probability = (
            1.0
            -
            win_probability
        )


        result[
            "Expected Return / Trade %"
        ] = (

            win_probability
            *
            result["Avg win%"]

            +

            loss_probability
            *
            result["Avg loss%"]

        )


        # -----------------------------------------------------
        # Risk adjusted returns
        # -----------------------------------------------------

        result[
            "CAGR / Max DD"
        ] = (

            result["CAGR%"]

            /

            result["Max DD%"]
            .abs()
            .replace(
                0,
                np.nan,
            )

        )


        result[
            "Expectancy / Day"
        ] = (

            result["Expectancy%"]

            /

            result["Avg days"]
            .replace(
                0,
                np.nan,
            )

        )


        result[
            "Expectancy × Profit Factor"
        ] = (

            result["Expectancy%"]

            *

            result["Profit factor"]

        )


        result[
            "Max DD Magnitude %"
        ] = (

            result["Max DD%"]
            .abs()

        )


        # -----------------------------------------------------
        # Backtest validity
        # -----------------------------------------------------

        result[
            "Backtest Duration Valid"
        ] = (

            result["BT from"].notna()

            &

            result["BT to"].notna()

            &

            (
                result["BT to"]
                >=
                result["BT from"]
            )

        ).astype(bool)



        # -----------------------------------------------------
        # Confidence Score
        #
        # Historical edge quality:
        #
        # expectancy
        # x win probability
        # x sample size reliability
        #
        # scaled 0-100
        # -----------------------------------------------------

        expectancy_factor = (

            result["Expectancy%"]
            .clip(
                lower=0
            )

        )


        win_rate_factor = (

            result["Win%"]
            /
            100.0

        )


        sample_size_factor = (

            result["Trades"]

            /

            (
                result["Trades"]
                +
                100
            )

        )


        result[
            "Confidence Score"
        ] = (

            expectancy_factor

            *

            win_rate_factor

            *

            sample_size_factor

            *

            10

        ).clip(
            upper=100
        )



        # -----------------------------------------------------
        # Confidence components
        # -----------------------------------------------------

        result[
            "Confidence - Expectancy Factor"
        ] = expectancy_factor


        result[
            "Confidence - Win Rate Factor"
        ] = win_rate_factor


        result[
            "Confidence - Sample Size Factor"
        ] = sample_size_factor



        return result