from __future__ import annotations

import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)


class GovernanceEngine:
    """
    Applies institutional eligibility rules.
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

        gates = {
            "Minimum Trades": (
                result["Trades"]
                >= self.config.minimum_trades
            ),
            "Minimum History": (
                result["Years"]
                >= self.config.minimum_years
            ),
            "Positive Expectancy": (
                result["Expectancy%"]
                > self.config.minimum_expectancy
            ),
            "Positive CAGR": (
                result["CAGR%"]
                > self.config.minimum_cagr
            ),
            "Profit Factor": (
                result["Profit factor"]
                >= self.config.minimum_profit_factor
            ),
            "Recovery Factor": (
                result["Recovery factor"]
                > self.config.minimum_recovery_factor
            ),
            "Risk Reward": (
                result["R:R"]
                >= self.config.minimum_risk_reward
            ),
            "Valid Backtest": (
                result["Backtest Duration Valid"]
            ),
        }

        for name, condition in gates.items():

            result[
                f"Gate - {name}"
            ] = condition.astype(bool)

        gate_columns = [
            column
            for column in result.columns
            if column.startswith(
                "Gate - "
            )
        ]

        result[
            "Institutional Eligible"
        ] = [
            bool(value)
            for value in (
                result[gate_columns]
                .all(axis=1)
            )
        ]
        
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

        if row["Trades"] < self.config.minimum_trades:
            flags.append(
                "LOW_TRADE_COUNT"
            )

        if row["Years"] < self.config.minimum_years:
            flags.append(
                "LIMITED_HISTORY"
            )

        if row["Expectancy%"] <= 0:
            flags.append(
                "NON_POSITIVE_EXPECTANCY"
            )

        if row["CAGR%"] <= 0:
            flags.append(
                "NON_POSITIVE_CAGR"
            )

        if row["Profit factor"] < 1:
            flags.append(
                "PROFIT_FACTOR_BELOW_1"
            )

        if row["Recovery factor"] <= 0:
            flags.append(
                "NON_POSITIVE_RECOVERY"
            )

        if row["R:R"] < 1:
            flags.append(
                "LOW_RISK_REWARD"
            )

        if not row[
            "Backtest Duration Valid"
        ]:
            flags.append(
                "INVALID_BACKTEST_DATES"
            )

        return (
            "NONE"
            if not flags
            else "|".join(flags)
        )