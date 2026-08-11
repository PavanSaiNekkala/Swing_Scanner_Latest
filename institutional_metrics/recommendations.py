"""
Institutional Recommendation Engine.

Responsibilities
----------------
1. Validate the Institutional_Ranking dataframe.
2. Restrict candidates to active signals.
3. Restrict candidates to institutionally eligible stocks.
4. Restrict recommendations to configured decisions.
5. Rank candidates deterministically.
6. Return the Top-N recommendations.
7. Produce summary statistics for downstream notification.

This module contains NO Telegram/API logic.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Final

import pandas as pd


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

STOCK_COLUMN: Final[str] = "Stock"
SIGNAL_COLUMN: Final[str] = "Signals today"
ELIGIBLE_COLUMN: Final[str] = "Institutional Eligible"
RANK_COLUMN: Final[str] = "Institutional Rank"
SCORE_COLUMN: Final[str] = "Institutional Score"
RATING_COLUMN: Final[str] = "Institutional Rating"
DECISION_COLUMN: Final[str] = "Institutional Decision"


REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    STOCK_COLUMN,
    SIGNAL_COLUMN,
    ELIGIBLE_COLUMN,
    RANK_COLUMN,
    SCORE_COLUMN,
    RATING_COLUMN,
    DECISION_COLUMN,
)


DEFAULT_RECOMMENDATION_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "STRONG_BUY",
        "BUY",
    }
)


# ============================================================
# EXCEPTIONS
# ============================================================


class RecommendationError(RuntimeError):
    """Base recommendation-engine exception."""


class RecommendationSchemaError(RecommendationError):
    """Raised when required ranking columns are missing."""


class NoRecommendationsError(RecommendationError):
    """Raised when no stock satisfies the recommendation policy."""


# ============================================================
# CONFIGURATION
# ============================================================


@dataclass(frozen=True, slots=True)
class RecommendationConfig:
    """
    Production configuration for institutional recommendations.
    """

    top_n: int = 5

    allowed_decisions: frozenset[str] = (
        DEFAULT_RECOMMENDATION_DECISIONS
    )

    require_signal: bool = True

    require_eligible: bool = True

    fail_if_empty: bool = False

    def __post_init__(self) -> None:

        if self.top_n <= 0:
            raise ValueError(
                "top_n must be greater than zero."
            )

        if not self.allowed_decisions:
            raise ValueError(
                "allowed_decisions cannot be empty."
            )


# ============================================================
# RESULT
# ============================================================


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    """
    Immutable recommendation result.

    Attributes
    ----------
    recommendations:
        Final Top-N recommendation dataframe.

    candidate_count:
        Number of stocks after recommendation filters.

    eligible_signal_count:
        Number of active institutionally eligible signals.

    selected_count:
        Number of stocks selected for notification.
    """

    recommendations: pd.DataFrame

    candidate_count: int

    eligible_signal_count: int

    selected_count: int

    def __post_init__(self) -> None:

        object.__setattr__(
            self,
            "recommendations",
            self.recommendations.copy(),
        )


# ============================================================
# ENGINE
# ============================================================


class InstitutionalRecommendationEngine:
    """
    Selects institutional-quality stock recommendations.

    Selection policy
    ----------------
    1. Active signal.
    2. Institutional eligibility.
    3. STRONG_BUY / BUY decision.
    4. Institutional Rank ascending.
    5. Institutional Score descending.
    6. Stock ascending as deterministic tie-breaker.
    """

    def __init__(
        self,
        config: RecommendationConfig | None = None,
    ) -> None:

        self.config = (
            config
            if config is not None
            else RecommendationConfig()
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def select(
        self,
        dataframe: pd.DataFrame,
    ) -> RecommendationResult:
        """
        Select Top-N institutional recommendations.
        """

        validated = self._validate_dataframe(
            dataframe
        )

        working = validated.copy()

        working[
            STOCK_COLUMN
        ] = (
            working[
                STOCK_COLUMN
            ]
            .astype("string")
            .str.strip()
            .str.upper()
        )

        working[
            SIGNAL_COLUMN
        ] = self._to_bool(
            working[
                SIGNAL_COLUMN
            ]
        )

        working[
            ELIGIBLE_COLUMN
        ] = self._to_bool(
            working[
                ELIGIBLE_COLUMN
            ]
        )

        working[
            RANK_COLUMN
        ] = pd.to_numeric(
            working[
                RANK_COLUMN
            ],
            errors="coerce",
        )

        working[
            SCORE_COLUMN
        ] = pd.to_numeric(
            working[
                SCORE_COLUMN
            ],
            errors="coerce",
        )

        working[
            DECISION_COLUMN
        ] = (
            working[
                DECISION_COLUMN
            ]
            .astype("string")
            .str.strip()
            .str.upper()
        )

        # ----------------------------------------------------
        # ACTIVE SIGNAL FILTER
        # ----------------------------------------------------

        if self.config.require_signal:

            working = working.loc[
                working[
                    SIGNAL_COLUMN
                ]
            ].copy()

        # ----------------------------------------------------
        # ELIGIBILITY FILTER
        # ----------------------------------------------------

        eligible_signal_count = int(
            (
                working[
                    ELIGIBLE_COLUMN
                ]
            )
            .sum()
        )

        if self.config.require_eligible:

            working = working.loc[
                working[
                    ELIGIBLE_COLUMN
                ]
            ].copy()

        # ----------------------------------------------------
        # DECISION FILTER
        # ----------------------------------------------------

        working = working.loc[
            working[
                DECISION_COLUMN
            ].isin(
                self.config.allowed_decisions
            )
        ].copy()

        # ----------------------------------------------------
        # REMOVE INVALID RANK/SCORE
        # ----------------------------------------------------

        working = working.loc[
            working[
                RANK_COLUMN
            ].notna()
            & working[
                SCORE_COLUMN
            ].notna()
        ].copy()

        candidate_count = len(
            working
        )

        # ----------------------------------------------------
        # DETERMINISTIC RANKING
        # ----------------------------------------------------

        working = working.sort_values(
            by=[
                RANK_COLUMN,
                SCORE_COLUMN,
                STOCK_COLUMN,
            ],
            ascending=[
                True,
                False,
                True,
            ],
            kind="stable",
        )

        recommendations = (
            working
            .head(
                self.config.top_n
            )
            .copy()
        )

        recommendations[
            "Recommendation Rank"
        ] = range(
            1,
            len(
                recommendations
            )
            + 1,
        )

        recommendations = (
            recommendations.reset_index(
                drop=True
            )
        )

        selected_count = len(
            recommendations
        )

        logger.info(
            "Institutional recommendations generated | "
            "EligibleSignals=%d | "
            "Candidates=%d | "
            "Selected=%d",
            eligible_signal_count,
            candidate_count,
            selected_count,
        )

        if (
            selected_count == 0
            and self.config.fail_if_empty
        ):
            raise NoRecommendationsError(
                "No stocks satisfy the institutional "
                "recommendation policy."
            )

        return RecommendationResult(
            recommendations=recommendations,
            candidate_count=candidate_count,
            eligible_signal_count=eligible_signal_count,
            selected_count=selected_count,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_dataframe(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Validate the Institutional_Ranking dataframe.
        """

        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):
            raise TypeError(
                "dataframe must be a pandas DataFrame."
            )

        if dataframe.empty:
            raise RecommendationSchemaError(
                "Institutional ranking dataframe is empty."
            )

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in dataframe.columns
        ]

        if missing:
            raise RecommendationSchemaError(
                "Institutional ranking dataframe is missing "
                f"required columns: {missing}"
            )

        result = dataframe.copy()

        if (
            result[
                STOCK_COLUMN
            ]
            .astype("string")
            .str.strip()
            .eq("")
            .any()
        ):
            raise RecommendationSchemaError(
                "Institutional ranking contains blank Stock values."
            )

        return result

    # ========================================================
    # BOOLEAN NORMALIZATION
    # ========================================================

    @staticmethod
    def _to_bool(
        series: pd.Series,
    ) -> pd.Series:
        """
        Safely normalize boolean-like scanner fields.
        """

        if pd.api.types.is_bool_dtype(
            series
        ):
            return series.fillna(
                False
            )

        normalized = (
            series
            .astype("string")
            .str.strip()
            .str.lower()
        )

        return normalized.isin(
            {
                "true",
                "1",
                "yes",
                "y",
                "signal",
                "signalled",
                "signaled",
            }
        )


# ============================================================
# CONVENIENCE API
# ============================================================


def select_top_recommendations(
    dataframe: pd.DataFrame,
    *,
    top_n: int = 5,
) -> RecommendationResult:
    """
    Convenience function for selecting Top-N recommendations.
    """

    engine = (
        InstitutionalRecommendationEngine(
            RecommendationConfig(
                top_n=top_n,
            )
        )
    )

    return engine.select(
        dataframe
    )