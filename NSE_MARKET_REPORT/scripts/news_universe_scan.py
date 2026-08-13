from __future__ import annotations

from config.config import (
    NEWS_UNIVERSE_FILE,
)

from config.logging_config import logger

from news.news_manager import NewsManager
from reports.news_excel_export import (
    NewsExcelExporter,
)


def main() -> None:

    logger.info(
        "=" * 80
    )

    logger.info(
        "FULL NEWS UNIVERSE SCAN"
    )

    logger.info(
        "=" * 80
    )

    manager = NewsManager()

    exporter = NewsExcelExporter()

    try:

        news_df = manager.scan_news_universe(
            NEWS_UNIVERSE_FILE
        )

        if news_df.empty:

            logger.warning(
                "News universe returned no data."
            )

            return

        exporter.export(
            news_df
        )

        logger.info(
            "FULL NEWS UNIVERSE SCAN COMPLETED"
        )

    finally:

        manager.close()


if __name__ == "__main__":
    main()