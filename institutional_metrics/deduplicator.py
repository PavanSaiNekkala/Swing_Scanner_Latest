from __future__ import annotations

import pandas as pd


class StockDeduplicator:
    """
    Consolidates stock observations into one canonical row.
    """

    def deduplicate(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:

        result = dataframe.copy()

        result["Stock"] = (
            result["Stock"]
            .astype("string")
            .str.strip()
            .str.upper()
        )

        result = result[
            result["Stock"].notna()
            & result["Stock"].ne("")
        ].copy()


        result["BT to"] = pd.to_datetime(
            result["BT to"],
            errors="coerce",
        )


        # -----------------------------------------------------
        # Source metadata is added by HistoryLoader.
        # Unit tests and external callers may not provide it.
        # -----------------------------------------------------

        if "Source Modified" not in result.columns:

            result["Source Modified"] = pd.NaT


        result["Source Modified"] = pd.to_datetime(
            result["Source Modified"],
            errors="coerce",
        )


        # -----------------------------------------------------
        # Prefer:
        # 1. Latest backtest end date
        # 2. Latest source workbook modification
        # -----------------------------------------------------

        result = result.sort_values(
            by=[
                "BT to",
                "Source Modified",
            ],
            ascending=[
                False,
                False,
            ],
            na_position="last",
            kind="stable",
        )


        duplicate_rows = (
            result[
                result["Stock"].duplicated(
                    keep=False
                )
            ]
            .copy()
        )


        deduplicated = (
            result
            .drop_duplicates(
                subset=["Stock"],
                keep="first",
            )
            .reset_index(drop=True)
        )


        return (
            deduplicated,
            duplicate_rows,
        )