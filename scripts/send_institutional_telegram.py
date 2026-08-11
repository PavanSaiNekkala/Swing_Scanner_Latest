from pathlib import Path
import logging

from institutional_metrics.pipeline import (
    build_workbook_pipeline,
)
from institutional_metrics.telegram import (
    TelegramClient,
    TelegramNotificationService,
    telegram_config_from_environment,
)


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "institutional.telegram"
)


def main() -> int:

    workbook = Path(
        "downloads/institutional_metrics/"
        "institutional_metrics.xlsx"
    )

    config = (
        telegram_config_from_environment()
    )

    client = TelegramClient(
        config
    )

    telegram = (
        TelegramNotificationService(
            client
        )
    )

    pipeline = build_workbook_pipeline(
        workbook,
        telegram_service=telegram,
        top_n=5,
    )

    result = pipeline.run(
        dry_run=False,
        send_telegram=True,
    )

    logger.info(
        "Telegram pipeline completed | "
        "Selected=%d | "
        "Sent=%s",
        result.recommendation_result.selected_count,
        result.sent_to_telegram,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )