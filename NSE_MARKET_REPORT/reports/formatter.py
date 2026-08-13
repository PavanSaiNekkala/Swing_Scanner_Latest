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

<<<<<<< HEAD
from config.timezone import format_ist

=======
>>>>>>> 263a17d ("13/08/2026")
###############################################################################
# DEFAULT VALUES
###############################################################################

DEFAULT_VALUES = {

    "Timestamp": "",
<<<<<<< HEAD
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
=======

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

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
            DATETIME_FORMAT,
=======

            DATETIME_FORMAT,

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
            df,
            pd.DataFrame,
        ):

            raise TypeError(
                "Expected pandas DataFrame."
=======

            df,

            pd.DataFrame,

        ):

            raise TypeError(

                "Expected pandas DataFrame."

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
                df[column] = DEFAULT_VALUES.get(
                    column,
                    "",
=======

                df[column] = DEFAULT_VALUES.get(

                    column,

                    "",

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
        Add current IST timestamp to every report row.
        """

        if df.empty:
            return df

        timestamp = format_ist()

        df["Timestamp"] = timestamp
=======
        Add report generation timestamp.
        """

        df["Timestamp"] = self.generated_at
>>>>>>> 263a17d ("13/08/2026")

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
<<<<<<< HEAD
            "CMP",
            "Open",
            "High",
            "Low",
            "Previous Close",
            "Close",
=======

            "CMP",

            "Open",

            "High",

            "Low",

            "Previous Close",

            "Close",

>>>>>>> 263a17d ("13/08/2026")
        ]

        for column in price_columns:

            if column not in df.columns:

                continue

            df[column] = (

                pd.to_numeric(

                    df[column],
<<<<<<< HEAD
                    errors="coerce",

                )
                .fillna(0)
                .round(2)
=======

                    errors="coerce",

                )

                .fillna(0)

                .round(2)

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
                    errors="coerce",

                )
                .fillna(0)
                .round(2)
=======

                    errors="coerce",

                )

                .fillna(0)

                .round(2)

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
=======

>>>>>>> 263a17d ("13/08/2026")
                errors="coerce",

            )

            .fillna(0)
<<<<<<< HEAD
            .astype("int64")
=======

            .astype("int64")

>>>>>>> 263a17d ("13/08/2026")
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
<<<<<<< HEAD
                errors="coerce",
=======

                errors="coerce",

>>>>>>> 263a17d ("13/08/2026")
            )

            .fillna(0)

            .clip(

                lower=0,
<<<<<<< HEAD
                upper=100,

            )
            .astype(int)
=======

                upper=100,

            )

            .astype(int)

>>>>>>> 263a17d ("13/08/2026")
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

<<<<<<< HEAD
    def sort_report(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Sort the final report without filtering out valid rows.
        """

        if df.empty:
            return df

        sort_columns = []
        ascending = []

        if "Category" in df.columns:
            category_order = {
                "Gainer": 0,
                "Loser": 1,
            }

            df["_CategoryOrder"] = (
                df["Category"]
                .astype(str)
                .map(category_order)
                .fillna(99)
            )

            sort_columns.append("_CategoryOrder")
            ascending.append(True)

        if "Change %" in df.columns:
            df["_ChangeSort"] = pd.to_numeric(
                df["Change %"],
                errors="coerce",
            ).fillna(0)

            sort_columns.append("_ChangeSort")
            ascending.append(False)

        elif "1 Day Change %" in df.columns:
            df["_ChangeSort"] = pd.to_numeric(
                df["1 Day Change %"],
                errors="coerce",
            ).fillna(0)

            sort_columns.append("_ChangeSort")
            ascending.append(False)

        if "Symbol" in df.columns:
            sort_columns.append("Symbol")
            ascending.append(True)

        if sort_columns:
            df = df.sort_values(
                by=sort_columns,
                ascending=ascending,
                kind="stable",
            )

        df.drop(
            columns=[
                "_CategoryOrder",
                "_ChangeSort",
            ],
            errors="ignore",
            inplace=True,
        )

        df.reset_index(
            drop=True,
            inplace=True,
        )

        return df
=======
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
>>>>>>> 263a17d ("13/08/2026")

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
<<<<<<< HEAD
            "[FORMATTER] Preparing report..."
        )

        self.validate_dataframe(
            report_df,
        )

        df = self.copy_dataframe(
            report_df,
        )

        logger.info(
            "[FORMATTER] After copy: %d rows",
            len(df),
        )

        df = self.ensure_columns(
            df,
        )

        logger.info(
            "[FORMATTER] After ensure_columns: %d rows",
            len(df),
        )

        df = self.fill_missing_values(
            df,
        )

        logger.info(
            "[FORMATTER] After fill_missing_values: %d rows",
            len(df),
        )

        df = self.add_timestamp(
            df,
        )

        logger.info(
            "[FORMATTER] After add_timestamp: %d rows",
            len(df),
        )

        df = self.format_prices(
            df,
        )

        logger.info(
            "[FORMATTER] After format_prices: %d rows",
            len(df),
        )

        df = self.format_percentages(
            df,
        )

        logger.info(
            "[FORMATTER] After format_percentages: %d rows",
            len(df),
        )

        df = self.format_volume(
            df,
        )

        logger.info(
            "[FORMATTER] After format_volume: %d rows",
            len(df),
        )

        df = self.format_strength_score(
            df,
        )

        logger.info(
            "[FORMATTER] After format_strength_score: %d rows",
            len(df),
        )

        df = self.clean_text(
            df,
        )

        logger.info(
            "[FORMATTER] After clean_text: %d rows",
            len(df),
        )

        df = self.sort_report(
            df,
        )

        logger.info(
            "[FORMATTER] After sort_report: %d rows",
            len(df),
        )

        df = self.reorder_columns(
            df,
        )

        logger.info(
            "[FORMATTER] After reorder_columns: %d rows",
            len(df),
        )

        logger.info(
            "[FORMATTER] Report ready."
=======

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

>>>>>>> 263a17d ("13/08/2026")
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