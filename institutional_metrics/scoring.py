from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)


class InstitutionalScorer:
    """
    Calculates institutional quality scores.

    Components:

    Alpha
    Profitability
    Risk
    Robustness
    Efficiency

    Final:

    Institutional Score =
        Quality Score
        +
        Conviction Contribution


    This module does NOT:

    - rank stocks
    - calculate news score
    - calculate stage2 score
    - calculate governance
    """


    def __init__(
        self,
        config: InstitutionalMetricsConfig,
    ) -> None:

        self.config = config



    # =========================================================
    # Percentile scoring
    # =========================================================


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

            &

            np.isfinite(values)

        )


        if not valid.any():

            return scores



        valid_values = values.loc[
            valid
        ]



        if valid_values.nunique() == 1:

            return scores



        scores.loc[valid] = (

            valid_values.rank(
                method="average",
                pct=True,
            )

            *

            100.0

        )


        return scores



    # =========================================================
    # Main scoring
    # =========================================================


    def calculate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:


        result = dataframe.copy()



        # -----------------------------------------------------
        # Market Cap Adaptive Weights
        # -----------------------------------------------------

        major_weights = (
            self._resolve_market_cap_weights(
                result
            )
        )



        # -----------------------------------------------------
        # Alpha
        # -----------------------------------------------------

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


        result[
            "Alpha Score"
        ] = (

            result[
                "Alpha - Exp/DAY Score"
            ]

            *

            self.config.exp_day_weight

            +

            result[
                "Alpha - RS Score"
            ]

            *

            self.config.relative_strength_weight

        )



        # -----------------------------------------------------
        # Profitability
        # -----------------------------------------------------

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

            *

            self.config.expectancy_weight


            +

            result[
                "Profitability - CAGR Score"
            ]

            *

            self.config.cagr_weight


            +

            result[
                "Profitability - Profit Factor Score"
            ]

            *

            self.config.profit_factor_weight

        )



        # -----------------------------------------------------
        # Risk
        # -----------------------------------------------------

        result[
            "Risk - Drawdown Score"
        ] = self.percentile(
            result["Max DD%"],
            reverse=True,
        )


        result[
            "Risk - Recovery Score"
        ] = self.percentile(
            result["Recovery factor"]
        )


        result[
            "Risk - Consecutive Loss Score"
        ] = self.percentile(
            result["Max consec. losses"],
            reverse=True,
        )


        result[
            "Risk Score"
        ] = (

            result[
                "Risk - Drawdown Score"
            ]

            *

            self.config.drawdown_weight


            +

            result[
                "Risk - Recovery Score"
            ]

            *

            self.config.recovery_factor_weight


            +

            result[
                "Risk - Consecutive Loss Score"
            ]

            *

            self.config.consecutive_loss_weight

        )



        # -----------------------------------------------------
        # Robustness
        # -----------------------------------------------------

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


        result[
            "Robustness Score"
        ] = (

            result[
                "Robustness - Trades Score"
            ]

            *

            self.config.trades_weight


            +

            result[
                "Robustness - Sequential Trades Score"
            ]

            *

            self.config.sequential_trades_weight


            +

            result[
                "Robustness - History Score"
            ]

            *

            self.config.history_years_weight


            +

            result[
                "Robustness - Win Rate Score"
            ]

            *

            self.config.win_rate_weight

        )



        # -----------------------------------------------------
        # Efficiency
        # -----------------------------------------------------

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


        result[
            "Efficiency Score"
        ] = (

            result[
                "Efficiency - R:R Score"
            ]

            *

            self.config.risk_reward_weight


            +

            result[
                "Efficiency - Holding Period Score"
            ]

            *

            self.config.holding_period_weight


            +

            result[
                "Efficiency - Trade Density Score"
            ]

            *

            self.config.trade_density_weight

        )



        # -----------------------------------------------------
        # Institutional Quality Contribution
        # -----------------------------------------------------

        result[
            "Alpha Contribution"
        ] = (

            result["Alpha Score"]

            *

            major_weights["alpha"]

        )


        result[
            "Profitability Contribution"
        ] = (

            result["Profitability Score"]

            *

            major_weights["profitability"]

        )


        result[
            "Risk Contribution"
        ] = (

            result["Risk Score"]

            *

            major_weights["risk"]

        )


        result[
            "Robustness Contribution"
        ] = (

            result["Robustness Score"]

            *

            major_weights["robustness"]

        )


        result[
            "Efficiency Contribution"
        ] = (

            result["Efficiency Score"]

            *

            major_weights["efficiency"]

        )



        result[
            "Quality Score"
        ] = (

            result[
                "Alpha Contribution"
            ]

            +

            result[
                "Profitability Contribution"
            ]

            +

            result[
                "Risk Contribution"
            ]

            +

            result[
                "Robustness Contribution"
            ]

            +

            result[
                "Efficiency Contribution"
            ]

        )



        # -----------------------------------------------------
        # Conviction Contribution
        # -----------------------------------------------------

        result[
            "Conviction Contribution"
        ] = (

            result.get(
                "Rank Score",
                50,
            )

            *

            0.15

        )



        # -----------------------------------------------------
        # Final Institutional Score
        # -----------------------------------------------------

        result[
            "Institutional Score"
        ] = (

            result[
                "Quality Score"
            ]

            *

            0.85


            +

            result[
                "Conviction Contribution"
            ]

        ).clip(
            0,
            100,
        )



        return result



    # =========================================================
    # Market Cap Weight Resolver
    # =========================================================


    def _resolve_market_cap_weights(
        self,
        dataframe: pd.DataFrame,
    ) -> dict[str, float]:


        if "Market Cap Category" not in dataframe.columns:

            return {

                "alpha":
                    self.config.alpha_weight,

                "profitability":
                    self.config.profitability_weight,

                "risk":
                    self.config.risk_weight,

                "robustness":
                    self.config.robustness_weight,

                "efficiency":
                    self.config.efficiency_weight,

            }


        # Future expansion point:
        #
        # Largecap
        # Midcap
        # Smallcap
        #
        # can be loaded from config profiles.


        return {

            "alpha":
                self.config.alpha_weight,

            "profitability":
                self.config.profitability_weight,

            "risk":
                self.config.risk_weight,

            "robustness":
                self.config.robustness_weight,

            "efficiency":
                self.config.efficiency_weight,

        }