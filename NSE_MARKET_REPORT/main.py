"""
==============================================================================
File        : main.py
Project     : NSE Market Report

Description
-----------
Application entry point.

Responsibilities
----------------
✓ Initialize services
✓ Perform health checks
✓ Collect market data
✓ Enrich report
✓ Generate AI summary
✓ Generate AI remarks
✓ Format report
✓ Export Excel
✓ Export CSV
✓ Print statistics
✓ Cleanup resources

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from tqdm import tqdm

import pandas as pd

from config.logging_config import logger
from config.settings import VERSION

from data.market_data import MarketData
from data.ohlc import OHLCData

from news.news_manager import NewsManager

from ai.summarizer import AISummarizer
from ai.remarks import AIRemarks

from reports.formatter import ReportFormatter
from reports.excel_export import ExcelExporter
from reports.csv_export import CSVExporter


###############################################################################
# APPLICATION
###############################################################################


class NSEMarketReport:
    """
    NSE Market Report Application.

    Workflow
    --------
    initialize
        ↓
    health check
        ↓
    collect market data
        ↓
    OHLC enrichment
        ↓
    News enrichment
        ↓
    AI Summary
        ↓
    AI Remarks
        ↓
    Formatting
        ↓
    Excel Export
        ↓
    CSV Export
        ↓
    Statistics
        ↓
    Cleanup
    """

    ###########################################################################

    def __init__(
        self,
    ) -> None:
        """
        Initialize application services.
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "Initializing NSE Market Report"
        )

        logger.info(
            "=" * 80
        )

        self.started_at = datetime.now()

        self.report_df: pd.DataFrame = pd.DataFrame()

        self.excel_file: Optional[Path] = None

        self.csv_file: Optional[Path] = None

        #######################################################################
        # DATA SERVICES
        #######################################################################

        self.market = MarketData()

        self.ohlc = OHLCData()

        #######################################################################
        # NEWS
        #######################################################################

        self.news = NewsManager()

        #######################################################################
        # AI
        #######################################################################

        self.ai_summary = AISummarizer()

        self.ai_remarks = AIRemarks()

        #######################################################################
        # REPORTING
        #######################################################################

        self.formatter = ReportFormatter()

        self.excel = ExcelExporter()

        self.csv = CSVExporter()

        logger.info(
            "All services initialized successfully."
        )

        logger.info("")


###############################################################################
# HEALTH CHECK
###############################################################################

    def health_check(
        self,
    ) -> None:
        """
        Verify every application service.
        """

        logger.info("")

        logger.info(
            "=" * 80
        )

        logger.info(
            "SYSTEM HEALTH CHECK"
        )

        logger.info(
            "=" * 80
        )

        services = {

            "Market Data": self.market,

            "OHLC": self.ohlc,

            "News": self.news,

            "AI Summary": self.ai_summary,

            "AI Remarks": self.ai_remarks,

            "Formatter": self.formatter,

            "Excel Exporter": self.excel,

            "CSV Exporter": self.csv,

        }

        for name, service in services.items():

            try:

                status = service.health_check()
                logger.info(
                    "%-20s : %s",
                    name,
                    status,
                )

            except Exception as ex:

                logger.exception(
                    "Health check failed for %s",
                    name,
                )

                raise RuntimeError(
                    f"{name} initialization failed."
                ) from ex

        logger.info(
            "Health check completed successfully."
        )

        logger.info("")


