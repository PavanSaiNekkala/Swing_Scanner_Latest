from __future__ import annotations



# ============================================================
# RAW SCANNER INPUT COLUMNS
# ============================================================

RAW_SCANNER_COLUMNS: tuple[str, ...] = (

    # --------------------------------------------------------
    # Identity
    # --------------------------------------------------------

    "Stock",

    "Signals today",



    # --------------------------------------------------------
    # Scanner Ranking / Alpha
    # --------------------------------------------------------

    "Rank",

    "Exp/DAY%",

    "RS%",



    # --------------------------------------------------------
    # Trade Management
    # --------------------------------------------------------

    "Target #",

    "Target %",

    "Stop #",

    "Stop %",

    "Trail #",

    "Trail %",



    # --------------------------------------------------------
    # Trade Statistics
    # --------------------------------------------------------

    "Trades",

    "Seq. trades",

    "Win%",



    # --------------------------------------------------------
    # Return Quality
    # --------------------------------------------------------

    "Expectancy%",

    "Avg win%",

    "Avg loss%",



    # --------------------------------------------------------
    # Efficiency
    # --------------------------------------------------------

    "R:R",

    "Avg days",



    # --------------------------------------------------------
    # Performance
    # --------------------------------------------------------

    "Total return (sum)%",

    "CAGR%",



    # --------------------------------------------------------
    # Risk
    # --------------------------------------------------------

    "Max DD%",

    "Profit factor",

    "Recovery factor",

    "Max consec. losses",



    # --------------------------------------------------------
    # Backtest Validity
    # --------------------------------------------------------

    "BT from",

    "BT to",

    "Years",

)



# ============================================================
# INSTITUTIONAL GENERATED COLUMNS
# ============================================================

INSTITUTIONAL_COLUMNS: tuple[str, ...] = (

    # --------------------------------------------------------
    # Conviction Engine
    # --------------------------------------------------------

    "Confidence",

    "Rank Score",



    # --------------------------------------------------------
    # Institutional Scoring
    # --------------------------------------------------------

    "Alpha Score",

    "Profitability Score",

    "Risk Score",

    "Robustness Score",

    "Efficiency Score",

    "Institutional Score",



    # --------------------------------------------------------
    # Governance
    # --------------------------------------------------------

    "Institutional Eligible",

    "Governance Flags",



    # --------------------------------------------------------
    # Ranking / Decision
    # --------------------------------------------------------

    "Institutional Rank",

    "Institutional Priority Score",

    "Institutional Rating",

    "Institutional Decision",

)



# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

#
# Existing modules may import REQUIRED_COLUMNS.
#
# Keep this alias until all imports are migrated.
#

REQUIRED_COLUMNS: tuple[str, ...] = (

    RAW_SCANNER_COLUMNS

)



# ============================================================
# NUMERIC NORMALIZATION COLUMNS
# ============================================================

NUMERIC_COLUMNS: tuple[str, ...] = (

    "Rank",

    "Exp/DAY%",


    "RS%",


    "Target #",

    "Target %",

    "Stop #",

    "Stop %",

    "Trail #",

    "Trail %",


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