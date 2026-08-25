"""
Scanner

Coordinates all services and builds the final ScanResult.
"""

from __future__ import annotations

from datetime import date

from app.models.scan_result import ScanResult

from app.services.analytics_service import AnalyticsService
from app.services.company_service import CompanyService
from app.services.dividend_service import DividendService
from app.services.market_service import MarketService
from app.services.news_service import NewsService
from app.services.scoring_service import ScoringService


class Scanner:

    def __init__(self):

        self.company = CompanyService()
        self.dividend = DividendService()
        self.market = MarketService()
        self.news = NewsService()
        self.analytics = AnalyticsService()
        self.scoring = ScoringService()


    def scan(
        self,
        symbol: str,
    ) -> ScanResult | None:

        # ---------------------------------------------------------
        # Fetch Data
        # ---------------------------------------------------------

        company = self.company.get(
            symbol,
        )

        if company is None:

            return None

        dividends = self.dividend.get(
            symbol,
        )

        market = self.market.get(
            symbol,
        )

        news = self.news.get(
            company,
        )

        # ---------------------------------------------------------
        # Dividend Analytics
        # ---------------------------------------------------------

        annual_dividend = None

        average_dividend = None

        dividend_yield = None

        years_paying = None

        dividend_count = len(

            dividends,

        )

        if dividends:

            annual_dividend = (

                self.analytics.metrics.annual_dividend(

                    dividends,

                    date.today(),

                )

            )

            average_dividend = (

                self.analytics.metrics.average_dividend(

                    dividends,

                    date.today(),

                )

            )

            valid_dates = [

                dividend.ex_date

                for dividend in dividends

                if dividend.ex_date

            ]

            # ---------------------------------------------------------
            # Dividend Yield
            # ---------------------------------------------------------

            if annual_dividend is not None and market:

                # Assuming market history is oldest -> newest.
                # Change to market[0] if your MarketService returns newest first.

                latest_price = market[-1].close

                if latest_price is not None:

                    dividend_yield = (

                        self.analytics.metrics.dividend_yield(

                            annual_dividend,

                            latest_price,

                        )

                    )

            # ---------------------------------------------------------
            # Years Paying
            # ---------------------------------------------------------

            if valid_dates:

                years_paying = (

                    self.analytics.metrics.years_since_first_dividend(

                        min(

                            valid_dates,

                        ),

                        date.today(),

                    )

                )

        # ---------------------------------------------------------
        # News Analytics
        # ---------------------------------------------------------

        news_count = len(
            news,
        )

        latest_news = None

        latest_news_date = None

        if news:

            latest = news[0]

            latest_news = latest.headline

            latest_news_date = latest.published_at

        # ---------------------------------------------------------
        # OHLC Window Analytics
        # ---------------------------------------------------------

        window = {}

        if dividends and market:

            first_dividend = next(

                (

                    dividend

                    for dividend in dividends

                    if dividend.ex_date

                ),

                None,

            )

            if first_dividend:

                window = self.analytics.window.build_window(

                    ex_date=first_dividend.ex_date,

                    history=market,

                )

        # ---------------------------------------------------------
        # Build ScanResult
        # ---------------------------------------------------------

        result = ScanResult(

            company=company,

            dividend=dividends,

            market=market,

            news=news,

            annual_dividend=annual_dividend,

            average_dividend=average_dividend,

            dividend_yield=dividend_yield,

            years_paying=years_paying,

            dividend_count=dividend_count,

            news_count=news_count,

            latest_news=latest_news,

            latest_news_date=latest_news_date,

            **window,

        )

        # ---------------------------------------------------------
        # Score
        # ---------------------------------------------------------

        result.score = self.scoring.calculate(

            result,

        )

        return result