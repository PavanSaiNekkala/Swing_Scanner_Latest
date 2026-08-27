from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import (
    InstitutionalMetricsConfig,
)

from .conviction import (
    ConvictionCalculator,
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



@dataclass(
    frozen=True,
    slots=True,
)
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

    Pipeline:

        Excel history
            ↓
        Load
            ↓
        Combine
            ↓
        Deduplicate
            ↓
        Derived Metrics
            ↓
        Conviction Engine
            ↓
        Institutional Scoring
            ↓
        Governance
            ↓
        Institutional Ranking
            ↓
        Export


    Responsibilities:

    - Pipeline orchestration only

    Does NOT:

    - Calculate raw metrics
    - Calculate conviction factors
    - Calculate scores
    - Apply governance rules
    - Export formatting logic

    """



    def __init__(
        self,
        config: InstitutionalMetricsConfig | None = None,
    ) -> None:


        self.config = (
            config
            or InstitutionalMetricsConfig()
        )


        self.loader = (
            HistoryLoader
        )


        self.deduplicator = (
            StockDeduplicator()
        )


        self.metrics = (
            DerivedMetricsCalculator()
        )


        self.conviction = (
            ConvictionCalculator(
                self.config
            )
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


        # -----------------------------------------------------
        # LOAD HISTORY WORKBOOKS
        # -----------------------------------------------------

        loader = self.loader(
            history_directory
        )


        loaded_sheets = (
            loader.load()
        )


        combined = pd.concat(
            [
                item.dataframe
                for item in loaded_sheets
            ],
            ignore_index=True,
        )



        # -----------------------------------------------------
        # DEDUPLICATION
        # -----------------------------------------------------

        universe, duplicates = (

            self.deduplicator.deduplicate(
                combined
            )

        )



        # -----------------------------------------------------
        # DERIVED METRICS
        # -----------------------------------------------------

        universe = (

            self.metrics.calculate(
                universe
            )

        )



        # -----------------------------------------------------
        # CONVICTION MODEL
        #
        # Creates:
        #
        # Confidence
        # RS Tilt
        # Stage2 Boost
        # Freshness
        # News Tilt
        # Rank Score
        #
        # -----------------------------------------------------

        universe = (

            self.conviction.calculate(
                universe
            )

        )



        # -----------------------------------------------------
        # INSTITUTIONAL SCORING
        #
        # Creates:
        #
        # Alpha Score
        # Profitability Score
        # Risk Score
        # Robustness Score
        # Efficiency Score
        # Institutional Score
        #
        # -----------------------------------------------------

        universe = (

            self.scorer.calculate(
                universe
            )

        )



        # -----------------------------------------------------
        # GOVERNANCE
        #
        # Creates:
        #
        # Gate columns
        # Institutional Eligible
        # Governance Flags
        #
        # -----------------------------------------------------

        universe = (

            self.governance.apply(
                universe
            )

        )



        # -----------------------------------------------------
        # FINAL RANKING
        #
        # Uses:
        #
        # Institutional Eligibility
        # Rank Score
        # Institutional Score
        #
        # -----------------------------------------------------

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



        # -----------------------------------------------------
        # VALIDATE FINAL OUTPUT
        # -----------------------------------------------------

        self._validate_output(
            universe
        )



        # -----------------------------------------------------
        # ROUND SCORES
        # -----------------------------------------------------

        score_columns = [

            "Confidence",

            "Rank Score",

            "Alpha Score",

            "Profitability Score",

            "Risk Score",

            "Robustness Score",

            "Efficiency Score",

            "Alpha Contribution",

            "Profitability Contribution",

            "Risk Contribution",

            "Robustness Contribution",

            "Efficiency Contribution",

            "Institutional Score",

        ]


        universe[
            score_columns
        ] = universe[
            score_columns
        ].round(
            self.config.score_precision
        )



        # -----------------------------------------------------
        # EXTRACT SIGNALS
        # -----------------------------------------------------

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

                    "Institutional Score",

                    "Rank Score",

                    "Stock",

                ],

                ascending=[

                    True,

                    False,

                    False,

                    True,

                ],

                kind="stable",

            )

        )



        # -----------------------------------------------------
        # EXPORT
        # -----------------------------------------------------

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




    @staticmethod
    def _validate_output(
        dataframe: pd.DataFrame,
    ) -> None:


        required_columns = {

            "Stock",

            "Signals today",

            "Rank Score",

            "Institutional Score",

            "Institutional Eligible",

            "Institutional Rank",

            "Institutional Rating",

            "Institutional Decision",

        }


        missing = (

            required_columns

            -

            set(
                dataframe.columns
            )

        )


        if missing:

            raise RuntimeError(
                "Institutional output validation failed. "
                f"Missing columns: {sorted(missing)}"
            )