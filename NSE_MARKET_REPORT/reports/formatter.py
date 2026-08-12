"""
==============================================================================
File        : reports/formatter.py
Project     : NSE Market Report

Description
-----------
Report formatting engine.

Responsibilities
----------------
✓ Validate report schema
✓ Add missing columns
✓ Normalize values
✓ Format numbers
✓ Format timestamps
✓ Clean strings
✓ Prepare final DataFrame for export

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

import pandas as pd

from config.config import (
    REPORT_COLUMNS,
    DATETIME_FORMAT,
)

from config.logging_config import logger

###############################################################################
# DEFAULT VALUES
###############################################################################

DEFAULT_VALUES = {

    "Timestamp": "",

    "Category": "",

    "Symbol": "",

    "Company": "",

    "CMP": 0.0,

    "Open": 0.0,

    "High": 0.0,

    "Low": 0.0,

    "Previous Close": 0.0,

    "Close": 0.0,

    "Volume": 0,

    "1 Day Change %": 0.0,

    "Top Headline": "",

    "Recent News": "",

    "AI Summary": "",

    "Sentiment": "",

    "Strength Score": "",

    "Risk": "",

    "Final Remarks": "",

}

###############################################################################
# REPORT FORMATTER
###############################################################################


class ReportFormatter:
    """
    Formats report data for CSV and Excel exports.
    """

    ###########################################################################

    def __init__(self):

        logger.info(

            "[FORMATTER] Initializing formatter..."

        )

        self.timestamp = datetime.now()

        logger.info(

            "[FORMATTER] Formatter ready."

        )

    ###########################################################################

    @property
    def generated_at(self) -> str:
        """
        Report generation timestamp.
        """

        return self.timestamp.strftime(

            DATETIME_FORMAT,

        )

###############################################################################
# VALIDATION
###############################################################################

    @staticmethod
    def validate_dataframe(
        df: pd.DataFrame,
    ) -> None:
        """
        Validate dataframe type.
        """

        if not isinstance(

            df,

            pd.DataFrame,

        ):

            raise TypeError(

                "Expected pandas DataFrame."

            )

###############################################################################

    @staticmethod
    def ensure_columns(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add any missing report columns.
        """

        for column in REPORT_COLUMNS:

            if column not in df.columns:

                df[column] = DEFAULT_VALUES.get(

                    column,

                    "",

                )

        return df

