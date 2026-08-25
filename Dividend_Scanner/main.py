"""
Dividend Scanner

Application Entry Point.
"""

from __future__ import annotations

import sys
import time

import pandas as pd

from config.settings import (
    INPUT_DIR,
    OUTPUT_DIR,
)

from app.pipeline.scanner import Scanner
from app.exporters.excel_exporter import ExcelExporter
from app.database.init_db import init_database
from app.utils.logger import get_logger


logger = get_logger("Main")

INPUT_FILE = INPUT_DIR / "nse_universe.csv"

OUTPUT_FILE = OUTPUT_DIR / "dividend_report.xlsx"


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------


def main() -> int:

    start = time.perf_counter()

    logger.info(
        "=" * 80
    )

    logger.info(
        "Dividend Scanner Started"
    )

    logger.info(
        "=" * 80
    )

    logger.info(
        f"Input : {INPUT_FILE}"
    )

    logger.info(
        f"Output: {OUTPUT_FILE}"
    )

    if not INPUT_FILE.exists():

        logger.error(
            f"Input file not found : {INPUT_FILE}"
        )

        return 1

    try:

        df = pd.read_csv(
            INPUT_FILE
        )

        if "Symbol" in df.columns:

            symbols = (
                df["Symbol"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

        else:

            symbols = (
                df.iloc[:, 0]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

        logger.info(
            f"Loaded {len(symbols)} symbols"
        )

        init_database()
        
        scanner = Scanner()

        results = []

        for index, symbol in enumerate(

            symbols,

            start=1,

        ):

            logger.info(

                f"[{index}/{len(symbols)}] "
                f"Processing {symbol}"

            )

            try:

                result = scanner.scan(
                    symbol
                )

                if result is not None:

                    results.append(
                        result
                    )

            except Exception:

                logger.exception(

                    f"Failed : {symbol}"

                )

        logger.info(

            f"Completed scan : "
            f"{len(results)} results"

        )

        #
        # Excel export
        #

        if results:

            logger.info(
                "Exporting report..."
            )

            output = ExcelExporter().export(

                results,

                OUTPUT_FILE,

            )

            logger.info(

                f"Report saved to: {output}"

            )

        else:

            logger.warning(

                "No results to export."

            )

        elapsed = (

            time.perf_counter()
            - start

        )

        logger.info(

            f"Finished in "
            f"{elapsed:.2f} seconds"

        )

        return 0

    except Exception:

        logger.exception(
            "Application failed."
        )

        return 1


# ---------------------------------------------------------
# Entry
# ---------------------------------------------------------


if __name__ == "__main__":

    sys.exit(
        main()
    )