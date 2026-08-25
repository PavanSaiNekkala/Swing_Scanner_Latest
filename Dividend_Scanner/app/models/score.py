"""
Score Model

Represents the composite score calculated for a stock.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class Score(
    BaseModel,
):

    model_config = ConfigDict(

        frozen=True,

        from_attributes=True,

    )

    # ---------------------------------------------------------
    # Individual Scores
    # ---------------------------------------------------------

    dividend_score: float = 0.0

    return_score: float = 0.0

    volume_score: float = 0.0

    news_score: float = 0.0

    # ---------------------------------------------------------
    # Composite Score
    # ---------------------------------------------------------

    total_score: float = 0.0

    recommendation: str = "Neutral"