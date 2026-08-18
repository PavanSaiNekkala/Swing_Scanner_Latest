"""
===============================================================================
Validate Indian Stock Symbols

Reads:
    stocks.xlsx

Expected Column:
    Symbol

Outputs:
    valid_symbols.csv
    invalid_symbols.csv

Author:
    Pavan Sai
===============================================================================
"""

from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

###############################################################################
# Configuration
###############################################################################

INPUT_FILE = "valid_stocks.xlsx"

SYMBOL_COLUMN = "Stock"

VALID_OUTPUT = "valid_symbols.csv"

INVALID_OUTPUT = "invalid_symbols.csv"

DOWNLOAD_PERIOD = "5d"

DOWNLOAD_INTERVAL = "1d"

###############################################################################
# Helpers
###############################################################################


def is_valid_symbol(
    symbol: str,
) -> tuple[bool, str]:
    """
    Check symbol on NSE and BSE using Yahoo Finance.

    Returns
    -------
    (True, ticker)
        if valid

    (False, "")
        otherwise
    """

    symbol = str(symbol).strip().upper()

    candidates = [
        f"{symbol}",
        #f"{symbol}.BO",
    ]

    for ticker in candidates:

        try:

            df = yf.download(
                ticker,
                period=DOWNLOAD_PERIOD,
                interval=DOWNLOAD_INTERVAL,
                progress=False,
                auto_adjust=False,
                threads=False,
            )

            if not df.empty:

                return True, ticker

        except Exception:
            pass

    return False, ""


###############################################################################
# Main
###############################################################################


def main():

    print("=" * 70)
    print("Reading Excel...")
    print("=" * 70)

    df = pd.read_excel(INPUT_FILE)

    if SYMBOL_COLUMN not in df.columns:

        raise ValueError(
            f"'{SYMBOL_COLUMN}' column not found."
        )

    valid = []

    invalid = []

    total = len(df)

    for i, symbol in enumerate(df[SYMBOL_COLUMN], start=1):

        print(f"[{i}/{total}] Checking {symbol}...")

        ok, ticker = is_valid_symbol(symbol)

        if ok:

            exchange = (
                "NSE"
                if ticker.endswith(".NS")
                else "BSE"
            )

            valid.append(
                {
                    "Symbol": symbol,
                    "Yahoo Symbol": ticker,
                    "Exchange": exchange,
                }
            )

            print(f"    ✓ Valid ({exchange})")

        else:

            invalid.append(
                {
                    "Symbol": symbol,
                }
            )

            print("    ✗ Invalid")

        #
        # Prevent Yahoo rate limiting.
        #

        time.sleep(0.10)

    pd.DataFrame(valid).to_csv(
        VALID_OUTPUT,
        index=False,
    )

    pd.DataFrame(invalid).to_csv(
        INVALID_OUTPUT,
        index=False,
    )

    print()
    print("=" * 70)
    print("Validation Complete")
    print("=" * 70)
    print(f"Total      : {total}")
    print(f"Valid      : {len(valid)}")
    print(f"Invalid    : {len(invalid)}")
    print(f"Saved      : {VALID_OUTPUT}")
    print(f"Saved      : {INVALID_OUTPUT}")


###############################################################################

if __name__ == "__main__":

    main()