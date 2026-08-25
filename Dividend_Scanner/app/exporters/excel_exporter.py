"""
Excel Exporter

Exports scan results to Excel.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from app.exporters.excel_styles import ExcelStyles
from app.exporters.report_builder import ReportBuilder


class ExcelExporter:

    def export(

        self,

        results,

        output_file: str | Path,

        sheet_name: str = "Dividend Scanner",

    ) -> Path:

        rows = ReportBuilder.build_rows(
            results
        )

        workbook = Workbook()

        worksheet = workbook.active

        worksheet.title = sheet_name

        if rows:

            headers = ReportBuilder.column_order(
                rows
            )

            worksheet.append(
                headers
            )

            for cell in worksheet[1]:

                cell.fill = (
                    ExcelStyles.HEADER_FILL
                )

                cell.font = (
                    ExcelStyles.HEADER_FONT
                )

                cell.border = (
                    ExcelStyles.BORDER
                )

                cell.alignment = (
                    ExcelStyles.CENTER
                )

            for row in rows:

                worksheet.append(

                    [

                        row.get(
                            column
                        )

                        for column

                        in headers

                    ]

                )

            for sheet_row in worksheet.iter_rows(

                min_row=2,

            ):

                for cell in sheet_row:

                    cell.border = (
                        ExcelStyles.BORDER
                    )

        output = Path(
            output_file
        )

        output.parent.mkdir(

            parents=True,

            exist_ok=True,

        )

        workbook.save(
            output
        )

        return output