###############################################################################

    @staticmethod
    def reorder_columns(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Arrange columns according to REPORT_COLUMNS.
        """

        return df[REPORT_COLUMNS]

###############################################################################

    @staticmethod
    def copy_dataframe(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Work on a copy to avoid mutating callers.
        """

        return df.copy(deep=True)
    

###############################################################################
# TIMESTAMP
###############################################################################

    def add_timestamp(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add report generation timestamp.
        """

        df["Timestamp"] = self.generated_at

        return df

###############################################################################
# PRICE FORMATTING
###############################################################################

    @staticmethod
    def format_prices(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Format price columns.
        """

        price_columns = [

            "CMP",

            "Open",

            "High",

            "Low",

            "Previous Close",

            "Close",

        ]

        for column in price_columns:

            if column not in df.columns:

                continue

            df[column] = (

                pd.to_numeric(

                    df[column],

                    errors="coerce",

                )

                .fillna(0)

                .round(2)

            )

        return df

###############################################################################
# PERCENTAGES
###############################################################################

    @staticmethod
    def format_percentages(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Format percentage columns.
        """

        if "1 Day Change %" in df.columns:

            df["1 Day Change %"] = (

                pd.to_numeric(

                    df["1 Day Change %"],

                    errors="coerce",

                )

                .fillna(0)

                .round(2)

            )

        return df

###############################################################################
# VOLUME
###############################################################################

    @staticmethod
    def format_volume(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Format traded volume.
        """

        if "Volume" not in df.columns:

            return df

        df["Volume"] = (

            pd.to_numeric(

                df["Volume"],

                errors="coerce",

            )

            .fillna(0)

            .astype("int64")

        )

        return df

###############################################################################
# STRENGTH SCORE
###############################################################################

    @staticmethod
    def format_strength_score(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Normalize AI strength score.
        """

        if "Strength Score" not in df.columns:

            return df

        df["Strength Score"] = (

            pd.to_numeric(

                df["Strength Score"],

                errors="coerce",

            )

            .fillna(0)

            .clip(

                lower=0,

                upper=100,

            )

            .astype(int)

        )

        return df

###############################################################################
# TEXT CLEANUP
###############################################################################

    @staticmethod
    def clean_text(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Clean text columns.
        """

        text_columns = [

            "Category",

            "Symbol",

            "Company",

            "Top Headline",

            "Recent News",

            "AI Summary",

            "Sentiment",

            "Risk",

            "Final Remarks",

        ]

        for column in text_columns:

            if column not in df.columns:

                continue

            df[column] = (

                df[column]

                .fillna("")

                .astype(str)

                .str.replace(

                    r"\s+",

                    " ",

                    regex=True,

                )

                .str.strip()

            )

        return df

###############################################################################
# MISSING VALUES
###############################################################################

    @staticmethod
    def fill_missing_values(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Fill missing values using defaults.
        """

        for column, value in DEFAULT_VALUES.items():

            if column in df.columns:

                df[column] = df[column].fillna(value)

        return df


###############################################################################
# SORT REPORT
###############################################################################

    @staticmethod
    def sort_report(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Sort report by category and percentage change.

        Gainers:
            Highest % change first

        Losers:
            Lowest % change first
        """

        if (
            "Category" not in df.columns
            or "1 Day Change %" not in df.columns
        ):
            return df

        gainers = df[
            df["Category"].str.lower() == "gainer"
        ].sort_values(
            by="1 Day Change %",
            ascending=False,
        )

        losers = df[
            df["Category"].str.lower() == "loser"
        ].sort_values(
            by="1 Day Change %",
            ascending=True,
        )

        return pd.concat(

            [

                gainers,

                losers,

            ],

            ignore_index=True,

        )

###############################################################################
# PREPARE REPORT
###############################################################################

    def prepare_report(
        self,
        report_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare final dataframe for export.

        Steps
        -----
        1. Validate
        2. Copy
        3. Ensure columns
        4. Fill missing values
        5. Add timestamp
        6. Format prices
        7. Format percentages
        8. Format volume
        9. Format AI strength score
        10. Clean text
        11. Sort rows
        12. Reorder columns
        """

        logger.info(

            "[FORMATTER] Preparing report..."

        )

        self.validate_dataframe(

            report_df,

        )

        df = self.copy_dataframe(

            report_df,

        )

        df = self.ensure_columns(

            df,

        )

        df = self.fill_missing_values(

            df,

        )

        df = self.add_timestamp(

            df,

        )

        df = self.format_prices(

            df,

        )

        df = self.format_percentages(

            df,

        )

        df = self.format_volume(

            df,

        )

        df = self.format_strength_score(

            df,

        )

        df = self.clean_text(

            df,

        )

        df = self.sort_report(

            df,

        )

        df = self.reorder_columns(

            df,

        )

        logger.info(

            "[FORMATTER] Report ready."

        )

        return df

###############################################################################
# REPORT PREVIEW
###############################################################################

    @staticmethod
    def preview(
        df: pd.DataFrame,
        rows: int = 5,
    ) -> pd.DataFrame:
        """
        Return first few rows of report.
        """

        return df.head(rows)

###############################################################################
# ROW COUNT
###############################################################################

    @staticmethod
    def row_count(
        df: pd.DataFrame,
    ) -> int:
        """
        Return total number of rows.
        """

        return len(df)

###############################################################################
# REPORT STATISTICS
###############################################################################

    def statistics(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Return report statistics.
        """

        self.validate_dataframe(df)

        stats = {

            "generated_at": self.generated_at,

            "total_records": len(df),

            "total_columns": len(df.columns),

            "gainers": 0,

            "losers": 0,

        }

        if "Category" in df.columns:

            stats["gainers"] = (

                df["Category"]

                .astype(str)

                .str.lower()

                .eq("gainer")

                .sum()

            )

            stats["losers"] = (

                df["Category"]

                .astype(str)

                .str.lower()

                .eq("loser")

                .sum()

            )

        return stats

###############################################################################
# VALIDATION REPORT
###############################################################################

    def validate_report(
        self,
        df: pd.DataFrame,
    ) -> List[str]:
        """
        Validate final report.

        Returns
        -------
        List[str]
            List of validation messages.
            Empty list means report is valid.
        """

        issues = []

        self.validate_dataframe(df)

        missing_columns = [

            column

            for column in REPORT_COLUMNS

            if column not in df.columns

        ]

        if missing_columns:

            issues.append(

                f"Missing columns: {missing_columns}"

            )

        if df.empty:

            issues.append(

                "Report dataframe is empty."

            )

        duplicate_symbols = []

        if "Symbol" in df.columns:

            duplicate_symbols = (

                df[df["Symbol"].duplicated()]

                ["Symbol"]

                .tolist()

            )

        if duplicate_symbols:

            issues.append(

                f"Duplicate symbols found: {duplicate_symbols}"

            )

        return issues

###############################################################################
# HEALTH CHECK
###############################################################################

    def health_check(self) -> Dict[str, Any]:
        """
        Formatter status.
        """

        return {

            "component": "ReportFormatter",

            "status": "ready",

            "generated_at": self.generated_at,

            "supported_columns": len(REPORT_COLUMNS),

        }

###############################################################################
# RESET
###############################################################################

    def reset(self) -> None:
        """
        Reset formatter timestamp.
        """

        self.timestamp = datetime.now()

        logger.info(

            "[FORMATTER] Reset completed."

        )