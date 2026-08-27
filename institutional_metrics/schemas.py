from __future__ import annotations



# ============================================================
# RAW SCANNER REQUIRED INPUT COLUMNS
# ============================================================

REQUIRED_COLUMNS: tuple[str, ...] = (

    # Identity

    "Stock",

    "Signals today",


    # Ranking / Alpha

    "Rank",

    "Exp/DAY%",

    "RS%",



    # Trade statistics

    "Trades",

    "Seq. trades",

    "Win%",



    # Return quality

    "Expectancy%",

    "Avg win%",

    "Avg loss%",


    # Efficiency

    "R:R",

    "Avg days",


    # Performance

    "Total return (sum)%",

    "CAGR%",



    # Risk

    "Max DD%",

    "Profit factor",

    "Recovery factor",

    "Max consec. losses",



    # Backtest validity

    "BT from",

    "BT to",

    "Years",

)



# ============================================================
# NUMERIC NORMALIZATION COLUMNS
# ============================================================

NUMERIC_COLUMNS: tuple[str, ...] = (

    "Rank",

    "Exp/DAY%",

    "RS%",


    "Trades",

    "Seq. trades",

    "Win%",


    "Expectancy%",

    "Avg win%",

    "Avg loss%",


    "R:R",

    "Avg days",


    "Total return (sum)%",

    "CAGR%",


    "Max DD%",


    "Profit factor",

    "Recovery factor",

    "Max consec. losses",


    "Years",

)