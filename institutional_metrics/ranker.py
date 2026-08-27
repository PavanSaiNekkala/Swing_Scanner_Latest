from __future__ import annotations

import pandas as pd



class InstitutionalRanker:
    """
    Institutional ranking engine.

    Ranking priority:

    1. Eligible institutional signals
    2. Conviction Rank Score
    3. Institutional Score
    4. Stock


    Institutional Rank is assigned only
    to active signals.

    Responsibilities:

    - Rank active signals
    - Assign institutional rank
    - Classify rating
    - Generate investment decision


    Does NOT:

    - Calculate Rank Score
    - Calculate Institutional Score
    - Apply governance rules
    """



    def rank(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:


        result = dataframe.copy()


        result[
            "Institutional Rank"
        ] = pd.Series(

            pd.NA,

            index=result.index,

            dtype="Int64",

        )


        # ----------------------------------------------------
        # Institutional Priority Score
        #
        # Final ranking metric:
        #
        # 70% Historical Quality
        # 30% Current Conviction
        #
        # Institutional Score:
        #   Backtest quality,
        #   profitability,
        #   risk,
        #   robustness
        #
        # Rank Score:
        #   Current opportunity:
        #   confidence,
        #   RS,
        #   stage alignment,
        #   freshness,
        #   news
        #
        # ----------------------------------------------------

        result[
            "Institutional Priority Score"
        ] = (

            result[
                "Institutional Score"
            ]
            * 0.50

            +

            result[
                "Rank Score"
            ]
            * 3
            * 0.50

        )


        active_mask = (

            result[
                "Signals today"
            ]
            .astype(bool)

        )


        signals = result.loc[
            active_mask
        ].copy()

        if signals.empty:

            return result



        signals = signals.sort_values(

            by=[

                "Institutional Eligible",

                "Institutional Priority Score",

                "Institutional Score",

                "Rank Score",

                "Stock",

            ],

            ascending=[

                False,

                False,

                False,

                False,

                True,

            ],

            kind="stable",

        )


        result.loc[

            signals.index,

            "Institutional Rank",

        ] = range(

            1,

            len(signals) + 1,

        )



        result = result.sort_values(

            by=[

                "Institutional Rank",

            ],

            ascending=[

                True,

            ],

            na_position="last",

            kind="stable",

        ).reset_index(

            drop=True

        )


        return result




    def classify(

        self,

        dataframe: pd.DataFrame,

    ) -> pd.DataFrame:



        result = dataframe.copy()



        result[

            "Institutional Rating"

        ] = result[

            "Institutional Score"

        ].map(

            self._rating

        )



        result[

            "Institutional Decision"

        ] = result.apply(

            self._decision,

            axis=1,

        )



        return result





    @staticmethod
    def _rating(

        score: float,

    ) -> str:



        if score >= 90:

            return "A+"



        if score >= 80:

            return "A"



        if score >= 70:

            return "B+"



        if score >= 60:

            return "B"



        if score >= 50:

            return "C"



        if score >= 40:

            return "D"



        return "F"





    @staticmethod
    def _decision(

        row: pd.Series,

    ) -> str:



        if not bool(

            row.get(

                "Signals today",

                False,

            )

        ):

            return "NO_SIGNAL"



        if not bool(

            row.get(

                "Institutional Eligible",

                False,

            )

        ):

            return "REJECT"



        score = float(

            row.get(

                "Institutional Score",

                0,

            )

            or 0

        )



        rank_score = float(

            row.get(

                "Rank Score",

                0,

            )

            or 0

        )



        # ----------------------------------------------------
        # Institutional decision thresholds
        #
        # Calibrated against current production distribution:
        #
        # Institutional Score:
        #   Quality of historical edge
        #
        # Rank Score:
        #   Current opportunity conviction
        #
        # ----------------------------------------------------


        if (

            score >= 70

            and

            rank_score >= 20

        ):

            return "STRONG_BUY"



        if (

            score >= 60

            and

            rank_score >= 15

        ):

            return "BUY"



        if score >= 50:

            return "WATCH"



        return "WEAK_WATCH"
