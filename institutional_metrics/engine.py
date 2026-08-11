from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)
from .deduplicator import (
    StockDeduplicator,
)
from .exporter import (
    InstitutionalExporter,
)
from .governance import (
    GovernanceEngine,
)
from .loader import (
    HistoryLoader,
)
from .metrics import (
    DerivedMetricsCalculator,
)
from .ranker import (
    InstitutionalRanker,
)
from .scoring import (
    InstitutionalScorer,
)


@dataclass(frozen=True, slots=True)
class InstitutionalBuildResult:
    """
    Immutable result of one institutional metrics build.
    """

    universe: pd.DataFrame
    signals: pd.DataFrame
    duplicates: pd.DataFrame
    csv_path: Path
    excel_path: Path


class InstitutionalMetricsEngine:
    """
    End-to-end institutional metrics pipeline.

    Flow:

        Excel history
            ↓
        Latest Scan discovery
            ↓
        Combine
            ↓
        Deduplicate
            ↓
        Derived metrics
            ↓
        Factor scores
            ↓
        Governance
            ↓
        Institutional Rank
            ↓
        Excel + CSV
    """

    def __init__(
        self,
        config: InstitutionalMetricsConfig | None = None,
    ) -> None:

        self.config = (
            config
            or InstitutionalMetricsConfig()
        )

        self.loader = HistoryLoader

        self.deduplicator = (
            StockDeduplicator()
        )

        self.metrics = (
            DerivedMetricsCalculator()
        )

        self.scorer = (
            InstitutionalScorer(
                self.config
            )
        )

        self.governance = (
            GovernanceEngine(
                self.config
            )
        )

        self.ranker = (
            InstitutionalRanker()
        )

        self.exporter = (
            InstitutionalExporter()
        )

    def run(
        self,
        *,
        history_directory: Path,
        output_directory: Path,
    ) -> InstitutionalBuildResult:

        loader = self.loader(
            history_directory
        )

        loaded_sheets = loader.load()

        combined = pd.concat(
            [
                item.dataframe
                for item in loaded_sheets
            ],
            ignore_index=True,
        )

        universe, duplicates = (
            self.deduplicator.deduplicate(
                combined
            )
        )

        universe = (
            self.metrics.calculate(
                universe
            )
        )

        universe = (
            self.scorer.calculate(
                universe
            )
        )

        universe = (
            self.governance.apply(
                universe
            )
        )

        universe = (
            self.ranker.rank(
                universe
            )
        )

        universe = (
            self.ranker.classify(
                universe
            )
        )

        universe[
            "Institutional Score"
        ] = (
            universe[
                "Institutional Score"
            ].round(
                self.config.score_precision
            )
        )

        signals = (
            universe[
                universe[
                    "Signals today"
                ].astype(bool)
            ]
            .copy()
            .sort_values(
                by=[
                    "Institutional Rank",
                    "Stock",
                ],
                kind="stable",
            )
        )

        csv_path, excel_path = (
            self.exporter.export(
                dataframe=universe,
                duplicates=duplicates,
                output_directory=output_directory,
            )
        )

        return InstitutionalBuildResult(
            universe=universe,
            signals=signals,
            duplicates=duplicates,
            csv_path=csv_path,
            excel_path=excel_path,
        )