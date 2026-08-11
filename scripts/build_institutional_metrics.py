from __future__ import annotations

import argparse
import logging
from pathlib import Path

from institutional_metrics import (
    InstitutionalMetricsEngine,
)


LOGGER = logging.getLogger(
    "build_institutional_metrics"
)


def parse_args() -> argparse.Namespace:

    parser = argparse.ArgumentParser(
        description=(
            "Build institutional metrics and "
            "institutional ranking from scanner "
            "history workbooks."
        )
    )

    parser.add_argument(
        "--history-dir",
        type=Path,
        default=Path(
            "downloads/history"
        ),
        help=(
            "Directory containing scanner "
            "history Excel workbooks."
        ),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "downloads/institutional_metrics"
        ),
        help=(
            "Directory where institutional "
            "outputs are written."
        ),
    )

    return parser.parse_args()


def main() -> int:

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    args = parse_args()

    LOGGER.info(
        "Starting institutional metrics build."
    )

    LOGGER.info(
        "History directory: %s",
        args.history_dir,
    )

    LOGGER.info(
        "Output directory: %s",
        args.output_dir,
    )

    engine = (
        InstitutionalMetricsEngine()
    )

    result = engine.run(
        history_directory=args.history_dir,
        output_directory=args.output_dir,
    )

    eligible = int(
        result.signals[
            "Institutional Eligible"
        ].sum()
    )

    rejected = (
        len(result.signals)
        - eligible
    )

    LOGGER.info(
        "Institutional metrics build completed."
    )

    LOGGER.info(
        "Unique universe: %d",
        len(result.universe),
    )

    LOGGER.info(
        "Active signals: %d",
        len(result.signals),
    )

    LOGGER.info(
        "Eligible signals: %d",
        eligible,
    )

    LOGGER.info(
        "Rejected signals: %d",
        rejected,
    )

    LOGGER.info(
        "Duplicate rows removed: %d",
        len(result.duplicates),
    )

    LOGGER.info(
        "CSV: %s",
        result.csv_path,
    )

    LOGGER.info(
        "Excel: %s",
        result.excel_path,
    )

    print()
    print("=" * 72)
    print(
        "INSTITUTIONAL METRICS BUILD COMPLETED"
    )
    print("=" * 72)
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

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )