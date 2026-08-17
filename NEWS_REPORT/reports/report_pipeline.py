"""
Institutional Report Pipeline

Responsibilities
----------------
- Orchestrate report generation
- Coordinate report exporters
- Validate report inputs
- Produce report artifacts
- Record execution statistics

This module intentionally DOES NOT

- Fetch market data
- Calculate returns
- Rank stocks
- Fetch news
- Summarize news
- Format Excel

Author
------
Pavan Sai Nekkala

Project
-------
NEWS_REPORT

Python
------
3.12+
"""

from __future__ import annotations

import time

from collections import defaultdict
from pathlib import Path

from config.logging_config import get_logger

from market.models import (
    ApplicationReport,
)

from reports.excel_exporter import (
    ExcelExporter,
    build_excel_exporter,
)

logger = get_logger(__name__)

###############################################################################
# Report Pipeline
###############################################################################


class ReportPipeline:
    """
    Institutional reporting pipeline.

    Responsible only for coordinating report exporters.
    """

    def __init__(
        self,
        excel_exporter: ExcelExporter,
    ) -> None:

        self.excel_exporter = (
            excel_exporter
        )

        self.statistics = defaultdict(
            int,
        )

        self.start_time = 0.0

        logger.info(
            "ReportPipeline initialized."
        )

###############################################################################
# Statistics
###############################################################################

    def reset_statistics(
        self,
    ) -> None:

        self.statistics.clear()

        self.start_time = (
            time.perf_counter()
        )

    def increment(
        self,
        metric: str,
        value: int = 1,
    ) -> None:

        self.statistics[
            metric
        ] += value

    def elapsed(
        self,
    ) -> float:

        return round(

            time.perf_counter()

            - self.start_time,

            2,

        )

###############################################################################
# Validation
###############################################################################

    @staticmethod
    def validate_inputs(
        report: ApplicationReport,
    ) -> None:
        """
        Validate reports before exporting.
        """

        if report is None:
            raise ValueError(
                "ApplicationReport cannot be None."
            )

        if report.market is None:
            raise ValueError(
                "MarketReport is missing."
            )

        if report.news is None:
            raise ValueError(
                "NewsReport is missing."
            )

        if not report.market.top_gainers:

            logger.warning(
                "MarketReport contains no gainers."
            )

        if not report.market.top_losers:

            logger.warning(
                "MarketReport contains no losers."
            )

###############################################################################
# Excel Export
###############################################################################

    def export_excel(
        self,
        report: ApplicationReport,
        output_file: Path | None = None,
    ) -> Path:
        """
        Generate Excel report.
        """

        logger.info(
            "Generating Excel report."
        )

        path = self.excel_exporter.export(
            report=report,
            output_file=output_file,
        )

        self.increment(
            "excel_reports",
        )

        return path

###############################################################################
# Execute Pipeline
###############################################################################

    def execute(
        self,
        report: ApplicationReport,
        output_file: Path | None = None,
    ) -> Path:
        """
        Execute the reporting pipeline.

        Workflow
        --------
            MarketReport
                  │
                  │
            NewsReport
                  │
                  ▼
            Validate Inputs
                  │
                  ▼
            Export Excel
                  │
                  ▼
          Return Generated File
        """

        logger.info(
            "=" * 80,
        )

        logger.info(
            "Starting Report Pipeline",
        )

        logger.info(
            "=" * 80,
        )

        self.reset_statistics()

        try:

            ###################################################################
            # Validation
            ###################################################################

            self.validate_inputs(
                report,
            )

            self.increment(
                "validated_reports",
            )

            ###################################################################
            # Excel Export
            ###################################################################

            report_path = self.export_excel(
                report=report,
                output_file=output_file,
            )

            ###################################################################
            # Statistics
            ###################################################################

            self.increment(
                "successful_runs",
            )

            self.log_statistics(
                report_path,
            )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "Report Pipeline Completed Successfully",
            )

            logger.info(
                "=" * 80,
            )

            return report_path

        except Exception:

            self.increment(
                "failed_runs",
            )

            logger.exception(
                "Report pipeline failed."
            )

            raise

###############################################################################
# Statistics
###############################################################################

    def log_statistics(
        self,
        report_path: Path,
    ) -> None:
        """
        Log execution statistics.
        """

        logger.info(
            "Execution Summary",
        )

        logger.info(
            "-" * 80,
        )

        logger.info(
            "Validated Reports : %d",
            self.statistics.get(
                "validated_reports",
                0,
            ),
        )

        logger.info(
            "Excel Reports     : %d",
            self.statistics.get(
                "excel_reports",
                0,
            ),
        )

        logger.info(
            "Successful Runs   : %d",
            self.statistics.get(
                "successful_runs",
                0,
            ),
        )

        logger.info(
            "Failed Runs       : %d",
            self.statistics.get(
                "failed_runs",
                0,
            ),
        )

        logger.info(
            "Execution Time    : %.2f sec",
            self.elapsed(),
        )

        logger.info(
            "Output File       : %s",
            report_path,
        )


###############################################################################
# Factory
###############################################################################

def build_report_pipeline(
    excel_exporter: ExcelExporter | None = None,
) -> ReportPipeline:
    """
    Factory for ReportPipeline.
    """

    pipeline = ReportPipeline(
        excel_exporter=excel_exporter
        or build_excel_exporter(),
    )

    logger.info(
        "ReportPipeline created."
    )

    return pipeline