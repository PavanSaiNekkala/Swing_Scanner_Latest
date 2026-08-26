from __future__ import annotations

import pandas as pd


class InstitutionalRanker:
    """
    Ranks active signals using the Institutional Score.

    Eligible signals always rank ahead of ineligible signals.
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

        active_mask = (
            result["Signals today"]
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
                "Institutional Score",
                "Stock",
            ],
            ascending=[
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
            ascending=True,
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

        if not row["Signals today"]:
            return "NO_SIGNAL"

        if not row["Institutional Eligible"]:
            return "REJECT"

        score = float(
            row["Institutional Score"]
        )

        if score >= 80:
            return "STRONG_BUY"

        if score >= 70:
            return "BUY"

        if score >= 60:
            return "WATCH"

        return "WEAK_WATCH"