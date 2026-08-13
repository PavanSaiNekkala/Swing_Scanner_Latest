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
<<<<<<< HEAD
import math
=======
>>>>>>> 263a17d ("13/08/2026")

from openpyxl import Workbook
from openpyxl import load_workbook

from openpyxl.styles import Font
from openpyxl.styles import PatternFill
from openpyxl.styles import Border
from openpyxl.styles import Side
from openpyxl.styles import Alignment

from openpyxl.utils import get_column_letter

<<<<<<< HEAD
from config.timezone import now_ist

from config.config import (
    OUTPUT_EXCEL,
    OUTPUT_EXCEL_DIR,
    HEADER_COLOR,
    GAINER_COLOR,
    LOSER_COLOR,
    REPORT_COLUMNS,
    DATETIME_FORMAT,
=======
from config.config import (

    OUTPUT_EXCEL,

    HEADER_COLOR,

    GAINER_COLOR,

    LOSER_COLOR,

    REPORT_COLUMNS,

    DATETIME_FORMAT,

>>>>>>> 263a17d ("13/08/2026")
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

<<<<<<< HEAD
        OUTPUT_EXCEL_DIR.mkdir(
=======
        OUTPUT_EXCEL.mkdir(
>>>>>>> 263a17d ("13/08/2026")

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

<<<<<<< HEAD
        return OUTPUT_EXCEL_DIR / name
=======
        return OUTPUT_EXCEL / name
>>>>>>> 263a17d ("13/08/2026")

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
    

<<<<<<< HEAD

    def export_gainers_losers_append(
        self,
        df: pd.DataFrame,
    ) -> Path:
        """
        Append current run's gainers and losers to separate
        persistent Excel worksheets.

        Workbook:
            NSE_Market_Report.xlsx

        Sheets:
            Gainers
            Losers
        """

        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                "Expected pandas DataFrame."
            )

        if df.empty:
            raise ValueError(
                "Cannot append an empty market report."
            )

        required_columns = [
            "Timestamp",
            "Category",
            "Symbol",
            "Company",
            "CMP",
            "Open",
            "High",
            "Low",
            "Previous Close",
            "Close",
            "Volume",
            "1 Day Change %",
            "Top Headline",
            "Recent News",
            "Final Remarks",
        ]

        missing = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                "Missing required columns: "
                + ", ".join(missing)
            )

        workbook_path = Path(
            OUTPUT_EXCEL
        )

        workbook_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if workbook_path.exists():
            workbook = load_workbook(
                workbook_path
            )
        else:
            workbook = Workbook()

        gainers = df.loc[
            df["Category"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("gainer")
        ].copy()

        losers = df.loc[
            df["Category"]
            .astype(str)
            .str.strip()
            .str.lower()
            .eq("loser")
        ].copy()

        #######################################################################
        # OPEN OR CREATE WORKBOOK
        #######################################################################

        if workbook_path.exists():

            workbook = load_workbook(
                workbook_path
            )

        else:

            workbook = Workbook()

            default_sheet = workbook.active
            workbook.remove(default_sheet)


        def _normalize_duplicate_value(
            value: Any,
        ) -> str:
            """
            Normalize a value for duplicate comparison.
            """

            if value is None:
                return ""

            if isinstance(
                value,
                float,
            ):

                if math.isnan(value):
                    return ""

                return f"{value:.10f}"

            if isinstance(
                value,
                (list, tuple),
            ):

                return " | ".join(
                    str(item).strip()
                    for item in value
                )

            return str(value).strip()

        def _same_day_duplicate_signatures(
            worksheet,
        ) -> set[tuple]:
            """
            Build signatures for rows already stored in the
            worksheet for the current IST calendar date.

            Timestamp is intentionally excluded from the
            signature so repeated runs on the same day can be
            detected even though execution times differ.
            """

            signatures: set[tuple] = set()

            if worksheet.max_row < 2:
                return signatures

            headers = [
                cell.value
                for cell in worksheet[1]
            ]

            header_index = {
                str(header): index
                for index, header in enumerate(
                    headers
                )
                if header is not None
            }

            signature_columns = [
                column
                for column in required_columns
                if column != "Timestamp"
            ]

            timestamp_index = header_index.get(
                "Timestamp"
            )

            if timestamp_index is None:
                return signatures

            today_ist = now_ist().date()

            for row in worksheet.iter_rows(
                min_row=2,
                values_only=True,
            ):

                timestamp_value = row[
                    timestamp_index
                ]

                if timestamp_value is None:
                    continue

                try:

                    if isinstance(
                        timestamp_value,
                        datetime,
                    ):

                        row_date = (
                            timestamp_value
                            .date()
                        )

                    else:

                        timestamp_text = (
                            str(timestamp_value)
                            .strip()
                        )

                        row_date = datetime.strptime(
                            timestamp_text[:10],
                            "%Y-%m-%d",
                        ).date()

                except (
                    ValueError,
                    TypeError,
                ):

                    continue

                if row_date != today_ist:
                    continue

                signature = tuple(
                    _normalize_duplicate_value(
                        row[
                            header_index[column]
                        ]
                    )
                    for column in signature_columns
                    if column in header_index
                )

                signatures.add(
                    signature
                )

            return signatures

        
        #######################################################################
        # APPEND HELPER
        #######################################################################

        def append_sheet(
            sheet_name: str,
            data: pd.DataFrame,
        ) -> None:

            if sheet_name in workbook.sheetnames:

                worksheet = workbook[sheet_name]

            else:

                worksheet = workbook.create_sheet(
                    sheet_name
                )

            if worksheet.max_row == 1 and all(
                cell.value is None
                for cell in worksheet[1]
            ):
                worksheet.delete_rows(1)

            ###################################################################
            # HEADER
            ###################################################################

            if worksheet.max_row == 0:

                for column_index, column in enumerate(
                    required_columns,
                    start=1,
                ):
                    worksheet.cell(
                        row=1,
                        column=column_index,
                        value=column,
                    )

            elif worksheet.max_row == 1:

                existing_headers = [
                    cell.value
                    for cell in worksheet[1]
                ]

                if not any(existing_headers):

                    for column_index, column in enumerate(
                        required_columns,
                        start=1,
                    ):
                        worksheet.cell(
                            row=1,
                            column=column_index,
                            value=column,
                        )

            ###################################################################
            # REMOVE SAME-DAY DUPLICATES
            ###################################################################

            existing_signatures = (
                _same_day_duplicate_signatures(
                    worksheet
                )
            )

            signature_columns = [
                column
                for column in required_columns
                if column != "Timestamp"
            ]

            rows_to_append = []

            skipped_duplicates = 0

            for values in data[
                required_columns
            ].itertuples(
                index=False,
                name=None,
            ):

                row_mapping = dict(
                    zip(
                        required_columns,
                        values,
                    )
                )

                signature = tuple(
                    _normalize_duplicate_value(
                        row_mapping.get(
                            column
                        )
                    )
                    for column in signature_columns
                )

                if signature in existing_signatures:

                    skipped_duplicates += 1

                    continue

                existing_signatures.add(
                    signature
                )

                rows_to_append.append(
                    row_mapping
                )

            ###################################################################
            # APPEND UNIQUE DATA
            ###################################################################

            if not rows_to_append:

                logger.info(
                    "[EXCEL] %s | "
                    "No new rows to append. "
                    "Skipped duplicates=%d",
                    sheet_name,
                    skipped_duplicates,
                )

                return

            start_row = (
                worksheet.max_row + 1
            )

            for row_offset, row_mapping in enumerate(
                rows_to_append,
                start=0,
            ):

                excel_row = (
                    start_row
                    + row_offset
                )

                for column_index, column in enumerate(
                    required_columns,
                    start=1,
                ):

                    value = row_mapping.get(
                        column
                    )

                    if isinstance(
                        value,
                        (list, tuple),
                    ):

                        value = " | ".join(
                            map(
                                str,
                                value,
                            )
                        )

                    if pd.isna(value):
                        value = None

                    worksheet.cell(
                        row=excel_row,
                        column=column_index,
                        value=value,
                    )

            logger.info(
                "[EXCEL] %s | "
                "Appended=%d | "
                "Skipped duplicates=%d",
                sheet_name,
                len(rows_to_append),
                skipped_duplicates,
            )

            ###################################################################
            # HEADER FORMATTING
            ###################################################################

            for cell in worksheet[1]:

                cell.font = cell.font.copy(
                    bold=True
                )

            ###################################################################
            # FREEZE HEADER
            ###################################################################

            worksheet.freeze_panes = "A2"

            ###################################################################
            # AUTO FILTER
            ###################################################################

            worksheet.auto_filter.ref = (
                worksheet.dimensions
            )

            ###################################################################
            # COLUMN WIDTHS
            ###################################################################

            widths = {
                "Timestamp": 22,
                "Category": 12,
                "Symbol": 16,
                "Company": 32,
                "CMP": 14,
                "Open": 14,
                "High": 14,
                "Low": 14,
                "Previous Close": 18,
                "Close": 14,
                "Volume": 16,
                "1 Day Change %": 18,
                "Top Headline": 50,
                "Recent News": 80,
                "Final Remarks": 60,
            }

            for index, column in enumerate(
                required_columns,
                start=1,
            ):

                worksheet.column_dimensions[
                    get_column_letter(index)
                ].width = widths.get(
                    column,
                    18,
                )

        #######################################################################
        # APPEND BOTH SHEETS
        #######################################################################

        append_sheet(
            "Gainers",
            gainers,
        )

        append_sheet(
            "Losers",
            losers,
        )

        #######################################################################
        # SAVE
        #######################################################################

        workbook.save(
            workbook_path
        )

        logger.info(
            "[EXCEL] Appended %d gainers and %d losers | File=%s",
            len(gainers),
            len(losers),
            workbook_path,
        )

        return workbook_path



=======
>>>>>>> 263a17d ("13/08/2026")
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

<<<<<<< HEAD
                OUTPUT_EXCEL_DIR,
=======
                OUTPUT_EXCEL,
>>>>>>> 263a17d ("13/08/2026")

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

<<<<<<< HEAD
                OUTPUT_EXCEL_DIR,
=======
                OUTPUT_EXCEL,
>>>>>>> 263a17d ("13/08/2026")

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
