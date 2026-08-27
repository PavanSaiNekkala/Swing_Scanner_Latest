from __future__ import annotations

from pathlib import Path

import pandas as pd



class InstitutionalExporter:
    """
    Writes institutional metrics outputs.

    Responsibilities:

    - CSV persistence
    - Excel reporting
    - Summary generation

    Does NOT:

    - calculate metrics
    - rank stocks
    - apply governance
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
            /
            "institutional_metrics.csv"
        )


        excel_path = (
            output_directory
            /
            "institutional_metrics.xlsx"
        )



        # -----------------------------------------------------
        # Signal ranking output
        # -----------------------------------------------------

        signals = dataframe.loc[
            dataframe[
                "Signals today"
            ].astype(bool)
        ].copy()



        ranking_columns = [

            "Institutional Rank",

            "Rank Score",

            "Institutional Score",

            "Stock",

        ]


        available_sort_columns = [

            column

            for column in ranking_columns

            if column in signals.columns

        ]



        if available_sort_columns:

            signals = signals.sort_values(

                by=available_sort_columns,

                ascending=[

                    True
                    if column
                    ==
                    "Institutional Rank"

                    else False

                    for column
                    in available_sort_columns

                ],

                kind="stable",

            )



        # -----------------------------------------------------
        # Summary
        # -----------------------------------------------------

        eligible_count = 0


        if "Institutional Eligible" in signals.columns:

            eligible_count = int(

                signals[
                    "Institutional Eligible"
                ]
                .sum()

            )


        rejected_count = (

            len(signals)

            -

            eligible_count

        )



        summary_rows = [

            (
                "Total Universe",
                len(dataframe),
            ),

            (
                "Signalled Stocks",
                len(signals),
            ),

            (
                "Eligible Signals",
                eligible_count,
            ),

            (
                "Rejected Signals",
                rejected_count,
            ),

            (
                "Duplicate Rows Removed",
                len(duplicates),
            ),

        ]



        if "Institutional Score" in signals.columns:

            summary_rows.append(

                (
                    "Average Institutional Score",

                    round(

                        signals[
                            "Institutional Score"
                        ]
                        .mean(),

                        2,

                    ),

                )

            )



        if "Rank Score" in signals.columns:

            summary_rows.append(

                (
                    "Average Rank Score",

                    round(

                        signals[
                            "Rank Score"
                        ]
                        .mean(),

                        2,

                    ),

                )

            )



        if "Institutional Decision" in signals.columns:

            decision_counts = (

                signals[
                    "Institutional Decision"
                ]
                .value_counts()

            )


            for decision, count in decision_counts.items():

                summary_rows.append(

                    (
                        f"Decision - {decision}",

                        int(count),

                    )

                )



        summary = pd.DataFrame(

            summary_rows,

            columns=[

                "Metric",

                "Value",

            ],

        )



        # -----------------------------------------------------
        # CSV
        # -----------------------------------------------------

        dataframe.to_csv(

            csv_path,

            index=False,

        )



        # -----------------------------------------------------
        # Excel
        # -----------------------------------------------------

        with pd.ExcelWriter(

            excel_path,

            engine="openpyxl",

        ) as writer:



            signals.to_excel(

                writer,

                sheet_name=(
                    "Institutional_Ranking"
                ),

                index=False,

            )



            dataframe.to_excel(

                writer,

                sheet_name=(
                    "Full_Universe"
                ),

                index=False,

            )



            duplicates.to_excel(

                writer,

                sheet_name=(
                    "Duplicates_Removed"
                ),

                index=False,

            )



            summary.to_excel(

                writer,

                sheet_name=(
                    "Summary"
                ),

                index=False,

            )



        return (

            csv_path,

            excel_path,

        )