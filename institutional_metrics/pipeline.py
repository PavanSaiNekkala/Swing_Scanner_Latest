from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import Callable, Final

import pandas as pd

from .recommendations import (
    InstitutionalRecommendationEngine,
    RecommendationConfig,
    RecommendationResult,
)

from .telegram import (
    TelegramNotificationService,
    recommendation_fingerprint,
)


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_RANKING_SHEET: Final[str] = (
    "Institutional_Ranking"
)


# ============================================================
# EXCEPTIONS
# ============================================================


class InstitutionalPipelineError(
    RuntimeError
):
    """
    Base pipeline exception.
    """


class RankingOutputError(
    InstitutionalPipelineError
):
    """
    Invalid institutional ranking output.
    """



# ============================================================
# RESULT
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class InstitutionalPipelineResult:
    """
    Final institutional recommendation result.
    """

    ranking_dataframe: pd.DataFrame

    recommendation_result: RecommendationResult

    message: str

    sent_to_telegram: bool

    recommendation_fingerprint: str

    generated_at: datetime

    ranking_sheet: str = (
        DEFAULT_RANKING_SHEET
    )

    def __post_init__(self):

        object.__setattr__(
            self,
            "ranking_dataframe",
            self.ranking_dataframe.copy(),
        )



# ============================================================
# PIPELINE
# ============================================================


class InstitutionalPipeline:
    """
    Production institutional orchestration layer.

    Responsibilities:

    - Consume institutional ranking output
    - Generate recommendations
    - Send notifications

    Does NOT:

    - Calculate metrics
    - Calculate scores
    - Apply governance
    - Rank stocks

    Those belong to InstitutionalMetricsEngine.
    """

    def __init__(
        self,
        *,
        ranking_builder: Callable[
            [],
            pd.DataFrame,
        ],
        recommendation_engine:
            InstitutionalRecommendationEngine
            | None = None,
        telegram_service:
            TelegramNotificationService
            | None = None,
        ranking_sheet: str = DEFAULT_RANKING_SHEET,
    ) -> None:


        self.ranking_builder = (
            ranking_builder
        )


        self.recommendation_engine = (
            recommendation_engine
            or InstitutionalRecommendationEngine(
                RecommendationConfig(
                    top_n=5,
                    allowed_decisions=frozenset(
                        {
                            "STRONG_BUY",
                            "BUY",
                        }
                    ),
                    require_signal=True,
                    require_eligible=True,
                    fail_if_empty=False,
                )
            )
        )


        self.telegram_service = (
            telegram_service
        )


        self.ranking_sheet = (
            ranking_sheet
        )



    # ========================================================
    # EXECUTION
    # ========================================================


    def run(
        self,
        *,
        dry_run: bool = False,
        send_telegram: bool = True,
        generated_at: datetime | None = None,
    ) -> InstitutionalPipelineResult:


        started = datetime.now()


        generated_at = (
            generated_at
            or started
        )


        logger.info(
            "Starting institutional recommendation pipeline."
        )


        ranking_dataframe = (
            self._build_ranking()
        )


        recommendation_result = (
            self.recommendation_engine.select(
                ranking_dataframe
            )
        )


        recommendations = (
            recommendation_result.recommendations
        )


        fingerprint = (
            recommendation_fingerprint(
                recommendations
            )
        )


        message = ""

        sent = False


        if self.telegram_service:

            message = (
                self.telegram_service
                .send_recommendations(
                    recommendations,
                    generated_at=generated_at,
                    candidate_count=(
                        recommendation_result
                        .candidate_count
                    ),
                    eligible_signal_count=(
                        recommendation_result
                        .eligible_signal_count
                    ),
                    dry_run=(
                        dry_run
                        or not send_telegram
                    ),
                )
            )


            sent = (
                send_telegram
                and not dry_run
            )


        elapsed = (
            datetime.now()
            - started
        ).total_seconds()


        logger.info(
            "Institutional pipeline completed | "
            "Selected=%d | "
            "Telegram=%s | "
            "Elapsed=%.2fs",
            recommendation_result.selected_count,
            sent,
            elapsed,
        )


        return InstitutionalPipelineResult(

            ranking_dataframe=ranking_dataframe,

            recommendation_result=(
                recommendation_result
            ),

            message=message,

            sent_to_telegram=sent,

            recommendation_fingerprint=fingerprint,

            generated_at=generated_at,

            ranking_sheet=self.ranking_sheet,

        )



    # ========================================================
    # VALIDATION
    # ========================================================


    def _build_ranking(
        self,
    ) -> pd.DataFrame:


        try:

            dataframe = (
                self.ranking_builder()
            )

        except Exception as error:

            raise RankingOutputError(
                "Institutional ranking generation failed."
            ) from error



        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):

            raise RankingOutputError(
                "Ranking builder must return DataFrame."
            )


        if dataframe.empty:

            raise RankingOutputError(
                "Institutional ranking is empty."
            )


        required_columns = {

            "Stock",

            "Signals today",

            "Rank Score",

            "Institutional Score",

            "Institutional Eligible",

            "Institutional Decision",

        }


        missing = sorted(
            required_columns
            -
            set(
                dataframe.columns
            )
        )


        if missing:

            raise RankingOutputError(
                "Missing institutional columns: "
                f"{missing}"
            )


        return dataframe.copy()



# ============================================================
# EXCEL ADAPTER
# ============================================================


class ExcelRankingLoader:

    def __init__(
        self,
        workbook_path: str | Path,
        *,
        sheet_name: str = DEFAULT_RANKING_SHEET,
    ) -> None:


        self.workbook_path = Path(
            workbook_path
        )

        self.sheet_name = sheet_name



    def load(self) -> pd.DataFrame:


        if not self.workbook_path.exists():

            raise RankingOutputError(
                f"Workbook missing: {self.workbook_path}"
            )


        try:

            dataframe = pd.read_excel(
                self.workbook_path,
                sheet_name=self.sheet_name,
                engine="openpyxl",
            )


        except Exception as error:

            raise RankingOutputError(
                "Unable to read ranking workbook."
            ) from error



        if dataframe.empty:

            raise RankingOutputError(
                "Ranking worksheet is empty."
            )


        return dataframe



# ============================================================
# FACTORY
# ============================================================


def build_workbook_pipeline(
    workbook_path: str | Path,
    *,
    telegram_service:
        TelegramNotificationService
        | None = None,
    top_n: int = 5,
) -> InstitutionalPipeline:


    loader = ExcelRankingLoader(
        workbook_path
    )


    recommendation_engine = (
        InstitutionalRecommendationEngine(
            RecommendationConfig(
                top_n=top_n,
                allowed_decisions=frozenset(
                    {
                        "STRONG_BUY",
                        "BUY",
                    }
                ),
                require_signal=True,
                require_eligible=True,
                fail_if_empty=False,
            )
        )
    )


    return InstitutionalPipeline(

        ranking_builder=loader.load,

        recommendation_engine=(
            recommendation_engine
        ),

        telegram_service=telegram_service,

    )