"""
Report Builder

Builds Excel-ready rows from scan results.
"""

from __future__ import annotations

from typing import Any
from typing import Iterable


class ReportBuilder:

    @staticmethod
    def build_rows(
        results: Iterable[Any],
    ) -> list[dict]:

        rows: list[dict] = []

        for result in results:

            company = result.company

            dividend = (
                result.dividend[0]
                if result.dividend
                else None
            )

            score = result.score

            rows.append(

                {

                    # -------------------------------------------------
                    # Company
                    # -------------------------------------------------

                    "Symbol": company.symbol,
                    "Company": company.company_name,
                    "Sector": company.sector,
                    "Industry": company.industry,
                    "Market Cap": company.market_cap,

                    # -------------------------------------------------
                    # Dividend
                    # -------------------------------------------------

                    "Dividend Amount":
                        dividend.amount if dividend else None,

                    "Dividend Yield (%)": result.dividend_yield,

                    "Ex Date":
                        dividend.ex_date if dividend else None,

                    "Record Date":
                        dividend.record_date if dividend else None,

                    "Payment Date":
                        dividend.payment_date if dividend else None,

                    "Annual Dividend":
                        result.annual_dividend,

                    "Average Dividend":
                        result.average_dividend,

                    "Years Paying":
                        result.years_paying,

                    "Dividend Count":
                        result.dividend_count,

                    # -------------------------------------------------
                    # OHLC Window
                    # -------------------------------------------------

                    "D-3 Close":
                        result.d3_close,

                    "D-2 Close":
                        result.d2_close,

                    "D-1 Close":
                        result.d1_close,

                    "D0 Close":
                        result.d0_close,

                    "D+1 Close":
                        result.p1_close,

                    "D+2 Close":
                        result.p2_close,

                    "D+3 Close":
                        result.p3_close,

                    # -------------------------------------------------
                    # Returns
                    # -------------------------------------------------

                    "D-3 → D0 %":
                        result.d3_to_d0_return,

                    "D-2 → D0 %":
                        result.d2_to_d0_return,

                    "D-1 → D0 %":
                        result.d1_to_d0_return,

                    "D0 → D+1 %":
                        result.d0_to_p1_return,

                    "D0 → D+2 %":
                        result.d0_to_p2_return,

                    "D0 → D+3 %":
                        result.d0_to_p3_return,

                    "Window Return %":
                        result.window_return,

                    # -------------------------------------------------
                    # Volume
                    # -------------------------------------------------

                    "Average Volume":
                        result.average_volume,

                    "Volume Change %":
                        result.volume_change,

                    # -------------------------------------------------
                    # News
                    # -------------------------------------------------

                    "News Count":
                        result.news_count,

                    "Latest News":
                        result.latest_news,

                    "Latest News Date":
                        result.latest_news_date,

                    "News Sentiment":
                        result.news_sentiment,

                    # -------------------------------------------------
                    # Score
                    # -------------------------------------------------

                    "Dividend Score":
                        score.dividend_score if score else None,

                    "Return Score":
                        score.return_score if score else None,

                    "Volume Score":
                        score.volume_score if score else None,

                    "News Score":
                        score.news_score if score else None,

                    "Total Score":
                        score.total_score if score else None,

                    "Recommendation":
                        score.recommendation if score else None,

                }

            )

        return rows

    @staticmethod
    def column_order(
        rows: list[dict],
    ) -> list[str]:

        if not rows:
            return []

        return list(rows[0].keys())