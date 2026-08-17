"""
Application entry point.

Responsibilities
----------------
- Bootstrap the application
- Configure dependencies
- Execute pipelines
- Handle fatal exceptions
- Produce the final Excel report

Author
------
Pavan Sai Nekkala

Project
-------
NEWS_REPORT

Python
------
3.12+
"""

from __future__ import annotations

from config.logging_config import get_logger

from data.providers.yfinance_provider import (
    YahooFinanceProvider,
)

from market.loader import (
    build_universe_loader,
)

from market.pipeline import (
    build_market_pipeline,
)

from market.ranking import (
    build_market_ranking_engine,
)

from news.collector import (
    build_news_collector,
)

from news.pipeline import (
    build_news_pipeline,
)

from reports.report_pipeline import (
    build_report_pipeline,
)

from market.models import (
    ApplicationReport,
)

logger = get_logger(__name__)

###############################################################################
# NEWS_REPORT Application
###############################################################################


class NewsReportApplication:
    """
    Root application.

    Creates all dependencies and orchestrates
    the complete NEWS_REPORT workflow.
    """

    ###########################################################################
    # Construction
    ###########################################################################

    def __init__(
        self,
    ) -> None:

        logger.info(
            "=" * 80,
        )

        logger.info(
            "Initializing NEWS_REPORT..."
        )

        logger.info(
            "=" * 80,
        )

        #######################################################################
        # Infrastructure
        #######################################################################

        self.loader = (
            build_universe_loader()
        )

        self.market_provider = (
            YahooFinanceProvider()
        )

        self.ranking_engine = (
            build_market_ranking_engine()
        )

        self.news_collector = (
            build_news_collector()
        )

        #######################################################################
        # Pipelines
        #######################################################################

        self.market_pipeline = (
            build_market_pipeline(
                loader=self.loader,
                provider=self.market_provider,
                ranking_engine=self.ranking_engine,
            )
        )

        self.news_pipeline = (
            build_news_pipeline(
                collector=self.news_collector,
            )
        )

        self.report_pipeline = (
            build_report_pipeline()
        )

        logger.info(
            "Application initialized successfully."
        )

    ###########################################################################
    # Execution Helpers
    ###########################################################################

    def run_market_pipeline(
        self,
    ):
        """
        Execute market workflow.
        """

        logger.info(
            "Executing Market Pipeline..."
        )

        return (
            self.market_pipeline.execute()
        )

    def run_news_pipeline(
        self,
        market_report,
    ):
        """
        Execute news workflow.
        """

        logger.info(
            "Executing News Pipeline..."
        )

        return (
            self.news_pipeline.execute(
                market_report,
            )
        )

    @staticmethod
    def build_application_report(
        market_report,
        news_report,
    ) -> ApplicationReport:
        """
        Build root report object.
        """

        return ApplicationReport(
            market=market_report,
            news=news_report,
        )

    ###########################################################################
    # Application Execution
    ###########################################################################

    def run(
        self,
    ) -> int:
        """
        Execute the complete NEWS_REPORT workflow.

        Returns
        -------
        int
            Process exit code.
        """

        try:

            logger.info(
                "=" * 80,
            )

            logger.info(
                "Starting NEWS_REPORT"
            )

            logger.info(
                "=" * 80,
            )

            ###################################################################
            # Market Pipeline
            ###################################################################

            market_report = (
                self.run_market_pipeline()
            )

            logger.info(
                "Market Pipeline completed."
            )

            ###################################################################
            # News Pipeline
            ###################################################################

            news_report = (
                self.run_news_pipeline(
                    market_report,
                )
            )

            logger.info(
                "News Pipeline completed."
            )

            ###################################################################
            # Build Root Report
            ###################################################################

            application_report = (
                self.build_application_report(
                    market_report,
                    news_report,
                )
            )

            ###################################################################
            # Reporting
            ###################################################################

            logger.info(
                "Generating Excel report..."
            )

            self.report_pipeline.execute(
                application_report,
            )

            logger.info(
                "Excel report generated successfully."
            )

            logger.info(
                "=" * 80,
            )

            logger.info(
                "NEWS_REPORT completed successfully."
            )

            logger.info(
                "=" * 80,
            )

            return 0

        except KeyboardInterrupt:

            logger.warning(
                "Execution cancelled by user."
            )

            return 130

        except Exception:

            logger.exception(
                "Fatal application error."
            )

            return 1


###############################################################################
# Factory
###############################################################################


def build_application(
) -> NewsReportApplication:
    """
    Factory for the application.
    """

    logger.info(
        "Creating application..."
    )

    return NewsReportApplication()


###############################################################################
# Entry Point
###############################################################################


def main() -> int:
    """
    Program entry point.
    """

    application = (
        build_application()
    )

    return application.run()


if __name__ == "__main__":

    raise SystemExit(
        main()
    )