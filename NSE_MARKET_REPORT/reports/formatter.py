"""
reports/formatter.py

Report formatting engine for NSE Market Report.

Responsibilities
----------------
- Validate report schema.
- Add missing columns.
- Normalize values.
- Format numbers.
- Format timestamps in IST.
- Clean strings.
- Sort report rows.
- Prepare final DataFrame for export.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

import pandas as pd

from config.config import (
    DATETIME_FORMAT,
    REPORT_COLUMNS,
)

from config.logging_config import logger

from config.timezone import (
    format_ist,
    now_ist,
)


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
    # INITIALIZATION
    ###########################################################################

    def __init__(
        self,
    ) -> None:

        logger.info(
            "[FORMATTER] Initializing formatter..."
        )

        self.timestamp = now_ist()

        logger.info(
            "[FORMATTER] Formatter ready."
        )

    ###########################################################################
    # GENERATED TIMESTAMP
    ###########################################################################

    @property
    def generated_at(
        self,
    ) -> str:
        """
        Return formatter generation timestamp in IST.
        """

        return self.timestamp.strftime(
            DATETIME_FORMAT
        )

    ###########################################################################
    # VALIDATION
    ###########################################################################

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

    ###########################################################################
    # ENSURE COLUMNS
    ###########################################################################

    @staticmethod
    def ensure_columns(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add missing report columns.
        """

        for column in REPORT_COLUMNS:

            if column not in df.columns:

                df[column] = (
                    DEFAULT_VALUES.get(
                        column,
                        "",
                    )
                )

        return df

    ###########################################################################
    # REORDER COLUMNS
    ###########################################################################

    @staticmethod
    def reorder_columns(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Arrange columns according to REPORT_COLUMNS.
        """

        return df[
            REPORT_COLUMNS
        ]

    ###########################################################################
    # COPY
    ###########################################################################

    @staticmethod
    def copy_dataframe(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Work on a deep copy.
        """

        return df.copy(
            deep=True
        )


###############################################################################
# TIMESTAMP
###############################################################################

    def add_timestamp(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Add current IST timestamp to every report row.
        """

        if df.empty:

            return df

        timestamp = format_ist()

        df[
            "Timestamp"
        ] = timestamp

        return df


###############################################################################
# PRICE FORMATTING
###############################################################################

    @staticmethod
    def format_prices(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Format price columns to two decimals.
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

        if "1 Day Change %" not in (
            df.columns
        ):

            return df

        df[
            "1 Day Change %"
        ] = (
            pd.to_numeric(
                df[
                    "1 Day Change %"
                ],
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
        Format traded volume as integer.
        """

        if "Volume" not in (
            df.columns
        ):

            return df

        df[
            "Volume"
        ] = (
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
        Normalize AI strength score to 0-100.
        """

        if (
            "Strength Score"
            not in df.columns
        ):

            return df

        df[
            "Strength Score"
        ] = (
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
        Normalize textual report fields.
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
        Fill missing values using configured defaults.
        """

        for column, value in (
            DEFAULT_VALUES.items()
        ):

            if column in df.columns:

                df[column] = (
                    df[column]
                    .fillna(value)
                )

        return df


###############################################################################
# SORT REPORT
###############################################################################

    def sort_report(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Sort the final report.

        Ordering
        --------
        1. Gainers before losers.
        2. Highest percentage change first.
        3. Symbol ascending.

        No valid rows are filtered out.
        """

        if df.empty:

            return df

        sort_columns: List[
            str
        ] = []

        ascending: List[
            bool
        ] = []

        #######################################################################
        # CATEGORY ORDER
        #######################################################################

        if "Category" in df.columns:

            category_order = {

                "Gainer": 0,

                "Loser": 1,

            }

            df[
                "_CategoryOrder"
            ] = (
                df[
                    "Category"
                ]
                .astype(str)
                .map(
                    category_order
                )
                .fillna(99)
            )

            sort_columns.append(
                "_CategoryOrder"
            )

            ascending.append(
                True
            )

        #######################################################################
        # CHANGE ORDER
        #######################################################################

        if "1 Day Change %" in (
            df.columns
        ):

            df[
                "_ChangeSort"
            ] = pd.to_numeric(
                df[
                    "1 Day Change %"
                ],
                errors="coerce",
            ).fillna(0)

            sort_columns.append(
                "_ChangeSort"
            )

            ascending.append(
                False
            )

        #######################################################################
        # SYMBOL
        #######################################################################

        if "Symbol" in df.columns:

            sort_columns.append(
                "Symbol"
            )

            ascending.append(
                True
            )

        #######################################################################
        # APPLY SORT
        #######################################################################

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
        5. Add IST timestamp
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

        #######################################################################
        # VALIDATE
        #######################################################################

        self.validate_dataframe(
            report_df
        )

        #######################################################################
        # COPY
        #######################################################################

        df = self.copy_dataframe(
            report_df
        )

        logger.info(
            "[FORMATTER] After copy: %d rows",
            len(df),
        )

        #######################################################################
        # ENSURE COLUMNS
        #######################################################################

        df = self.ensure_columns(
            df
        )

        logger.info(
            "[FORMATTER] After ensure_columns: %d rows",
            len(df),
        )

        #######################################################################
        # FILL MISSING
        #######################################################################

        df = self.fill_missing_values(
            df
        )

        logger.info(
            "[FORMATTER] After fill_missing_values: %d rows",
            len(df),
        )

        #######################################################################
        # TIMESTAMP
        #######################################################################

        df = self.add_timestamp(
            df
        )

        logger.info(
            "[FORMATTER] After add_timestamp: %d rows",
            len(df),
        )

        #######################################################################
        # PRICE
        #######################################################################

        df = self.format_prices(
            df
        )

        logger.info(
            "[FORMATTER] After format_prices: %d rows",
            len(df),
        )

        #######################################################################
        # PERCENTAGE
        #######################################################################

        df = self.format_percentages(
            df
        )

        logger.info(
            "[FORMATTER] After format_percentages: %d rows",
            len(df),
        )

        #######################################################################
        # VOLUME
        #######################################################################

        df = self.format_volume(
            df
        )

        logger.info(
            "[FORMATTER] After format_volume: %d rows",
            len(df),
        )

        #######################################################################
        # STRENGTH SCORE
        #######################################################################

        df = (
            self.format_strength_score(
                df
            )
        )

        logger.info(
            "[FORMATTER] After format_strength_score: %d rows",
            len(df),
        )

        #######################################################################
        # TEXT
        #######################################################################

        df = self.clean_text(
            df
        )

        logger.info(
            "[FORMATTER] After clean_text: %d rows",
            len(df),
        )

        #######################################################################
        # SORT
        #######################################################################

        df = self.sort_report(
            df
        )

        logger.info(
            "[FORMATTER] After sort_report: %d rows",
            len(df),
        )

        #######################################################################
        # COLUMN ORDER
        #######################################################################

        df = self.reorder_columns(
            df
        )

        logger.info(
            "[FORMATTER] After reorder_columns: %d rows",
            len(df),
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
        Return the first N rows.
        """

        return df.head(
            rows
        )


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

        self.validate_dataframe(
            df
        )

        stats = {

            "generated_at":
                self.generated_at,

            "total_records":
                len(df),

            "total_columns":
                len(df.columns),

            "gainers":
                0,

            "losers":
                0,

        }

        if "Category" in df.columns:

            category_series = (
                df["Category"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
            )

            stats["gainers"] = (
                category_series
                .eq("gainer")
                .sum()
            )

            stats["losers"] = (
                category_series
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
        list[str]
            Empty list means valid report.
        """

        issues: List[str] = []

        self.validate_dataframe(
            df
        )

        #######################################################################
        # REQUIRED COLUMNS
        #######################################################################

        missing_columns = [

            column

            for column in REPORT_COLUMNS

            if column not in df.columns

        ]

        if missing_columns:

            issues.append(
                "Missing columns: "
                f"{missing_columns}"
            )

        #######################################################################
        # EMPTY REPORT
        #######################################################################

        if df.empty:

            issues.append(
                "Report dataframe is empty."
            )

        #######################################################################
        # DUPLICATE SYMBOLS
        #######################################################################

        if "Symbol" in df.columns:

            duplicate_mask = (
                df["Symbol"]
                .duplicated(
                    keep=False
                )
            )

            duplicate_symbols = (
                df.loc[
                    duplicate_mask,
                    "Symbol",
                ]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            if duplicate_symbols:

                issues.append(
                    "Duplicate symbols found: "
                    f"{duplicate_symbols}"
                )

        return issues


###############################################################################
# HEALTH CHECK
###############################################################################

    def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Formatter status.
        """

        return {

            "component":
                "ReportFormatter",

            "status":
                "ready",

            "generated_at":
                self.generated_at,

            "supported_columns":
                len(REPORT_COLUMNS),

        }


###############################################################################
# RESET
###############################################################################

    def reset(
        self,
    ) -> None:
        """
        Reset formatter timestamp.
        """

        self.timestamp = now_ist()

        logger.info(
            "[FORMATTER] Reset completed."
        )
