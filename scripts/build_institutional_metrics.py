from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

from institutional_metrics.engine import (
    InstitutionalMetricsEngine,
)


LOGGER = logging.getLogger(
    "build_institutional_metrics"
)


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Build institutional metrics "
            "and institutional ranking."
        )
    )

    parser.add_argument(
        "--history-dir",
        type=Path,
        default=Path(
            "downloads/history"
        ),
        help=(
            "Scanner history workbook directory."
        ),
    )


    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "downloads/institutional_metrics"
        ),
        help=(
            "Institutional output directory."
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
        help="Logging level.",
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

def validate_directories(
    history_dir: Path,
    output_dir: Path,
) -> None:


    if not history_dir.exists():

        raise FileNotFoundError(
            f"History directory missing: "
            f"{history_dir}"
        )


    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )



# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    result,
    duration: float,
) -> None:


    eligible = int(
        result.signals[
            "Institutional Eligible"
        ].sum()
    )


    rejected = (
        len(result.signals)
        -
        eligible
    )


    print()

    print("=" * 72)

    print(
        "INSTITUTIONAL METRICS BUILD COMPLETED"
    )

    print("=" * 72)

    print(
        f"Run duration          : "
        f"{duration:.2f} seconds"
    )

    print(
        f"Unique universe       : "
        f"{len(result.universe)}"
    )

    print(
        f"Signalled stocks      : "
        f"{len(result.signals)}"
    )

    print(
        f"Eligible signals      : "
        f"{eligible}"
    )

    print(
        f"Rejected signals      : "
        f"{rejected}"
    )

    print(
        f"Duplicates removed    : "
        f"{len(result.duplicates)}"
    )

    print(
        f"CSV                   : "
        f"{result.csv_path}"
    )

    print(
        f"Excel                 : "
        f"{result.excel_path}"
    )

    print("=" * 72)



# ============================================================
# MAIN
# ============================================================

def main() -> int:


    args = parse_args()


    configure_logging(
        args.log_level
    )


    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )


    started = time.monotonic()


    try:

        LOGGER.info(
            "Starting institutional metrics build."
        )


        LOGGER.info(
            "Run ID: %s",
            run_id,
        )


        LOGGER.info(
            "History directory: %s",
            args.history_dir,
        )


        LOGGER.info(
            "Output directory: %s",
            args.output_dir,
        )


        validate_directories(
            args.history_dir,
            args.output_dir,
        )


        engine = (
            InstitutionalMetricsEngine()
        )


        result = engine.run(
            history_directory=args.history_dir,
            output_directory=args.output_dir,
        )


        duration = (
            time.monotonic()
            -
            started
        )


        eligible = int(
            result.signals[
                "Institutional Eligible"
            ].sum()
        )


        LOGGER.info(
            "Build completed successfully."
        )


        LOGGER.info(
            "Universe=%d | Signals=%d | Eligible=%d",
            len(result.universe),
            len(result.signals),
            eligible,
        )


        LOGGER.info(
            "CSV=%s",
            result.csv_path,
        )


        LOGGER.info(
            "Excel=%s",
            result.excel_path,
        )


        print_summary(
            result,
            duration,
        )


        return 0



    except Exception:

        LOGGER.exception(
            "Institutional metrics build failed."
        )

        return 1



if __name__ == "__main__":

    raise SystemExit(
        main()
    )