###############################################################################
# MARKET DATA
###############################################################################

    def collect_market_data(
        self,
    ) -> pd.DataFrame:
        """
        Download today's market movers from Yahoo Finance.

        Returns
        -------
        pd.DataFrame
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "COLLECTING MARKET DATA"
        )

        logger.info(
            "=" * 80
        )

        #######################################################################
        # WORKFLOW
        #######################################################################

        tasks = [

            (
                "Fetching Top Gainers",
                self.market.fetch_top_gainers,
            ),

            (
                "Fetching Top Losers",
                self.market.fetch_top_losers,
            ),

        ]

        results = {}

        with tqdm(

            total=len(tasks),
            desc="Market Data",
            unit="task",
            colour="black",
            ncols=100,

        ) as progress:

            for title, function in tasks:

                logger.info(
                    "%s...",
                    title,
                )

                df = function()

                results[title] = df

                logger.info(
                    "%s completed (%d stocks).",
                    title,
                    len(df),
                )

                progress.update(1)

        #######################################################################
        # ASSIGN RESULTS
        #######################################################################

        gainers = results[
            "Fetching Top Gainers"
        ]

        losers = results[
            "Fetching Top Losers"
        ]

        #######################################################################
        # MERGE
        #######################################################################

        report_df = pd.concat(

            [
                gainers,
                losers,
            ],
            ignore_index=True,
        )

        logger.info(
            "Merged DataFrame columns: %s",
            report_df.columns.tolist(),
        )

        #######################################################################
        # NORMALIZE COLUMN NAMES
        #######################################################################

        report_df.rename(

            columns={
                "Stock": "Symbol",
                "ticker": "Symbol",
                "Ticker": "Symbol",
                "symbol": "Symbol",
                "SYMBOL": "Symbol",
            },
            inplace=True,
        )

        #######################################################################
        # VALIDATE
        #######################################################################

        if "Symbol" not in report_df.columns:

            raise RuntimeError(

                "Market data does not contain "
                "'Symbol' column.\n"
                f"Available columns: "
                f"{report_df.columns.tolist()}"

            )

        #######################################################################
        # REMOVE DUPLICATES
        #######################################################################

        report_df.drop_duplicates(
            subset=["Symbol"],
            inplace=True,
        )

        report_df.reset_index(
            drop=True,
            inplace=True,
        )

        #######################################################################
        # COMPLETE
        #######################################################################

        logger.info(

            "Total unique stocks collected : %d",

            len(report_df),

        )

        logger.info("")

        return report_df


###############################################################################
# OHLC ENRICHMENT
###############################################################################

    def enrich_ohlc(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge OHLC information.
        """

        logger.info(

            "=" * 80

        )

        logger.info(

            "ADDING OHLC DATA"

        )

        logger.info(

            "=" * 80

        )

        report_df = self.ohlc.merge(

            report_df,

        )

        logger.info(

            "OHLC merge completed."

        )

        logger.info("")

        return report_df

