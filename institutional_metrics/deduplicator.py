from __future__ import annotations

import pandas as pd



class StockDeduplicator:
    """
    Consolidates multiple stock observations
    into one canonical record.

    Selection priority:

    1. Latest backtest end date.
    2. Latest source workbook modification.

    Does NOT:

    - calculate metrics
    - score stocks
    - rank stocks
    - apply governance
    """



    def deduplicate(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:


        result = dataframe.copy()



        # -----------------------------------------------------
        # Normalize stock identifier
        # -----------------------------------------------------

        result["Stock"] = (

            result["Stock"]

            .astype("string")

            .str.strip()

            .str.upper()

        )



        result = result.loc[

            result["Stock"].notna()

            &

            result["Stock"].ne("")

        ].copy()



        # -----------------------------------------------------
        # Normalize dates
        # -----------------------------------------------------

        if "BT to" in result.columns:

            result["BT to"] = pd.to_datetime(

                result["BT to"],

                errors="coerce",

            )

        else:

            result["BT to"] = pd.NaT



        if "Source Modified" in result.columns:

            result["Source Modified"] = pd.to_datetime(

                result["Source Modified"],

                errors="coerce",

            )

        else:

            result["Source Modified"] = pd.NaT



        # -----------------------------------------------------
        # Sort canonical candidate priority
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



        # -----------------------------------------------------
        # Duplicate audit
        # -----------------------------------------------------

        duplicates = (

            result.loc[

                result["Stock"]

                .duplicated(
                    keep=False
                )

            ]

            .copy()

        )



        # -----------------------------------------------------
        # Keep canonical row
        # -----------------------------------------------------

        deduplicated = (

            result

            .drop_duplicates(

                subset=[

                    "Stock"

                ],

                keep="first",

            )

            .reset_index(
                drop=True
            )

        )



        return (

            deduplicated,

            duplicates,

        )