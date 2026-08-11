from __future__ import annotations

from pathlib import Path

import pandas as pd


class InstitutionalExporter:
    """
    Writes institutional metrics outputs.
    """

    def export(
        self,
        dataframe: pd.DataFrame,
        duplicates: pd.DataFrame,
        output_directory: Path,
    ) -> tuple[Path, Path]:

        output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        csv_path = (
            output_directory
            / "institutional_metrics.csv"
        )

        excel_path = (
            output_directory
            / "institutional_metrics.xlsx"
        )

        signals = (
            dataframe[
                dataframe["Signals today"]
                .astype(bool)
            ]
            .sort_values(
                by=[
                    "Institutional Rank",
                    "Stock",
                ],
                kind="stable",
            )
        )

        summary = pd.DataFrame(
            {
                "Metric": [
                    "Total Universe",
                    "Signalled Stocks",
                    "Eligible Signals",
                    "Rejected Signals",
                    "Duplicate Rows Removed",
                ],
                "Value": [
                    len(dataframe),
                    len(signals),
                    int(
                        signals[
                            "Institutional Eligible"
                        ].sum()
                    ),
                    int(
                        (
                            ~signals[
                                "Institutional Eligible"
                            ]
                        ).sum()
                    ),
                    len(duplicates),
                ],
            }
        )

        dataframe.to_csv(
            csv_path,
            index=False,
        )

        with pd.ExcelWriter(
            excel_path,
            engine="openpyxl",
        ) as writer:

            signals.to_excel(
                writer,
                sheet_name="Institutional_Ranking",
                index=False,
            )

            dataframe.to_excel(
                writer,
                sheet_name="Full_Universe",
                index=False,
            )

            duplicates.to_excel(
                writer,
                sheet_name="Duplicates_Removed",
                index=False,
            )

            summary.to_excel(
                writer,
                sheet_name="Summary",
                index=False,
            )

        return (
            csv_path,
            excel_path,
        )