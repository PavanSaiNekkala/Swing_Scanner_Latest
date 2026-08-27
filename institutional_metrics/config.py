from __future__ import annotations

from dataclasses import dataclass


# ============================================================
# MARKET CAP ADAPTIVE WEIGHTS
# ============================================================


@dataclass(frozen=True, slots=True)
class MarketCapWeightConfig:
    """
    Institutional factor allocation by market capitalization.
    """

    alpha_weight: float
    profitability_weight: float
    risk_weight: float
    robustness_weight: float
    efficiency_weight: float

    confidence_weight: float
    rs_weight: float
    stage2_weight: float
    news_weight: float

    def __post_init__(self) -> None:

        factor_total = (
            self.alpha_weight
            + self.profitability_weight
            + self.risk_weight
            + self.robustness_weight
            + self.efficiency_weight
        )

        if abs(
            factor_total - 1.0
        ) > 1e-9:

            raise ValueError(
                "Market cap factor weights must sum to 1.0"
            )

        ranking_total = (
            self.confidence_weight
            + self.rs_weight
            + self.stage2_weight
            + self.news_weight
        )

        if abs(
            ranking_total - 1.0
        ) > 1e-9:

            raise ValueError(
                "Rank score weights must sum to 1.0"
            )


# ============================================================
# LARGE CAP
# ============================================================

LARGE_CAP_CONFIG = MarketCapWeightConfig(

    alpha_weight=0.20,
    profitability_weight=0.30,
    risk_weight=0.25,
    robustness_weight=0.20,
    efficiency_weight=0.05,

    confidence_weight=0.45,
    rs_weight=0.25,
    stage2_weight=0.15,
    news_weight=0.15,
)


# ============================================================
# MID CAP
# ============================================================

MID_CAP_CONFIG = MarketCapWeightConfig(

    alpha_weight=0.30,
    profitability_weight=0.25,
    risk_weight=0.20,
    robustness_weight=0.20,
    efficiency_weight=0.05,

    confidence_weight=0.40,
    rs_weight=0.30,
    stage2_weight=0.20,
    news_weight=0.10,
)


# ============================================================
# SMALL CAP
# ============================================================

SMALL_CAP_CONFIG = MarketCapWeightConfig(

    alpha_weight=0.35,
    profitability_weight=0.20,
    risk_weight=0.20,
    robustness_weight=0.15,
    efficiency_weight=0.10,

    confidence_weight=0.35,
    rs_weight=0.30,
    stage2_weight=0.25,
    news_weight=0.10,
)



# ============================================================
# MAIN PIPELINE CONFIGURATION
# ============================================================


@dataclass(frozen=True, slots=True)
class InstitutionalMetricsConfig:
    """
    Global institutional metrics configuration.
    """


    # ---------------------------------------------------------
    # Default factor weights
    # ---------------------------------------------------------

    alpha_weight: float = 0.25
    profitability_weight: float = 0.25
    risk_weight: float = 0.20
    robustness_weight: float = 0.20
    efficiency_weight: float = 0.10


    # ---------------------------------------------------------
    # Alpha scoring
    # ---------------------------------------------------------

    exp_day_weight: float = 0.50
    relative_strength_weight: float = 0.50


    # ---------------------------------------------------------
    # Profitability scoring
    # ---------------------------------------------------------

    expectancy_weight: float = 0.40
    cagr_weight: float = 0.32
    profit_factor_weight: float = 0.28


    # ---------------------------------------------------------
    # Risk scoring
    # ---------------------------------------------------------

    drawdown_weight: float = 0.40
    recovery_factor_weight: float = 0.35
    consecutive_loss_weight: float = 0.25


    # ---------------------------------------------------------
    # Robustness scoring
    # ---------------------------------------------------------

    trades_weight: float = 0.35
    sequential_trades_weight: float = 0.25
    history_years_weight: float = 0.25
    win_rate_weight: float = 0.15


    # ---------------------------------------------------------
    # Efficiency scoring
    # ---------------------------------------------------------

    risk_reward_weight: float = 0.50
    holding_period_weight: float = 0.20
    trade_density_weight: float = 0.30


    # ---------------------------------------------------------
    # Rank Score
    # ---------------------------------------------------------

    confidence_weight: float = 0.40
    rs_tilt_weight: float = 0.25
    stage2_weight: float = 0.20
    news_weight: float = 0.15


    # ---------------------------------------------------------
    # Governance thresholds
    # Institutional quality filters
    # ---------------------------------------------------------

    minimum_trades: int = 50
    minimum_years: float = 3.0
    minimum_expectancy: float = 0.0
    minimum_cagr: float = 0.0
    minimum_profit_factor: float = 1.25
    minimum_recovery_factor: float = 1.0
    minimum_risk_reward: float = 1.0


    # ---------------------------------------------------------
    # Numerical configuration
    # ---------------------------------------------------------

    neutral_percentile: float = 50.0
    score_precision: int = 2



    # ---------------------------------------------------------
    # Market-cap mappings
    # ---------------------------------------------------------

    market_cap_configs: dict[str, MarketCapWeightConfig] = None


    def __post_init__(self) -> None:

        if self.market_cap_configs is None:

            object.__setattr__(
                self,
                "market_cap_configs",
                {
                    "LargeCap": LARGE_CAP_CONFIG,
                    "MidCap": MID_CAP_CONFIG,
                    "SmallCap": SMALL_CAP_CONFIG,
                },
            )


        factor_total = (
            self.alpha_weight
            + self.profitability_weight
            + self.risk_weight
            + self.robustness_weight
            + self.efficiency_weight
        )


        if abs(
            factor_total - 1.0
        ) > 1e-9:

            raise ValueError(
                "Major factor weights must sum to 1.0"
            )


        rank_total = (
            self.confidence_weight
            + self.rs_tilt_weight
            + self.stage2_weight
            + self.news_weight
        )


        if abs(
            rank_total - 1.0
        ) > 1e-9:

            raise ValueError(
                "Rank score weights must sum to 1.0"
            )