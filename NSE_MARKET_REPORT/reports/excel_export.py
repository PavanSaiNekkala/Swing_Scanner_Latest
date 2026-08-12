"""
==============================================================================
File        : reports/excel_export.py
Project     : NSE Market Report

Description
-----------
Professional Excel Report Exporter.

Responsibilities
----------------
✓ Export report DataFrame to Excel
✓ Apply professional formatting
✓ Create worksheets
✓ Apply styles
✓ Auto-size columns
✓ Freeze panes
✓ Apply filters
✓ Save workbook

Author      : Your Name
==============================================================================
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict

import pandas as pd

from openpyxl import Workbook
from openpyxl import load_workbook

from openpyxl.styles import Font
from openpyxl.styles import PatternFill
from openpyxl.styles import Border
from openpyxl.styles import Side
from openpyxl.styles import Alignment

from openpyxl.utils import get_column_letter

from config.config import (

    OUTPUT_EXCEL,

    HEADER_COLOR,

    GAINER_COLOR,

    LOSER_COLOR,

    REPORT_COLUMNS,

    DATETIME_FORMAT,

)

from config.logging_config import logger

###############################################################################
# STYLES
###############################################################################

HEADER_FILL = PatternFill(

    fill_type="solid",

    fgColor=HEADER_COLOR,

)

HEADER_FONT = Font(

    bold=True,

    color="FFFFFF",

)

CENTER_ALIGNMENT = Alignment(

    horizontal="center",

    vertical="center",

)

LEFT_ALIGNMENT = Alignment(

    horizontal="left",

    vertical="top",

    wrap_text=True,

)

THIN_BORDER = Border(

    left=Side(style="thin"),

    right=Side(style="thin"),

    top=Side(style="thin"),

    bottom=Side(style="thin"),

)

###############################################################################
# EXPORTER
###############################################################################

class ExcelExporter:
    """
    Excel Export Service.
    """

    ###########################################################################

    def __init__(self):

        logger.info(

            "[EXCEL] Initializing exporter..."

        )

        self.timestamp = datetime.now()

        OUTPUT_EXCEL.mkdir(

            parents=True,

            exist_ok=True,

        )

        logger.info(

            "[EXCEL] Ready."

        )

    ###########################################################################

    @property
    def filename(self) -> Path:
        """
        Default output filename.
        """

        name = self.timestamp.strftime(

            "%Y-%m-%d_NSE_Report.xlsx"

        )

        return OUTPUT_EXCEL / name

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

        if not isinstance(

            df,

            pd.DataFrame,

        ):

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
        Ensure all report columns exist.
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
    def create_workbook() -> Workbook:
        """
        Create Excel workbook.
        """

        workbook = Workbook()

        return workbook


###############################################################################
# WORKSHEET
###############################################################################

    @staticmethod
    def create_worksheet(
        workbook: Workbook,
        title: str = "NSE Market Report",
    ):
        """
        Create or rename the active worksheet.
        """

        worksheet = workbook.active

        worksheet.title = title

        return worksheet

###############################################################################
# WRITE HEADER
###############################################################################

    @staticmethod
    def write_header(
        worksheet,
    ) -> None:
        """
        Write report header row.
        """

        for column_index, column_name in enumerate(

            REPORT_COLUMNS,

            start=1,

        ):

            cell = worksheet.cell(

                row=1,

                column=column_index,

                value=column_name,

            )

            cell.fill = HEADER_FILL

            cell.font = HEADER_FONT

            cell.alignment = CENTER_ALIGNMENT

            cell.border = THIN_BORDER

###############################################################################
# WRITE DATA
###############################################################################

    @staticmethod
    def write_data(
        worksheet,
        df: pd.DataFrame,
    ) -> None:
        """
        Write dataframe rows.
        """

        for row_index, row in enumerate(

            df.itertuples(index=False),

            start=2,

        ):

            for column_index, value in enumerate(

                row,

                start=1,

            ):

                cell = worksheet.cell(

                    row=row_index,

                    column=column_index,

                    value=value,

                )

                cell.border = THIN_BORDER

                cell.alignment = LEFT_ALIGNMENT

###############################################################################
# FREEZE PANES
###############################################################################

    @staticmethod
    def freeze_header(
        worksheet,
    ) -> None:
        """
        Freeze header row.
        """

        worksheet.freeze_panes = "A2"

###############################################################################
# AUTO FILTER
###############################################################################

    @staticmethod
    def apply_filter(
        worksheet,
    ) -> None:
        """
        Enable Excel filter.
        """

        worksheet.auto_filter.ref = worksheet.dimensions

###############################################################################
# AUTO WIDTH
###############################################################################

    @staticmethod
    def autofit_columns(
        worksheet,
    ) -> None:
        """
        Auto-size worksheet columns.
        """

        for column_cells in worksheet.columns:

            max_length = 0

            column_letter = get_column_letter(

                column_cells[0].column,

            )

            for cell in column_cells:

                try:

                    length = len(

                        str(cell.value)

                    )

                    if length > max_length:

                        max_length = length

                except Exception:

                    pass

            adjusted_width = min(

                max_length + 3,

                60,

            )

            worksheet.column_dimensions[

                column_letter

            ].width = adjusted_width

###############################################################################
# NUMBER FORMATS
###############################################################################

    @staticmethod
    def apply_number_formats(
        worksheet,
    ) -> None:
        """
        Apply Excel number formats.
        """

        headers = {

            cell.value: cell.column

            for cell in worksheet[1]

        }

        price_columns = [

            "CMP",

            "Open",

            "High",

            "Low",

            "Previous Close",

            "Close",

        ]

        for name in price_columns:

            if name not in headers:

                continue

            col = headers[name]

            for row in range(

                2,

                worksheet.max_row + 1,

            ):

                worksheet.cell(

                    row=row,

                    column=col,

                ).number_format = "#,##0.00"

        if "1 Day Change %" in headers:

            col = headers["1 Day Change %"]

            for row in range(

                2,

                worksheet.max_row + 1,

            ):

                worksheet.cell(

                    row=row,

                    column=col,

                ).number_format = "0.00"

        if "Volume" in headers:

            col = headers["Volume"]

            for row in range(

                2,

                worksheet.max_row + 1,

            ):

                worksheet.cell(

                    row=row,

                    column=col,

                ).number_format = "#,##0"


###############################################################################
# CONDITIONAL FORMATTING
###############################################################################

    @staticmethod
    def apply_conditional_formatting(
        worksheet,
    ) -> None:
        """
        Color entire row based on Category.
        """

        headers = {

            cell.value: cell.column

            for cell in worksheet[1]

        }

        if "Category" not in headers:

            return

        category_column = headers["Category"]

        gainer_fill = PatternFill(

            fill_type="solid",

            fgColor=GAINER_COLOR,

        )

        loser_fill = PatternFill(

            fill_type="solid",

            fgColor=LOSER_COLOR,

        )

        for row in range(2, worksheet.max_row + 1):

            category = worksheet.cell(

                row=row,

                column=category_column,

            ).value

            if category is None:

                continue

            category = str(category).strip().lower()

            if category == "gainer":

                fill = gainer_fill

            elif category == "loser":

                fill = loser_fill

            else:

                continue

            for col in range(1, worksheet.max_column + 1):

                worksheet.cell(

                    row=row,

                    column=col,

                ).fill = fill

###############################################################################
# SUMMARY SHEET
###############################################################################

    def create_summary_sheet(
        self,
        workbook: Workbook,
        df: pd.DataFrame,
    ):
        """
        Create report summary worksheet.
        """

        ws = workbook.create_sheet(

            title="Summary",

        )

        total = len(df)

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

        rows = [

            ("Report Name", "NSE Market Report"),

            ("Generated At", self.timestamp.strftime(DATETIME_FORMAT)),

            ("Total Stocks", total),

            ("Top Gainers", gainers),

            ("Top Losers", losers),

        ]

        for r, (label, value) in enumerate(rows, start=1):

            c1 = ws.cell(row=r, column=1, value=label)
            c2 = ws.cell(row=r, column=2, value=value)

            c1.font = HEADER_FONT
            c1.fill = HEADER_FILL
            c1.border = THIN_BORDER

            c2.border = THIN_BORDER

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 35

        return ws

###############################################################################
# DOCUMENT PROPERTIES
###############################################################################

    def apply_document_properties(
        self,
        workbook: Workbook,
    ) -> None:
        """
        Set workbook metadata.
        """

        workbook.properties.creator = "NSE Market Report"

        workbook.properties.title = "NSE Daily Market Report"

        workbook.properties.subject = "Top 20 Gainers & Losers"

        workbook.properties.description = (

            "Automatically generated NSE Market Report"

        )

###############################################################################
# SAVE WORKBOOK
###############################################################################

    def save(
        self,
        workbook: Workbook,
        output_path: Path | None = None,
    ) -> Path:
        """
        Save workbook to disk.
        """

        if output_path is None:

            output_path = self.filename

        workbook.save(output_path)

        logger.info(

            "[EXCEL] Saved: %s",

            output_path,

        )

        return output_path
    

###############################################################################
# EXPORT REPORT
###############################################################################

    def export(
        self,
        df: pd.DataFrame,
        output_path: Path | None = None,
    ) -> Path:
        """
        Export DataFrame to formatted Excel workbook.

        Parameters
        ----------
        df : pd.DataFrame
            Formatted report dataframe.

        output_path : Path, optional
            Output Excel path.

        Returns
        -------
        Path
            Saved Excel file.
        """

        logger.info(

            "[EXCEL] Starting Excel export..."

        )

        self.validate_dataframe(df)

        self.validate_columns(df)

        workbook = self.create_workbook()

        worksheet = self.create_worksheet(

            workbook,

        )

        self.write_header(

            worksheet,

        )

        self.write_data(

            worksheet,

            df,

        )

        self.freeze_header(

            worksheet,

        )

        self.apply_filter(

            worksheet,

        )

        self.apply_number_formats(

            worksheet,

        )

        self.autofit_columns(

            worksheet,

        )

        self.apply_conditional_formatting(

            worksheet,

        )

        self.create_summary_sheet(

            workbook,

            df,

        )

        self.apply_document_properties(

            workbook,

        )

        path = self.save(

            workbook,

            output_path,

        )

        logger.info(

            "[EXCEL] Export completed."

        )

        return path

###############################################################################
# EXPORT STATISTICS
###############################################################################

    def statistics(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Return export statistics.
        """

        return {

            "rows": len(df),

            "columns": len(df.columns),

            "generated_at": self.timestamp.strftime(

                DATETIME_FORMAT,

            ),

            "output_directory": str(

                OUTPUT_EXCEL,

            ),

        }

###############################################################################
# HEALTH CHECK
###############################################################################

    def health_check(self) -> Dict[str, Any]:
        """
        Exporter status.
        """

        return {

            "component": "ExcelExporter",

            "status": "ready",

            "timestamp": self.timestamp.strftime(

                DATETIME_FORMAT,

            ),

            "output_directory": str(

                OUTPUT_EXCEL,

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

            "[EXCEL] Exporter reset."

        )

###############################################################################
# CLOSE
###############################################################################

    def close(self) -> None:
        """
        Cleanup resources.
        """

        logger.info(

            "[EXCEL] Exporter closed.")