###############################################################################
# NEWS ENRICHMENT
###############################################################################

    def enrich_news(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Merge latest news.
        """

        logger.info(

            "=" * 80

        )

        logger.info(

            "ADDING NEWS"

        )

        logger.info(

            "=" * 80

        )

        report_df = self.news.merge(

            report_df,

        )

        logger.info(

            "News merge completed."

        )

        logger.info("")

        return report_df

###############################################################################
# AI SUMMARY
###############################################################################

    def generate_ai_summary(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate AI summaries.
        """

        logger.info(

            "=" * 80

        )

        logger.info(

            "GENERATING AI SUMMARIES"

        )

        logger.info(

            "=" * 80

        )

        report_df = self.ai_summary.merge(

            report_df,

        )

        logger.info(

            "AI summaries generated."

        )

        logger.info("")

        return report_df

###############################################################################
# AI REMARKS
###############################################################################

    def generate_ai_remarks(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate AI remarks.
        """

        logger.info(

            "=" * 80

        )

        logger.info(

            "GENERATING AI REMARKS"

        )

        logger.info(

            "=" * 80

        )

        report_df = self.ai_remarks.merge(

            report_df,

        )

        logger.info(

            "AI remarks generated."

        )

        logger.info("")

        return report_df

###############################################################################
# REPORT FORMATTING
###############################################################################

    def prepare_report(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare final report.
        """

        logger.info(

            "=" * 80
        )

        logger.info(
            "FORMATTING REPORT"
        )

        logger.info(
            "=" * 80
        )

        formatted_df = self.formatter.prepare_report(
            report_df,
        )

        if not isinstance(formatted_df, pd.DataFrame):

            raise TypeError(
                "formatter.prepare_report() returned "
                f"{type(formatted_df).__name__}, "
                "expected pandas DataFrame."
            )

        logger.info(
            "Report formatting completed | rows=%d | columns=%d",
            len(formatted_df),
            len(formatted_df.columns),
        )

        return formatted_df

        logger.info(

            "FORMATTING REPORT"

        )

        logger.info(

            "=" * 80

        )

        report_df = self.formatter.prepare_report(

            report_df,

        )

        logger.info(

            "Report formatting completed."

        )

        logger.info("")

        return report_df

###############################################################################
# EXCEL EXPORT
###############################################################################

    def export_excel(
        self,
        report_df: pd.DataFrame,
    ) -> Path:
        """
        Export persistent gainers/losers workbook.
        """

        logger.info(
            "=" * 80
        )

        logger.info(
            "EXPORTING EXCEL"
        )

        logger.info(
            "=" * 80
        )

        excel_file = (
            self.excel
            .export_gainers_losers_append(
                report_df,
            )
        )

        logger.info(
            "Excel exported : %s",
            excel_file,
        )

        logger.info(

            "=" * 80

        )

        logger.info(

            "EXPORTING EXCEL"

        )

        logger.info(

            "=" * 80

        )

        excel_file = self.excel.export(

            report_df,

        )

        logger.info(

            "Excel exported : %s",

            excel_file,

        )

        logger.info("")

        return excel_file

###############################################################################
# CSV EXPORT
###############################################################################

    def export_csv(
        self,
        report_df: pd.DataFrame,
    ) -> Path:
        """
        Export CSV report.
        """

        logger.info(

            "=" * 80

        )

        logger.info(

            "EXPORTING CSV"

        )

        logger.info(

            "=" * 80

        )

        csv_file = self.csv.export(

            report_df,

        )

        logger.info(

            "CSV exported : %s",

            csv_file,

        )

        logger.info("")

        return csv_file

###############################################################################
# EXPORT REPORTS
###############################################################################

    def export_reports(
        self,
        report_df: pd.DataFrame,
    ) -> None:
        """
        Export all reports.
        """

        if not isinstance(report_df, pd.DataFrame):
            raise TypeError(
                "export_reports() received "
                f"{type(report_df).__name__}, expected pandas DataFrame."
            )

        self.excel_file = self.export_excel(

            report_df,

        )

        self.csv_file = self.export_csv(

            report_df,

        )

###############################################################################
# STATISTICS
###############################################################################

    def print_statistics(
        self,
        report_df: pd.DataFrame,
    ) -> None:
        """
        Print application statistics.
        """

        logger.info("")

        logger.info(
            "=" * 80
        )

        logger.info(
            "REPORT STATISTICS"
        )

        logger.info(
            "=" * 80
        )

        logger.info(

            "Total Stocks      : %d",

            len(report_df),

        )

        logger.info(

            "AI Summary        : %s",

            self.ai_summary.statistics(

                report_df,

            ),

        )

        logger.info(

            "AI Remarks        : %s",

            self.ai_remarks.statistics(

                report_df,

            ),

        )

        logger.info(

            "Excel File        : %s",

            self.excel_file,

        )

        logger.info(

            "CSV File          : %s",

            self.csv_file,

        )

        logger.info("")

###############################################################################
# CLEANUP
###############################################################################

    def cleanup(
        self,
    ) -> None:
        """
        Cleanup resources.
        """

        logger.info("")

        logger.info(
            "=" * 80
        )

        logger.info(
            "CLEANUP"
        )

        logger.info(
            "=" * 80
        )

        services = [

            self.ai_summary,

            self.ai_remarks,

            self.excel,

            self.csv,

        ]

        for service in services:

            try:

                service.close()

            except Exception:

                logger.exception(

                    "Cleanup failed."

                )

        logger.info(

            "Cleanup completed."

        )

###############################################################################
# RUN APPLICATION
###############################################################################

    def run(
        self,
    ) -> None:
        """
        Execute complete workflow.
        """

        try:

            ###################################################################
            # HEALTH CHECK
            ###################################################################

            self.health_check()

            ###################################################################
            # COLLECT DATA
            ###################################################################

            report_df = self.collect_market_data()

            ###################################################################
            # OHLC
            ###################################################################

            report_df = self.enrich_ohlc(

                report_df,

            )

            ###################################################################
            # NEWS
            ###################################################################

            report_df = self.enrich_news(

                report_df,

            )

            ###################################################################
            # AI SUMMARY
            ###################################################################

            report_df = self.generate_ai_summary(

                report_df,

            )

            ###################################################################
            # AI REMARKS
            ###################################################################

            report_df = self.generate_ai_remarks(

                report_df,

            )

            ###################################################################
            # FORMAT
            ###################################################################

            report_df = self.prepare_report(
                report_df,
            )

            if not isinstance(report_df, pd.DataFrame):
                raise TypeError(
                    "prepare_report() returned "
                    f"{type(report_df).__name__}, expected pandas DataFrame."
                )

            self.report_df = report_df

            ###################################################################
            # EXPORT
            ###################################################################

            self.export_reports(

                report_df,

            )

            ###################################################################
            # STATISTICS
            ###################################################################

            self.print_statistics(

                report_df,

            )

            logger.info("")

            logger.info(
                "=" * 80
            )

            logger.info(
                "NSE MARKET REPORT COMPLETED SUCCESSFULLY"
            )

            logger.info(
                "=" * 80
            )

        except KeyboardInterrupt:

            logger.warning(

                "Execution interrupted by user."

            )

        except Exception:

            logger.exception(

                "Unexpected application error."

            )

            raise

        finally:

            self.cleanup()

###############################################################################
# MAIN
###############################################################################


def main() -> None:
    """
    Application entry point.
    """

    app = NSEMarketReport()

    app.run()

###############################################################################
# SCRIPT ENTRY
###############################################################################

if __name__ == "__main__":

    main()
