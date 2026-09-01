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

ELIGIBLE_COLUMN: Final[str] = (
    "Institutional Eligible"
)

RANK_SCORE_COLUMN: Final[str] = (
    "Rank Score"
)

SCORE_COLUMN: Final[str] = (
    "Institutional Score"
)

RATING_COLUMN: Final[str] = (
    "Institutional Rating"
)

DECISION_COLUMN: Final[str] = (
    "Institutional Decision"
)



REQUIRED_COLUMNS: Final[tuple[str,...]] = (

    STOCK_COLUMN,

    SIGNAL_COLUMN,

    ELIGIBLE_COLUMN,

    RANK_SCORE_COLUMN,

    SCORE_COLUMN,

    RATING_COLUMN,

    DECISION_COLUMN,

)


DEFAULT_DECISIONS: Final[frozenset[str]] = frozenset(
    {
        "STRONG_BUY",
        "BUY",
    }
)


# ============================================================
# EXCEPTIONS
# ============================================================

class RecommendationError(RuntimeError):
    pass


class RecommendationSchemaError(
    RecommendationError
):
    pass



class NoRecommendationsError(
    RecommendationError
):
    pass



# ============================================================
# CONFIG
# ============================================================

@dataclass(
    frozen=True,
    slots=True,
)
class RecommendationConfig:

    top_n: int = 5

    require_signal: bool = True

    require_eligible: bool = True

    allowed_decisions: frozenset[str] = (
        DEFAULT_DECISIONS
    )

    fail_if_empty: bool = False

    def __post_init__(self):

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

@dataclass(
    frozen=True,
    slots=True,
)
class RecommendationResult:

    recommendations: pd.DataFrame

    selected_count: int

    candidate_count: int

    eligible_signal_count: int


    def __post_init__(self):

        object.__setattr__(
            self,
            "recommendations",
            self.recommendations.copy(),
        )


# ============================================================
# ENGINE
# ============================================================

class InstitutionalRecommendationEngine:


    def __init__(
        self,
        config: RecommendationConfig | None = None,
    ):


        self.config = (
            config
            if config is not None
            else RecommendationConfig()
        )



    def select(
        self,
        dataframe: pd.DataFrame,
    ) -> RecommendationResult:


        working = (
            self._validate_dataframe(
                dataframe
            )
        )


        working = working.copy()


        working[STOCK_COLUMN] = (
            working[STOCK_COLUMN]
            .astype("string")
            .str.strip()
            .str.upper()
        )


        working[SIGNAL_COLUMN] = (

            self._to_bool(
                working[SIGNAL_COLUMN]
            )

        )



        working[ELIGIBLE_COLUMN] = (
            self._to_bool(
                working[ELIGIBLE_COLUMN]
            )
        )


        working[RANK_SCORE_COLUMN] = pd.to_numeric(
            working[RANK_SCORE_COLUMN],
            errors="coerce",

        )


        working[SCORE_COLUMN] = pd.to_numeric(
            working[SCORE_COLUMN],
            errors="coerce",
        )


        working[DECISION_COLUMN] = (

            working[DECISION_COLUMN]
            .astype("string")
            .str.strip()
            .str.upper()

        )



        # ----------------------------------------------------
        # Active institutional signals
        # ----------------------------------------------------


        working = working.loc[

            working[SIGNAL_COLUMN]

            &

            working[ELIGIBLE_COLUMN]

        ].copy()



        # ----------------------------------------------------
        # Decision filter
        # ----------------------------------------------------


        working = working.loc[

            working[DECISION_COLUMN]

            .isin(
                self.config.allowed_decisions
            )

        ].copy()



        # ----------------------------------------------------
        # Remove invalid scoring rows
        # ----------------------------------------------------


        working = working.loc[

            working[RANK_SCORE_COLUMN]
            .notna()

            &

            working[SCORE_COLUMN]
            .notna()

        ].copy()



        candidate_count = len(
            working
        )



        if candidate_count == 0:


            if self.config.fail_if_empty:

                raise NoRecommendationsError(

                    "No institutional recommendations found."

                )



            return RecommendationResult(

                recommendations=working,

                candidate_count=0,

                selected_count=0,

                eligible_signal_count=0,

            )



        # ----------------------------------------------------
        # Institutional selection
        # ----------------------------------------------------


        recommendations = (

            working
            .sort_values(
                by=[
                    "Institutional Priority Score",
                    RANK_SCORE_COLUMN,
                    SCORE_COLUMN,
                    STOCK_COLUMN,
                ],

                ascending=[
                    False,
                    False,
                    False,
                    True,
                ],
                kind="stable",
            )
            .head(
                self.config.top_n
            )
            .copy()
        )



        recommendations[
            "Recommendation Rank"
        ] = range(
            1,
            len(recommendations)+1,
        )



        logger.info(

            "Institutional recommendations generated | "
            "Candidates=%d | Selected=%d",

            candidate_count,
            len(recommendations),

        )


        return RecommendationResult(

            recommendations=recommendations,

            candidate_count=int(
                dataframe[
                    ELIGIBLE_COLUMN
                ]
                .astype(bool)
                .sum()
            ),

            selected_count=len(
                recommendations
            ),

            eligible_signal_count=int(
                dataframe[
                    SIGNAL_COLUMN
                ]
                .astype(bool)
                .sum()
            ),

        )



    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_dataframe(
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:


        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):

            raise TypeError(
                "Expected pandas DataFrame."
            )



        missing = [

            column
            for column in REQUIRED_COLUMNS
            if column not in dataframe.columns

        ]



        if missing:

            raise RecommendationSchemaError(

                f"Missing columns: {missing}"

            )



        return dataframe.copy()




    # ========================================================
    # BOOLEAN NORMALIZATION
    # ========================================================


    @staticmethod
    def _to_bool(
        series: pd.Series,
    ) -> pd.Series:


        if pd.api.types.is_bool_dtype(
            series
        ):

            return series.fillna(
                False
            )



        return (

            series
            .astype("string")
            .str.lower()
            .isin(

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
        )



# ============================================================
# Convenience API
# ============================================================

def select_top_recommendations(
    dataframe: pd.DataFrame,
    *,
    top_n: int = 5,
) -> RecommendationResult:


    return InstitutionalRecommendationEngine(

        RecommendationConfig(
            top_n=top_n,
        )

    ).select(
        dataframe
    )
