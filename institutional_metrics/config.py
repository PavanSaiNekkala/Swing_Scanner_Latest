from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InstitutionalMetricsConfig:
    """
    Configuration for the institutional metrics pipeline.
    """

    # ---------------------------------------------------------
    # Factor weights
    # ---------------------------------------------------------

    alpha_weight: float = 0.25
    profitability_weight: float = 0.25
    risk_weight: float = 0.20
    robustness_weight: float = 0.20
    efficiency_weight: float = 0.10

    # ---------------------------------------------------------
    # Alpha
    # ---------------------------------------------------------

    exp_day_weight: float = 0.50
    relative_strength_weight: float = 0.50

    # ---------------------------------------------------------
    # Profitability
    # ---------------------------------------------------------

    expectancy_weight: float = 0.40
    cagr_weight: float = 0.32
    profit_factor_weight: float = 0.28

    # ---------------------------------------------------------
    # Risk
    # ---------------------------------------------------------

    drawdown_weight: float = 0.40
    recovery_factor_weight: float = 0.35
    consecutive_loss_weight: float = 0.25

    # ---------------------------------------------------------
    # Robustness
    # ---------------------------------------------------------

    trades_weight: float = 0.35
    sequential_trades_weight: float = 0.25
    history_years_weight: float = 0.25
    win_rate_weight: float = 0.15

    # ---------------------------------------------------------
    # Efficiency
    # ---------------------------------------------------------

    risk_reward_weight: float = 0.50
    holding_period_weight: float = 0.20
    trade_density_weight: float = 0.30

    # ---------------------------------------------------------
    # Governance thresholds
    # ---------------------------------------------------------

    minimum_trades: int = 50
    minimum_years: float = 5.0
    minimum_expectancy: float = 0.0
    minimum_cagr: float = 0.0
    minimum_profit_factor: float = 1.0
    minimum_recovery_factor: float = 0.0
    minimum_risk_reward: float = 1.0

    # ---------------------------------------------------------
    # Numerical configuration
    # ---------------------------------------------------------

    neutral_percentile: float = 50.0
    score_precision: int = 2

    def __post_init__(self) -> None:
        major_weights = (
            self.alpha_weight
            + self.profitability_weight
            + self.risk_weight
            + self.robustness_weight
            + self.efficiency_weight
        )

        if abs(major_weights - 1.0) > 1e-9:
            raise ValueError(
                "Major factor weights must sum to 1.0."
            )

        groups = {
            "alpha": (
                self.exp_day_weight,
                self.relative_strength_weight,
            ),
            "profitability": (
                self.expectancy_weight,
                self.cagr_weight,
                self.profit_factor_weight,
            ),
            "risk": (
                self.drawdown_weight,
                self.recovery_factor_weight,
                self.consecutive_loss_weight,
            ),
            "robustness": (
                self.trades_weight,
                self.sequential_trades_weight,
                self.history_years_weight,
                self.win_rate_weight,
            ),
            "efficiency": (
                self.risk_reward_weight,
                self.holding_period_weight,
                self.trade_density_weight,
            ),
        }

        for name, weights in groups.items():

            if abs(sum(weights) - 1.0) > 1e-9:
                raise ValueError(
                    f"{name} weights must sum to 1.0."
                )