"""
Dividend Scoring Engine

Computes composite score.
"""

from __future__ import annotations

from app.models.scan_result import ScanResult


class ScoringEngine:

    @staticmethod
    def weighted_score(

        yield_score: float,

        consistency_score: float,

        return_score: float,

        volume_score: float,

    ) -> float:

        return round(

            (

                yield_score * 0.30

                + consistency_score * 0.30

                + return_score * 0.25

                + volume_score * 0.15

            ),

            2,

        )

    def score(

        self,

        result: ScanResult,

    ) -> float:

        # -------------------------------------------------
        # Temporary placeholders.
        # Replace with analytics calculations later.
        # -------------------------------------------------

        yield_score = 0.0

        consistency_score = 0.0

        return_score = 0.0

        volume_score = 0.0

        return self.weighted_score(

            yield_score,

            consistency_score,

            return_score,

            volume_score,

        )