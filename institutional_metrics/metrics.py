from __future__ import annotations

import numpy as np
import pandas as pd


class DerivedMetricsCalculator:
    """
    Calculates deterministic metrics from raw scanner fields.
    """

    def calculate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        result = dataframe.copy()

        numeric_columns = [
            "Rank",
            "Exp/DAY%",
            "RS%",
            "Trades",
            "Win%",
            "Target #",
            "Target %",
            "Trail #",
            "Trail %",
            "Stop #",
            "Stop %",
            "Time #",
            "Time %",
            "Time-win",
            "Time-loss",
            "MomExit #",
            "MomExit %",
            "Decay #",
            "Decay %",
            "Staircase #",
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

            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

        result["BT from"] = pd.to_datetime(
            result["BT from"],
            errors="coerce",
        )

        result["BT to"] = pd.to_datetime(
            result["BT to"],
            errors="coerce",
        )

        result["Loss %"] = (
            100.0
            - result["Win%"]
        )

        result["Trade Density"] = (
            result["Trades"]
            / result["Years"].replace(
                0,
                np.nan,
            )
        )

        result[
            "Sequential Trade Density"
        ] = (
            result["Seq. trades"]
            / result["Years"].replace(
                0,
                np.nan,
            )
        )

        win_probability = (
            result["Win%"]
            / 100.0
        )

        loss_probability = (
            1.0
            - win_probability
        )

        result[
            "Expected Return / Trade %"
        ] = (
            win_probability
            * result["Avg win%"]
            + loss_probability
            * result["Avg loss%"]
        )

        result["CAGR / Max DD"] = (
            result["CAGR%"]
            / result["Max DD%"]
            .abs()
            .replace(
                0,
                np.nan,
            )
        )

        result["Expectancy / Day"] = (
            result["Expectancy%"]
            / result["Avg days"]
            .replace(
                0,
                np.nan,
            )
        )

        result[
            "Expectancy × Profit Factor"
        ] = (
            result["Expectancy%"]
            * result["Profit factor"]
        )

        result[
            "Max DD Magnitude %"
        ] = result["Max DD%"].abs()

        result[
            "Backtest Duration Valid"
        ] = (
            result["BT from"].notna()
            & result["BT to"].notna()
            & (
                result["BT to"]
                >= result["BT from"]
            )
        )

        return result