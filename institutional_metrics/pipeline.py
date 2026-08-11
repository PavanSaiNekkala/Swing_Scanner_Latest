"""
Institutional Metrics + Recommendation + Telegram Pipeline.

Pipeline
--------
History / Institutional Engine
        ↓
Institutional Ranking
        ↓
Recommendation Engine
        ↓
Telegram Notification

The core metrics engine is injected as a dependency so this
orchestrator does not duplicate existing business logic.
"""

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
    """Base institutional pipeline exception."""


class RankingOutputError(
    InstitutionalPipelineError
):
    """Raised when institutional ranking output is invalid."""


class DuplicateDeliveryError(
    InstitutionalPipelineError
):
    """Raised when the same recommendation set was already sent."""


# ============================================================
# RESULT
# ============================================================


@dataclass(frozen=True, slots=True)
class InstitutionalPipelineResult:
    """
    Complete pipeline result.
    """

    ranking_dataframe: pd.DataFrame

    recommendation_result: RecommendationResult

    message: str

    sent_to_telegram: bool

    recommendation_fingerprint: str

    generated_at: datetime

    ranking_workbook: Path | None = None

    ranking_sheet: str = (
        DEFAULT_RANKING_SHEET
    )

    def __post_init__(self) -> None:

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
    Production orchestration service.

    The actual Institutional Metrics Engine is supplied through
    `ranking_builder`.

    This is intentionally dependency-injected because your
    existing loader/deduplicator/metrics/scoring/governance/
    ranker/exporter modules remain the source of truth.
    """

    def __init__(
        self,
        *,
        ranking_builder: Callable[
            [],
            pd.DataFrame,
        ],
        recommendation_engine: (
            InstitutionalRecommendationEngine
            | None
        ) = None,
        telegram_service: (
            TelegramNotificationService
            | None
        ) = None,
        ranking_sheet: str = (
            DEFAULT_RANKING_SHEET
        ),
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
    # MAIN EXECUTION
    # ========================================================

    def run(
        self,
        *,
        dry_run: bool = False,
        send_telegram: bool = True,
        generated_at: datetime | None = None,
    ) -> InstitutionalPipelineResult:
        """
        Execute the complete recommendation pipeline.
        """

        started_at = datetime.now()

        generated_at = (
            generated_at
            or started_at
        )

        logger.info(
            "Starting Institutional Pipeline."
        )

        # ----------------------------------------------------
        # STEP 1: BUILD INSTITUTIONAL RANKING
        # ----------------------------------------------------

        ranking_dataframe = (
            self._build_ranking()
        )

        logger.info(
            "Institutional ranking generated | "
            "Rows=%d | Columns=%d",
            len(ranking_dataframe),
            len(ranking_dataframe.columns),
        )

        # ----------------------------------------------------
        # STEP 2: SELECT RECOMMENDATIONS
        # ----------------------------------------------------

        recommendation_result = (
            self.recommendation_engine.select(
                ranking_dataframe
            )
        )

        recommendations = (
            recommendation_result.recommendations
        )

        logger.info(
            "Recommendation stage completed | "
            "Candidates=%d | Selected=%d",
            recommendation_result.candidate_count,
            recommendation_result.selected_count,
        )

        # ----------------------------------------------------
        # STEP 3: FINGERPRINT
        # ----------------------------------------------------

        fingerprint = (
            recommendation_fingerprint(
                recommendations
            )
        )

        # ----------------------------------------------------
        # STEP 4: TELEGRAM
        # ----------------------------------------------------

        message = ""

        sent_to_telegram = False

        if self.telegram_service is not None:

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

            sent_to_telegram = (
                send_telegram
                and not dry_run
            )

        else:

            logger.info(
                "Telegram service not configured."
            )

        # ----------------------------------------------------
        # STEP 5: COMPLETE
        # ----------------------------------------------------

        elapsed = (
            datetime.now()
            - started_at
        ).total_seconds()

        logger.info(
            "Institutional Pipeline completed | "
            "Selected=%d | "
            "TelegramSent=%s | "
            "Elapsed=%.2fs",
            recommendation_result.selected_count,
            sent_to_telegram,
            elapsed,
        )

        return InstitutionalPipelineResult(
            ranking_dataframe=ranking_dataframe,
            recommendation_result=(
                recommendation_result
            ),
            message=message,
            sent_to_telegram=(
                sent_to_telegram
            ),
            recommendation_fingerprint=(
                fingerprint
            ),
            generated_at=generated_at,
            ranking_sheet=self.ranking_sheet,
        )

    # ========================================================
    # RANKING BUILDER
    # ========================================================

    def _build_ranking(
        self,
    ) -> pd.DataFrame:
        """
        Execute the existing institutional metrics engine.
        """

        try:

            dataframe = (
                self.ranking_builder()
            )

        except Exception as exc:

            logger.exception(
                "Institutional ranking generation failed."
            )

            raise RankingOutputError(
                "Failed to generate Institutional_Ranking."
            ) from exc

        if not isinstance(
            dataframe,
            pd.DataFrame,
        ):

            raise RankingOutputError(
                "ranking_builder must return "
                "a pandas DataFrame."
            )

        if dataframe.empty:

            raise RankingOutputError(
                "Institutional_Ranking is empty."
            )

        required_columns = {
            "Stock",
            "Signals today",
            "Institutional Eligible",
            "Institutional Rank",
            "Institutional Score",
            "Institutional Rating",
            "Institutional Decision",
        }

        missing = sorted(
            required_columns
            - set(
                dataframe.columns
            )
        )

        if missing:

            raise RankingOutputError(
                "Institutional_Ranking is missing "
                f"required columns: {missing}"
            )

        return dataframe.copy()


# ============================================================
# EXCEL RANKING LOADER
# ============================================================


class ExcelRankingLoader:
    """
    Adapter for consuming an already-generated
    institutional_metrics.xlsx workbook.

    Useful for the GitHub downstream workflow where the
    scanner and institutional workbook already exist.
    """

    def __init__(
        self,
        workbook_path: str | Path,
        *,
        sheet_name: str = (
            DEFAULT_RANKING_SHEET
        ),
    ) -> None:

        self.workbook_path = Path(
            workbook_path
        )

        self.sheet_name = (
            sheet_name
        )

    def load(self) -> pd.DataFrame:
        """
        Load Institutional_Ranking.
        """

        if not self.workbook_path.exists():

            raise RankingOutputError(
                "Institutional ranking workbook "
                f"does not exist: "
                f"{self.workbook_path}"
            )

        if (
            self.workbook_path
            .suffix
            .lower()
            != ".xlsx"
        ):

            raise RankingOutputError(
                "Institutional ranking workbook "
                "must be an .xlsx file."
            )

        try:

            dataframe = pd.read_excel(
                self.workbook_path,
                sheet_name=self.sheet_name,
                engine="openpyxl",
            )

        except ValueError as exc:

            raise RankingOutputError(
                f"Sheet '{self.sheet_name}' was not "
                f"found in {self.workbook_path}."
            ) from exc

        except Exception as exc:

            raise RankingOutputError(
                "Failed to read institutional "
                "ranking workbook."
            ) from exc

        if dataframe.empty:

            raise RankingOutputError(
                f"Sheet '{self.sheet_name}' is empty."
            )

        logger.info(
            "Institutional ranking workbook loaded | "
            "File=%s | "
            "Sheet=%s | "
            "Rows=%d | "
            "Columns=%d",
            self.workbook_path,
            self.sheet_name,
            len(dataframe),
            len(dataframe.columns),
        )

        return dataframe


# ============================================================
# WORKBOOK-BASED PIPELINE FACTORY
# ============================================================


def build_workbook_pipeline(
    workbook_path: str | Path,
    *,
    telegram_service: (
        TelegramNotificationService
        | None
    ) = None,
    top_n: int = 5,
) -> InstitutionalPipeline:
    """
    Create a pipeline that consumes the existing
    Institutional_Ranking workbook.

    This is ideal for GitHub Actions.
    """

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
        telegram_service=(
            telegram_service
        ),
    )