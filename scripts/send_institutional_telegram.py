from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path


from institutional_metrics.pipeline import (
    build_workbook_pipeline,
)

from institutional_metrics.telegram import (
    TelegramClient,
    TelegramNotificationService,
    telegram_config_from_environment,
)



LOGGER = logging.getLogger(
    "institutional.telegram"
)



# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Send institutional metrics "
            "recommendations to Telegram."
        )
    )


    parser.add_argument(
        "--workbook",
        type=Path,
        default=Path(
            "downloads/institutional_metrics/"
            "institutional_metrics.xlsx"
        ),
        help=(
            "Institutional metrics workbook."
        ),
    )


    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help=(
            "Number of top recommendations "
            "to send."
        ),
    )


    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Generate recommendation without "
            "sending Telegram."
        ),
    )


    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=[
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
        ],
    )


    return parser.parse_args()



# ============================================================
# LOGGING
# ============================================================

def configure_logging(
    level: str,
) -> None:


    logging.basicConfig(
        level=getattr(
            logging,
            level,
        ),
        format=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
    )



# ============================================================
# VALIDATION
# ============================================================

def validate_workbook(
    workbook: Path,
) -> None:


    if not workbook.exists():

        raise FileNotFoundError(
            f"Institutional workbook not found: "
            f"{workbook}"
        )



# ============================================================
# MAIN
# ============================================================

def main() -> int:


    args = parse_args()


    configure_logging(
        args.log_level
    )


    started = time.monotonic()


    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    try:

        LOGGER.info(
            "Starting Telegram recommendation pipeline."
        )


        LOGGER.info(
            "Run ID=%s",
            run_id,
        )


        LOGGER.info(
            "Workbook=%s",
            args.workbook,
        )


        LOGGER.info(
            "Top N=%d",
            args.top_n,
        )


        LOGGER.info(
            "Dry Run=%s",
            args.dry_run,
        )


        validate_workbook(
            args.workbook
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
            args.workbook,
            telegram_service=telegram,
            top_n=args.top_n,
        )


        result = pipeline.run(
            dry_run=args.dry_run,
            send_telegram=not args.dry_run,
        )


        duration = (
            time.monotonic()
            -
            started
        )


        selected = (
            result
            .recommendation_result
            .selected_count
        )


        LOGGER.info(
            "Telegram pipeline completed."
        )


        LOGGER.info(
            "Selected=%d | Sent=%s | Duration=%.2fs",
            selected,
            result.sent_to_telegram,
            duration,
        )


        print()

        print("=" * 72)

        print(
            "INSTITUTIONAL TELEGRAM PIPELINE COMPLETED"
        )

        print("=" * 72)

        print(
            f"Run ID              : {run_id}"
        )

        print(
            f"Selected stocks     : {selected}"
        )

        print(
            f"Telegram sent       : "
            f"{result.sent_to_telegram}"
        )

        print(
            f"Duration            : "
            f"{duration:.2f} seconds"
        )

        print("=" * 72)


        return 0



    except Exception:

        LOGGER.exception(
            "Telegram pipeline failed."
        )

        return 1



if __name__ == "__main__":

    raise SystemExit(
        main()
    )