"""
==============================================================================
File        : reports/csv_export.py
Project     : NSE Market Report

Description
-----------
Professional CSV Exporter.

Responsibilities
----------------
✓ Export formatted DataFrame to CSV
✓ Validate report schema
✓ Create output directory
✓ Handle UTF-8 encoding
✓ Support configurable delimiters
✓ Generate timestamped filenames

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from config.config import (
    OUTPUT_CSV,
    REPORT_COLUMNS,
    DATETIME_FORMAT,
)

from config.logging_config import logger

###############################################################################
# CSV CONFIGURATION
###############################################################################

DEFAULT_ENCODING = "utf-8-sig"
DEFAULT_SEPARATOR = ","
DEFAULT_LINE_TERMINATOR = "\n"

###############################################################################
# CSV EXPORTER
###############################################################################


class CSVExporter:
    """
    CSV Export Service.

    Public API
    ----------
    export()
    statistics()
    health_check()
    reset()
    close()
    """

    ###########################################################################

    def __init__(self):

        logger.info(

            "[CSV] Initializing exporter..."

        )

        self.timestamp = datetime.now()

        OUTPUT_CSV.mkdir(

            parents=True,

            exist_ok=True,

        )

        logger.info(

            "[CSV] Exporter ready."

        )

    ###########################################################################

    @property
    def filename(self) -> Path:
        """
        Default CSV filename.
        """

        filename = self.timestamp.strftime(

            "%Y-%m-%d_NSE_Report.csv"

        )

        return OUTPUT_CSV / filename

###############################################################################
# VALIDATION
###############################################################################

    @staticmethod
    def validate_dataframe(
        df: pd.DataFrame,
    ) -> None:
        """
        Validate dataframe.
        """

        if not isinstance(df, pd.DataFrame):

            raise TypeError(

                "Expected pandas DataFrame."

            )

        if df.empty:

            raise ValueError(

                "Report dataframe is empty."

            )

###############################################################################

    @staticmethod
    def validate_columns(
        df: pd.DataFrame,
    ) -> None:
        """
        Ensure dataframe contains all report columns.
        """

        missing = [

            column

            for column in REPORT_COLUMNS

            if column not in df.columns

        ]

        if missing:

            raise ValueError(

                f"Missing columns: {missing}"

            )

###############################################################################

    @staticmethod
    def prepare_dataframe(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Create safe copy before exporting.
        """

        return df.copy(deep=True)

###############################################################################

    @property
    def generated_at(self) -> str:
        """
        Export timestamp.
        """

        return self.timestamp.strftime(

            DATETIME_FORMAT,

        )


###############################################################################
# DATA CLEANUP
###############################################################################

    @staticmethod
    def clean_dataframe(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Clean dataframe before CSV export.
        """

        df = df.copy()

        # Replace NaN with empty strings
        df = df.fillna("")

        # Convert lists/tuples to strings
        for column in df.columns:

            df[column] = df[column].apply(

                lambda value: (
                    " | ".join(map(str, value))
                    if isinstance(value, (list, tuple))
                    else value
                )

            )

        return df

###############################################################################
# NORMALIZE LINE BREAKS
###############################################################################

    @staticmethod
    def normalize_text(
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Remove unwanted line breaks and tabs.
        """

        object_columns = df.select_dtypes(

            include=["object"]

        ).columns

        for column in object_columns:

            df[column] = (

                df[column]

                .astype(str)

                .str.replace("\r\n", " ", regex=False)

                .str.replace("\n", " ", regex=False)

                .str.replace("\t", " ", regex=False)

                .str.strip()

            )

        return df

###############################################################################
# WRITE CSV
###############################################################################

    @staticmethod
    def write_csv(
        df: pd.DataFrame,
        output_path: Path,
        separator: str = DEFAULT_SEPARATOR,
        encoding: str = DEFAULT_ENCODING,
    ) -> None:
        """
        Write dataframe to CSV.
        """

        import csv

        df.to_csv(

            output_path,

            index=False,

            sep=separator,

            encoding=encoding,

            lineterminator=DEFAULT_LINE_TERMINATOR,

            quoting=csv.QUOTE_MINIMAL,

        )

###############################################################################
# SAFE SAVE
###############################################################################

    def save(
        self,
        df: pd.DataFrame,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Save dataframe safely using a temporary file.
        """

        import os
        import tempfile

        if output_path is None:

            output_path = self.filename

        temp_fd, temp_name = tempfile.mkstemp(

            suffix=".csv",

            dir=output_path.parent,

        )

        os.close(temp_fd)

        temp_path = Path(temp_name)

        try:

            self.write_csv(

                df,

                temp_path,

            )

            temp_path.replace(

                output_path,

            )

            logger.info(

                "[CSV] Saved: %s",

                output_path,

            )

            return output_path

        except Exception:

            if temp_path.exists():

                temp_path.unlink()

            raise

###############################################################################
# EXPORT PREPARATION
###############################################################################

    def prepare_for_export(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Prepare dataframe for CSV export.
        """

        self.validate_dataframe(

            df,

        )

        self.validate_columns(

            df,

        )

        df = self.prepare_dataframe(

            df,

        )

        df = self.clean_dataframe(

            df,

        )

        df = self.normalize_text(

            df,

        )

        return df


###############################################################################
# EXPORT
###############################################################################

    def export(
        self,
        df: pd.DataFrame,
        output_path: Optional[Path] = None,
    ) -> Path:
        """
        Export report dataframe to CSV.

        Parameters
        ----------
        df : pd.DataFrame
            Formatted report dataframe.

        output_path : Path, optional
            Custom output path.

        Returns
        -------
        Path
            Saved CSV file.
        """

        logger.info(

            "[CSV] Starting CSV export..."

        )

        df = self.prepare_for_export(

            df,

        )

        path = self.save(

            df,

            output_path,

        )

        logger.info(

            "[CSV] Export completed."

        )

        return path

###############################################################################
# FILE EXISTS
###############################################################################

    @staticmethod
    def file_exists(
        file_path: Path,
    ) -> bool:
        """
        Check whether exported file exists.
        """

        return file_path.exists()

###############################################################################
# FILE SIZE
###############################################################################

    @staticmethod
    def file_size(
        file_path: Path,
    ) -> int:
        """
        Return file size in bytes.
        """

        if not file_path.exists():

            return 0

        return file_path.stat().st_size

###############################################################################
# EXPORT SUMMARY
###############################################################################

    def export_summary(
        self,
        df: pd.DataFrame,
        output_path: Path,
    ) -> Dict[str, Any]:
        """
        Return export summary.
        """

        gainers = 0
        losers = 0

        if "Category" in df.columns:

            gainers = (

                df["Category"]

                .astype(str)

                .str.lower()

                .eq("gainer")

                .sum()

            )

            losers = (

                df["Category"]

                .astype(str)

                .str.lower()

                .eq("loser")

                .sum()

            )

        return {

            "file": str(output_path),

            "exists": self.file_exists(

                output_path,

            ),

            "size_bytes": self.file_size(

                output_path,

            ),

            "rows": len(df),

            "columns": len(df.columns),

            "gainers": gainers,

            "losers": losers,

            "generated_at": self.generated_at,

        }

###############################################################################
# LAST EXPORT INFO
###############################################################################

    def last_export_info(
        self,
        output_path: Path,
    ) -> Dict[str, Any]:
        """
        Information about an exported CSV.
        """

        return {

            "path": str(output_path),

            "exists": self.file_exists(

                output_path,

            ),

            "size_bytes": self.file_size(

                output_path,

            ),

            "timestamp": self.generated_at,

        }

###############################################################################
# VERIFY EXPORT
###############################################################################

    @staticmethod
    def verify_export(
        output_path: Path,
    ) -> bool:
        """
        Verify exported CSV is readable.
        """

        try:

            pd.read_csv(

                output_path,

            )

            return True

        except Exception:

            return False
        

###############################################################################
# STATISTICS
###############################################################################

    def statistics(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Return CSV export statistics.
        """

        self.validate_dataframe(df)

        gainers = 0
        losers = 0

        if "Category" in df.columns:

            gainers = (
                df["Category"]
                .astype(str)
                .str.lower()
                .eq("gainer")
                .sum()
            )

            losers = (
                df["Category"]
                .astype(str)
                .str.lower()
                .eq("loser")
                .sum()
            )

        return {

            "rows": len(df),

            "columns": len(df.columns),

            "gainers": gainers,

            "losers": losers,

            "generated_at": self.generated_at,

            "output_directory": str(

                OUTPUT_CSV,

            ),

        }

###############################################################################
# HEALTH CHECK
###############################################################################

    def health_check(self) -> Dict[str, Any]:
        """
        Return exporter health information.
        """

        return {

            "component": "CSVExporter",

            "status": "ready",

            "generated_at": self.generated_at,

            "output_directory": str(

                OUTPUT_CSV,

            ),

        }

###############################################################################
# RESET
###############################################################################

    def reset(self) -> None:
        """
        Reset exporter timestamp.
        """

        self.timestamp = datetime.now()

        logger.info(

            "[CSV] Exporter reset."

        )

###############################################################################
# CLOSE
###############################################################################

    def close(self) -> None:
        """
        Cleanup exporter resources.
        """

        logger.info(

            "[CSV] Exporter closed."

        )