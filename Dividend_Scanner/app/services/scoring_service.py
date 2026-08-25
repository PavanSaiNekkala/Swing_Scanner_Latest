"""
Scoring Service

Calculates the composite score for a scan result.
"""

from __future__ import annotations

from app.analytics.scoring import ScoringEngine
from app.models.score import Score


class ScoringService:

    def __init__(
        self,
        engine: ScoringEngine | None = None,
    ) -> None:

        self.engine = engine or ScoringEngine()

    def calculate(
        self,
        result,
    ) -> Score:

        # ---------------------------------------------------------
        # Dividend Score
        # ---------------------------------------------------------

        dividend_score = 0.0

        if result.dividend_yield is not None:

            dividend_score = min(

                result.dividend_yield,

                10.0,

            )

        # ---------------------------------------------------------
        # Return Score
        # ---------------------------------------------------------

        return_score = 0.0

        if result.window_return is not None:

            return_score = max(

                min(

                    result.window_return,

                    10.0,

                ),

                -10.0,

            )

        # ---------------------------------------------------------
        # Volume Score
        # ---------------------------------------------------------

        volume_score = 0.0

        if result.volume_change is not None:

            volume_score = max(

                min(

                    result.volume_change / 10,

                    10.0,

                ),

                -10.0,

            )

        # ---------------------------------------------------------
        # News Score
        # ---------------------------------------------------------

        news_score = 0.0

        if result.news_count >= 5:

            news_score = 5.0

        elif result.news_count >= 2:

            news_score = 2.5

        # ---------------------------------------------------------
        # Total Score
        # ---------------------------------------------------------

        total_score = self.engine.weighted_score(

            dividend_score,

            0.0,

            return_score,

            volume_score,

        )

        total_score += news_score

        # ---------------------------------------------------------
        # Recommendation
        # ---------------------------------------------------------

        if total_score >= 20:

            recommendation = "Strong Buy"

        elif total_score >= 15:

            recommendation = "Buy"

        elif total_score >= 10:

            recommendation = "Watch"

        else:

            recommendation = "Neutral"

        # ---------------------------------------------------------
        # Build Score Model
        # ---------------------------------------------------------

        return Score(

            dividend_score=round(

                dividend_score,

                2,

            ),

            return_score=round(

                return_score,

                2,

            ),

            volume_score=round(

                volume_score,

                2,

            ),

            news_score=round(

                news_score,

                2,

            ),

            total_score=round(

                total_score,

                2,

            ),

            recommendation=recommendation,

        )