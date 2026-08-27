from __future__ import annotations


import argparse
import logging
import time

from datetime import datetime, timezone

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

            "Build institutional metrics, "
            "conviction ranking and governance output."

        )

    )


    parser.add_argument(

        "--history-dir",

        type=Path,

        default=Path(
            "downloads/history"
        ),

    )


    parser.add_argument(

        "--output-dir",

        type=Path,

        default=Path(
            "downloads/institutional_metrics"
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


def validate_directories(

    history_dir: Path,

    output_dir: Path,

) -> None:



    if not history_dir.exists():


        raise FileNotFoundError(

            f"History directory missing: {history_dir}"

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



    signals = result.signals



    eligible = int(

        signals.get(

            "Institutional Eligible",

            False,

        ).sum()

    )



    rejected = (

        len(signals)

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

        f"Duration              : "
        f"{duration:.2f} seconds"

    )


    print(

        f"Universe              : "
        f"{len(result.universe)}"

    )


    print(

        f"Signals               : "
        f"{len(signals)}"

    )


    print(

        f"Eligible               : "
        f"{eligible}"

    )


    print(

        f"Rejected               : "
        f"{rejected}"

    )


    print(

        f"Duplicates             : "
        f"{len(result.duplicates)}"

    )


    if "Rank Score" in signals.columns:


        print(

            f"Highest Rank Score     : "
            f"{signals['Rank Score'].max():.2f}"

        )



    if "Institutional Score" in signals.columns:


        print(

            f"Highest Institutional : "
            f"{signals['Institutional Score'].max():.2f}"

        )



    print(

        f"CSV                    : "
        f"{result.csv_path}"

    )


    print(

        f"Excel                  : "
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



    run_id = datetime.now(

        timezone.utc

    ).strftime(

        "%Y%m%d_%H%M%S"

    )



    started = time.monotonic()



    try:



        LOGGER.info(
            "Starting institutional metrics build."
        )


        LOGGER.info(

            "Run ID=%s",

            run_id,

        )


        LOGGER.info(

            "History=%s | Output=%s",

            args.history_dir,

            args.output_dir,

        )



        validate_directories(

            args.history_dir,

            args.output_dir,

        )



        engine = InstitutionalMetricsEngine()



        result = engine.run(

            history_directory=args.history_dir,

            output_directory=args.output_dir,

        )



        duration = (

            time.monotonic()

            -

            started

        )



        LOGGER.info(

            "Build successful | "
            "Universe=%d | "
            "Signals=%d",

            len(result.universe),

            len(result.signals),

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