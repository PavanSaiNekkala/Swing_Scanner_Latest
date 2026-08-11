from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .exceptions import NoSourceDataError
from .schemas import REQUIRED_COLUMNS


@dataclass(frozen=True, slots=True)
class LoadedSheet:
    dataframe: pd.DataFrame
    workbook: Path
    sheet_name: str


class HistoryLoader:
    """
    Reads Latest Scan sheets from history workbooks.
    """

    def __init__(
        self,
        history_directory: Path,
    ) -> None:

        self.history_directory = (
            history_directory
        )

    @staticmethod
    def normalize_sheet_name(
        name: str,
    ) -> str:

        return (
            str(name)
            .strip()
            .lower()
            .replace("_", "")
            .replace("-", "")
            .replace(" ", "")
        )

    def discover_workbooks(
        self,
    ) -> list[Path]:

        if not self.history_directory.exists():
            raise NoSourceDataError(
                f"History directory does not exist: "
                f"{self.history_directory}"
            )

        return sorted(
            self.history_directory.glob(
                "*.xlsx"
            )
        )

    def find_latest_scan_sheets(
        self,
        workbook: Path,
    ) -> list[str]:

        excel = pd.ExcelFile(
            workbook
        )

        return [
            sheet
            for sheet in excel.sheet_names
            if self.normalize_sheet_name(
                sheet
            )
            == "latestscan"
        ]

    def load(
        self,
    ) -> list[LoadedSheet]:

        loaded: list[LoadedSheet] = []

        for workbook in self.discover_workbooks():

            sheets = (
                self.find_latest_scan_sheets(
                    workbook
                )
            )

            for sheet in sheets:

                dataframe = pd.read_excel(
                    workbook,
                    sheet_name=sheet,
                )

                missing = [
                    column
                    for column in REQUIRED_COLUMNS
                    if column not in dataframe.columns
                ]

                if missing:
                    continue

                dataframe = dataframe[
                    list(REQUIRED_COLUMNS)
                ].copy()

                dataframe[
                    "Source Workbook"
                ] = workbook.name

                dataframe[
                    "Source Sheet"
                ] = sheet

                dataframe[
                    "Source Modified"
                ] = pd.Timestamp(
                    workbook.stat().st_mtime,
                    unit="s",
                )

                loaded.append(
                    LoadedSheet(
                        dataframe=dataframe,
                        workbook=workbook,
                        sheet_name=sheet,
                    )
                )

        if not loaded:
            raise NoSourceDataError(
                "No valid Latest Scan sheets found."
            )

        return loaded