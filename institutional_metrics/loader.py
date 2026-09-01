from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .exceptions import (
    NoSourceDataError,
)

from .schemas import (
    RAW_SCANNER_COLUMNS,
)



@dataclass(
    frozen=True,
    slots=True,
)
class LoadedSheet:
    """
    Loaded scanner sheet with lineage metadata.
    """

    dataframe: pd.DataFrame
    workbook: Path
    sheet_name: str




class HistoryLoader:
    """
    Loads Latest Scan sheets from scanner history workbooks.

    Responsibilities:

    - Discover Excel history files
    - Locate Latest Scan sheets
    - Validate required columns
    - Attach source metadata

    Does NOT:

    - deduplicate stocks
    - calculate metrics
    - score securities
    - rank securities
    """



    def __init__(
        self,
        history_directory: Path,
    ) -> None:

        self.history_directory = (
            history_directory
        )



    # =========================================================
    # Sheet normalization
    # =========================================================

    @staticmethod
    def normalize_sheet_name(
        name: str,
    ) -> str:

        return (

            str(name)

            .strip()

            .lower()

            .replace(
                "_",
                "",
            )

            .replace(
                "-",
                "",
            )

            .replace(
                " ",
                "",
            )

        )



    # =========================================================
    # Workbook discovery
    # =========================================================

    def discover_workbooks(
        self,
    ) -> list[Path]:

        if not self.history_directory.exists():

            raise NoSourceDataError(
                f"History directory does not exist: "
                f"{self.history_directory}"
            )


        workbooks = sorted(

            self.history_directory.glob(

                "swing_scanner_allnse_history_*.xlsx"

            ),

            key=lambda path: path.stat().st_mtime,

            reverse=True,

        )


        if not workbooks:

            raise NoSourceDataError(

                "No AllNSE history workbook found."

            )


        return [

            workbooks[0]

        ]



    # =========================================================
    # Latest Scan discovery
    # =========================================================

    def find_latest_scan_sheets(
        self,
        workbook: Path,
    ) -> list[str]:


        with pd.ExcelFile(
            workbook
        ) as excel:


            return [

                sheet

                for sheet in excel.sheet_names

                if self.normalize_sheet_name(
                    sheet
                )
                ==
                "latestscan"

            ]



    # =========================================================
    # Schema validation
    # =========================================================

    @staticmethod
    def validate_columns(
        dataframe: pd.DataFrame,
    ) -> bool:


        return all(

            column in dataframe.columns

            for column in RAW_SCANNER_COLUMNS

        )



    # =========================================================
    # Load
    # =========================================================

    def load(
        self,
    ) -> list[LoadedSheet]:


        loaded: list[LoadedSheet] = []



        for workbook in self.discover_workbooks():


            latest_sheets = (

                self.find_latest_scan_sheets(
                    workbook
                )

            )



            for sheet in latest_sheets:


                dataframe = pd.read_excel(

                    workbook,

                    sheet_name=sheet,

                )



                if not self.validate_columns(
                    dataframe
                ):

                    continue



                dataframe = (

                    dataframe[
                        list(RAW_SCANNER_COLUMNS)
                    ]

                    .copy()

                )



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
