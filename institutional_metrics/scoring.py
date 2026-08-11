from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)


class InstitutionalScorer:
    """
    Calculates cross-sectional institutional factor scores.
    """

    def __init__(
        self,
        config: InstitutionalMetricsConfig,
    ) -> None:

        self.config = config

    def percentile(
        self,
        series: pd.Series,
        *,
        reverse: bool = False,
    ) -> pd.Series:

        values = pd.to_numeric(
            series,
            errors="coerce",
        )

        if reverse:
            values = -values

        scores = pd.Series(
            self.config.neutral_percentile,
            index=series.index,
            dtype=float,
        )

        valid = (
            values.notna()
            & np.isfinite(values)
        )

        if not valid.any():
            return scores

        valid_values = values.loc[
            valid
        ]

        if valid_values.nunique() == 1:

            scores.loc[
                valid
            ] = self.config.neutral_percentile

            return scores

        scores.loc[
            valid
        ] = (
            valid_values.rank(
                method="average",
                pct=True,
            )
            * 100.0
        )

        return scores

    def calculate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        result = dataframe.copy()

        # =====================================================
        # ALPHA
        # =====================================================

        result[
            "Alpha - Exp/DAY Score"
        ] = self.percentile(
            result["Exp/DAY%"]
        )

        result[
            "Alpha - RS Score"
        ] = self.percentile(
            result["RS%"]
        )

        result["Alpha Score"] = (
            result[
                "Alpha - Exp/DAY Score"
            ]
            * self.config.exp_day_weight
            + result[
                "Alpha - RS Score"
            ]
            * self.config.relative_strength_weight
        )

        # =====================================================
        # PROFITABILITY
        # =====================================================

        result[
            "Profitability - Expectancy Score"
        ] = self.percentile(
            result["Expectancy%"]
        )

        result[
            "Profitability - CAGR Score"
        ] = self.percentile(
            result["CAGR%"]
        )

        result[
            "Profitability - Profit Factor Score"
        ] = self.percentile(
            result["Profit factor"]
        )

        result[
            "Profitability Score"
        ] = (
            result[
                "Profitability - Expectancy Score"
            ]
            * self.config.expectancy_weight
            + result[
                "Profitability - CAGR Score"
            ]
            * self.config.cagr_weight
            + result[
                "Profitability - Profit Factor Score"
            ]
            * self.config.profit_factor_weight
        )

        # =====================================================
        # RISK
        # =====================================================

        result[
            "Risk - Drawdown Score"
        ] = self.percentile(
            result["Max DD%"]
        )

        result[
            "Risk - Recovery Score"
        ] = self.percentile(
            result["Recovery factor"]
        )

        result[
            "Risk - Consecutive Loss Score"
        ] = self.percentile(
            result[
                "Max consec. losses"
            ],
            reverse=True,
        )

        result["Risk Score"] = (
            result[
                "Risk - Drawdown Score"
            ]
            * self.config.drawdown_weight
            + result[
                "Risk - Recovery Score"
            ]
            * self.config.recovery_factor_weight
            + result[
                "Risk - Consecutive Loss Score"
            ]
            * self.config.consecutive_loss_weight
        )

        # =====================================================
        # ROBUSTNESS
        # =====================================================

        result[
            "Robustness - Trades Score"
        ] = self.percentile(
            result["Trades"]
        )

        result[
            "Robustness - Sequential Trades Score"
        ] = self.percentile(
            result["Seq. trades"]
        )

        result[
            "Robustness - History Score"
        ] = self.percentile(
            result["Years"]
        )

        result[
            "Robustness - Win Rate Score"
        ] = self.percentile(
            result["Win%"]
        )

        result["Robustness Score"] = (
            result[
                "Robustness - Trades Score"
            ]
            * self.config.trades_weight
            + result[
                "Robustness - Sequential Trades Score"
            ]
            * self.config.sequential_trades_weight
            + result[
                "Robustness - History Score"
            ]
            * self.config.history_years_weight
            + result[
                "Robustness - Win Rate Score"
            ]
            * self.config.win_rate_weight
        )

        # =====================================================
        # EFFICIENCY
        # =====================================================

        result[
            "Efficiency - R:R Score"
        ] = self.percentile(
            result["R:R"]
        )

        result[
            "Efficiency - Holding Period Score"
        ] = self.percentile(
            result["Avg days"],
            reverse=True,
        )

        result[
            "Efficiency - Trade Density Score"
        ] = self.percentile(
            result["Trade Density"]
        )

        result["Efficiency Score"] = (
            result[
                "Efficiency - R:R Score"
            ]
            * self.config.risk_reward_weight
            + result[
                "Efficiency - Holding Period Score"
            ]
            * self.config.holding_period_weight
            + result[
                "Efficiency - Trade Density Score"
            ]
            * self.config.trade_density_weight
        )

        # =====================================================
        # CONTRIBUTIONS
        # =====================================================

        result[
            "Alpha Contribution"
        ] = (
            result["Alpha Score"]
            * self.config.alpha_weight
        )

        result[
            "Profitability Contribution"
        ] = (
            result["Profitability Score"]
            * self.config.profitability_weight
        )

        result[
            "Risk Contribution"
        ] = (
            result["Risk Score"]
            * self.config.risk_weight
        )

        result[
            "Robustness Contribution"
        ] = (
            result["Robustness Score"]
            * self.config.robustness_weight
        )

        result[
            "Efficiency Contribution"
        ] = (
            result["Efficiency Score"]
            * self.config.efficiency_weight
        )

        result[
            "Institutional Score"
        ] = (
            result["Alpha Contribution"]
            + result[
                "Profitability Contribution"
            ]
            + result[
                "Risk Contribution"
            ]
            + result[
                "Robustness Contribution"
            ]
            + result[
                "Efficiency Contribution"
            ]
        ).clip(
            0,
            100,
        )

        return result