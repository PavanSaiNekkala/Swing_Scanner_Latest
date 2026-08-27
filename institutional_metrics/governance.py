from __future__ import annotations

import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)



class GovernanceEngine:
    """
    Applies institutional eligibility rules.

    Responsibilities:

    - Hard risk gates
    - Backtest quality checks
    - Institutional eligibility

    Does NOT:

    - calculate scores
    - rank stocks
    - decide BUY/SELL
    """



    def __init__(
        self,
        config: InstitutionalMetricsConfig,
    ) -> None:

        self.config = config



    def apply(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:


        result = dataframe.copy()



        # -----------------------------------------------------
        # Governance Gates
        # -----------------------------------------------------

        gates = {


            "Minimum Trades":

                result[
                    "Trades"
                ]

                >=

                self.config.minimum_trades,



            "Minimum History":

                result[
                    "Years"
                ]

                >=

                self.config.minimum_years,



            "Positive Expectancy":

                result[
                    "Expectancy%"
                ]

                >

                self.config.minimum_expectancy,



            "Positive CAGR":

                result[
                    "CAGR%"
                ]

                >

                self.config.minimum_cagr,



            "Profit Factor":

                result[
                    "Profit factor"
                ]

                >=

                self.config.minimum_profit_factor,



            "Recovery Factor":

                result[
                    "Recovery factor"
                ]

                >

                self.config.minimum_recovery_factor,



            "Risk Reward":

                result[
                    "R:R"
                ]

                >=

                self.config.minimum_risk_reward,



            "Valid Backtest":

                result[
                    "Backtest Duration Valid"
                ]
                .astype(bool),

        }



        for name, condition in gates.items():


            result[
                f"Gate - {name}"
            ] = (

                condition

                .fillna(False)

                .astype(bool)

            )



        gate_columns = [

            column

            for column in result.columns

            if column.startswith(
                "Gate - "
            )

        ]



        result[
            "Institutional Eligible"
        ] = (

            result[
                gate_columns
            ]

            .all(
                axis=1
            )

        )



        # -----------------------------------------------------
        # Governance flags
        # -----------------------------------------------------

        result[
            "Governance Flags"
        ] = result.apply(

            self._flags,

            axis=1,

        )



        return result





    def _flags(
        self,
        row: pd.Series,
    ) -> str:


        flags: list[str] = []



        if (
            row["Trades"]
            <
            self.config.minimum_trades
        ):

            flags.append(
                "LOW_TRADE_COUNT"
            )



        if (
            row["Years"]
            <
            self.config.minimum_years
        ):

            flags.append(
                "LIMITED_HISTORY"
            )



        if (
            row["Expectancy%"]
            <=
            self.config.minimum_expectancy
        ):

            flags.append(
                "NON_POSITIVE_EXPECTANCY"
            )



        if (
            row["CAGR%"]
            <=
            self.config.minimum_cagr
        ):

            flags.append(
                "NON_POSITIVE_CAGR"
            )



        if (
            row["Profit factor"]
            <
            self.config.minimum_profit_factor
        ):

            flags.append(
                "PROFIT_FACTOR_BELOW_THRESHOLD"
            )



        if (
            row["Recovery factor"]
            <=
            self.config.minimum_recovery_factor
        ):

            flags.append(
                "RECOVERY_FACTOR_BELOW_THRESHOLD"
            )



        if (
            row["R:R"]
            <
            self.config.minimum_risk_reward
        ):

            flags.append(
                "LOW_RISK_REWARD"
            )



        if not bool(
            row[
                "Backtest Duration Valid"
            ]
        ):

            flags.append(
                "INVALID_BACKTEST"
            )



        # -----------------------------------------------------
        # Conviction quality flags
        # -----------------------------------------------------

        if "Rank Score" in row.index:


            if row["Rank Score"] < 50:

                flags.append(
                    "LOW_CONVICTION"
                )



        if not flags:

            return "NONE"



        return "|".join(flags)