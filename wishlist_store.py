"""
wishlist_store.py — WISHLIST v2 STORAGE LAYER
=============================================
Central Excel-backed store for the wishlist / tracker workflow.

The user's design:
  Sheet 1 · signaled_today  — auto-appended by the daily scanner after each
                              run; every stock that fired a technical signal
                              tonight, with full parameter snapshot.
  Sheet 2 · positive_news    — auto-appended by the daily scanner; stocks that
                              did NOT signal but carried positive news
                              (news_score ≥ 0.15).
  Sheet 3 · top_movers       — MANUAL entry by the user (top Nifty 500 movers
                              they want the algorithm compared against).

Corresponding analysis workbook (wishlist_observations.xlsx) is produced by
`wishlist_app.py`, one analysis sheet per input sheet.

All elapsed / remaining timings in this module are computed as WORKING DAYS
(numpy busday_count — weekdays only; NSE holidays not explicitly modelled).

Public API
----------
    initialize_workbook()                       — ensure wishlist.xlsx exists
    append_signaled(rows: list[dict])           — Sheet 1 auto-append
    append_positive_news(rows: list[dict])      — Sheet 2 auto-append
    read_sheet(sheet_name)  -> DataFrame        — read one sheet
    read_all_sheets()       -> dict[str, DataFrame]
    write_observations(analyses: dict[str, DataFrame])
    working_days_between(d1, d2) -> int
"""

import os
import time
import datetime as dt
import numpy as np
import pandas as pd


class WorkbookLockedError(RuntimeError):
    """Raised when wishlist.xlsx can't be replaced because another process
    holds the destination handle open — typically Excel is viewing the file,
    or an antivirus / Windows Search indexer briefly locked it. Caller
    should surface a clear "close Excel and retry" message to the user
    instead of crashing."""
    pass

_HERE = os.path.dirname(os.path.abspath(__file__))

WISHLIST_XLSX = os.path.join(_HERE, "wishlist.xlsx")
OBS_XLSX      = os.path.join(_HERE, "wishlist_observations.xlsx")

# --------------------------------------------------------------------------
# Sheet names — kept short so tabs render cleanly in Excel / Streamlit
# --------------------------------------------------------------------------
SHEET_SIGNALED = "signaled_today"
SHEET_NEWS     = "positive_news"
SHEET_MOVERS   = "top_movers"

# --------------------------------------------------------------------------
# Column schemas per input sheet.
# Order matters — Excel column order is preserved from this list.
# --------------------------------------------------------------------------
SIGNALED_COLS = [
    "observation_date",    # date the scanner ran (append time)
    "signal_date",         # bar the technical signal fired on
    "ticker",
    "category",            # SEBI cap tier — LargeCap / MidCap / SmallCap
    "sector",
    "strategy",            # PASS_combined / PASS_recommended / etc.
    "regime_at_signal",    # composite regime label at time of scan
    "trade_type",          # UPTREND / DOWNTREND (from engine.generate_signals)
    "status",              # KEPT / RS_LAGGARD / SECTOR_CAPPED / EVENT_BLOCKED
    "why",                 # human-readable status reason
    # --- pricing plan (executable) ---
    "signal_price",        # cutoff close on signal day
    "buy_limit",           # target BUY LIMIT (or NaN for market-open entry)
    "target_price",
    "stop_price",
    "stop_pct",
    "expected_days_to_target",
    # --- ranking + evidence ---
    "rank_score",
    "stage2_score",
    "confidence",
    "rel_strength",
    "news_score",
    "news_top_headline",
    "rank_penalty",
    # v4 (Aug-2026 evidence-driven) — anti-crowding audit
    "crowding_score",           # 0..100 (higher = more crowded, worse for entry)
    "anti_crowding_mult",       # 0.70..1.00 — the multiplier applied to rank_score
    "crowding_reason",          # human-readable breakdown
    # --- risk / volatility ---
    "atr_pct",
    # --- historical evidence (sequential trades) ---
    "hist_seq_trades",
    "hist_seq_win_pct",
    "hist_seq_expectancy_pct",
    "hist_seq_exp_per_day_pct",
    "hist_total_return_sum_pct",
    "hist_cagr_pct",
    "hist_max_dd_pct",
    # --- entry mode audit (Limit / Market) ---
    "entry_mode",
    "limit_pct",
]

POSITIVE_NEWS_COLS = [
    "observation_date",
    "ticker",
    "category",
    "sector",
    "news_score",
    "n_articles",
    "news_top_headline",
    "news_top_date",
    "news_latest_headline",
    "news_latest_date",
    "news_matched_terms",
    "signal_price",        # last close on obs date (assumed next-day open buy)
    "rel_strength",
    "atr_pct",
    "rank_score",          # informational — was a rank_score even computed?
    "signals_today",       # False by definition (this sheet is non-signal)
    # NEW columns to make Sheet-2 analysis meaningful (Aug-2026 v2 addition)
    "signal_reject_reason",   # WHY this stock didn't fire a signal (regime, extension, funda etc.)
    "reject_category",        # short bucket: "extension" | "regime" | "no_signal" | "funda" | "unknown"
]

TOP_MOVERS_COLS = [
    "observation_date",   # date the user observed the move
    "ticker",
    "pct_change",         # optional — user can fill; tracker recomputes if blank
    "notes",              # free-form ("India Q1 GDP beat", etc.)
]

# --------------------------------------------------------------------------
# Observation-sheet schemas (produced by wishlist_app.py)
# --------------------------------------------------------------------------
OBS_SIGNALED_COLS = [
    "observation_date", "ticker", "signal_date",
    "working_days_elapsed", "working_days_remaining",
    "buy_limit", "was_limit_hit", "entry_actual_price", "entry_actual_date",
    # --- v4 (Aug-2026): rich next-session executability audit ---
    # Answers the user's "we may lose the stock even if it's rising" question:
    # shows exactly how the stock opened vs the limit, whether the intraday
    # low ever touched the limit, and how much of the move we forfeited by
    # not chasing.
    "next_session_open",              # first post-signal open price
    "next_session_high",              # first post-signal high
    "next_session_low",               # first post-signal low
    "next_session_close",             # first post-signal close
    "open_gap_vs_limit_pct",          # +ve = opened ABOVE limit (missed the fill)
    "intraday_low_vs_limit_pct",      # closest the stock got to the limit intraday
    "opportunity_cost_pct",           # curr_price vs limit — what we forfeited
    # --- unchanged snapshot columns ---
    "signal_price", "current_price", "peak_price_since_signal",
    "current_pnl_pct", "peak_pnl_pct",
    "target_price", "distance_to_target_pct",
    "stop_price", "distance_to_stop_pct",
    "expected_days_to_target",
    "rank_score", "category", "sector", "status_at_signal",
    "verdict", "note",
]
OBS_NEWS_COLS = [
    "observation_date", "ticker", "signal_date",
    "working_days_elapsed",
    "buy_at_open_price", "buy_at_open_date",
    "signal_price", "current_price",
    "current_pnl_pct", "peak_pnl_pct",
    "news_score", "news_top_headline",
    "signal_reject_reason", "reject_category",
    "verdict", "note",
]
OBS_MOVERS_COLS = [
    "observation_date", "ticker",
    "pct_change_that_day",   # actual day-of move
    "current_price",
    "in_signaled_sheet",     # Y/N — did this ticker appear in Sheet 1 that day?
    "signaled_status",       # if Y, what status (KEPT/RS_LAGGARD/...)
    "in_news_sheet",         # Y/N — did this ticker appear in Sheet 2 that day?
    "news_score_that_day",
    "reason_recognized_or_missed",
    "user_notes",
]


# ======================================================================
#  WORKING-DAYS UTILITY
# ======================================================================
def _to_date(x):
    """Coerce str / pandas Timestamp / date / datetime → datetime.date."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    if isinstance(x, dt.datetime):
        return x.date()
    if isinstance(x, dt.date):
        return x
    if isinstance(x, pd.Timestamp):
        return x.to_pydatetime().date()
    if isinstance(x, str):
        try:
            return dt.date.fromisoformat(x[:10])
        except Exception:
            try:
                return pd.to_datetime(x).date()
            except Exception:
                return None
    return None


def working_days_between(d1, d2) -> int:
    """Number of full weekday sessions (Mon-Fri) STRICTLY between d1 (exclusive)
    and d2 (inclusive). If d2 < d1, returns 0 (never negative).

    NSE holidays are not explicitly modelled here — user asked for "working
    days only" which we interpret as weekdays. If holiday-precision matters
    later, wire in a holiday calendar via numpy.busdaycalendar."""
    d1 = _to_date(d1)
    d2 = _to_date(d2)
    if d1 is None or d2 is None:
        return 0
    if d2 < d1:
        return 0
    # busday_count is [start, end) — half-open. Adding a day makes it inclusive
    # of d2 while excluding d1 (signal day itself doesn't count as elapsed).
    try:
        return int(np.busday_count(d1, d2 + dt.timedelta(days=1))) - 1
    except Exception:
        # Fallback if numpy datatypes trip on very old dates
        n = 0
        cur = d1 + dt.timedelta(days=1)
        while cur <= d2:
            if cur.weekday() < 5:
                n += 1
            cur += dt.timedelta(days=1)
        return n


def add_working_days(start_date, n_working_days: int) -> dt.date:
    """Return the date that is `n_working_days` weekdays after `start_date`."""
    d = _to_date(start_date)
    if d is None:
        return None
    added = 0
    cur = d
    while added < n_working_days:
        cur += dt.timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


# ======================================================================
#  WORKBOOK INIT / READ / WRITE
# ======================================================================
_SHEET_SCHEMAS = {
    SHEET_SIGNALED: SIGNALED_COLS,
    SHEET_NEWS:     POSITIVE_NEWS_COLS,
    SHEET_MOVERS:   TOP_MOVERS_COLS,
}


def initialize_workbook(path: str = WISHLIST_XLSX,
                        overwrite: bool = False) -> bool:
    """Create an empty wishlist.xlsx with three schema-conformant sheets.

    Returns True if the file was (re)created, False if it already existed and
    overwrite=False. Never raises — errors are swallowed so scanner start-up
    is never blocked by a permission blip on a locked Excel file.
    """
    if os.path.exists(path) and not overwrite:
        return False
    try:
        with pd.ExcelWriter(path, engine="openpyxl", mode="w") as w:
            for sheet, cols in _SHEET_SCHEMAS.items():
                pd.DataFrame(columns=cols).to_excel(w, sheet_name=sheet, index=False)
        return True
    except Exception:
        return False


def _ensure_workbook_exists() -> None:
    """Called before every read/append so a missing workbook self-heals."""
    if not os.path.exists(WISHLIST_XLSX):
        initialize_workbook(WISHLIST_XLSX, overwrite=False)


def read_sheet(sheet_name: str) -> pd.DataFrame:
    """Read one sheet as a DataFrame. Returns an EMPTY frame with the correct
    column schema if the sheet is missing or the workbook doesn't exist yet."""
    schema = _SHEET_SCHEMAS.get(sheet_name)
    if schema is None:
        return pd.DataFrame()
    _ensure_workbook_exists()
    try:
        df = pd.read_excel(WISHLIST_XLSX, sheet_name=sheet_name,
                           engine="openpyxl")
    except Exception:
        return pd.DataFrame(columns=schema)
    # Add missing columns (schema evolution across versions)
    for c in schema:
        if c not in df.columns:
            df[c] = pd.NA
    return df[schema].copy()


def read_all_sheets() -> dict:
    """Return {sheet_name: DataFrame} for every input sheet."""
    return {name: read_sheet(name) for name in _SHEET_SCHEMAS}


def _atomic_replace_with_retry(src: str, dst: str,
                                 retries: int = 5, delay: float = 0.3) -> None:
    """os.replace with Windows-friendly retry. Excel / antivirus / Search
    indexer can hold a brief exclusive lock on the destination — retry a
    handful of times before giving up so a transient lock isn't fatal."""
    last_err = None
    for _ in range(max(1, retries)):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:
            last_err = e
            time.sleep(delay)
        except OSError as e:
            last_err = e
            time.sleep(delay)
    # If we get here, the destination stayed locked. Surface a clean error
    # so the caller can present "close Excel and re-run".
    raise WorkbookLockedError(
        f"Could not replace `{dst}`: the file is held open by another "
        f"process (Excel viewer, Windows preview pane, antivirus, "
        f"file-indexer). Close any program that has it open and retry. "
        f"Underlying error: {last_err!r}"
    )


def _write_all_sheets(sheets: dict) -> None:
    """Atomically rewrite the workbook with all three sheets."""
    # pandas' ExcelWriter validates the extension against the engine, so the
    # tmp file MUST end in .xlsx (a bare .tmp trips ValueError). We insert
    # ".tmp" into the stem instead — same atomicity guarantee via os.replace.
    tmp = WISHLIST_XLSX.replace(".xlsx", ".tmp.xlsx")
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl", mode="w") as w:
            for name, cols in _SHEET_SCHEMAS.items():
                df = sheets.get(name, pd.DataFrame(columns=cols))
                # Re-order columns to schema; add missing as empty
                for c in cols:
                    if c not in df.columns:
                        df[c] = pd.NA
                df = df[cols]
                df.to_excel(w, sheet_name=name, index=False)
        _atomic_replace_with_retry(tmp, WISHLIST_XLSX)
    except WorkbookLockedError:
        # Clean the orphaned tmp so it doesn't accumulate on repeated locks
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise


def _append_rows(sheet_name: str, rows: list) -> int:
    """Append rows to `sheet_name`, deduplicated by (observation_date, ticker).
    Returns the number of net-new rows persisted."""
    if not rows:
        return 0
    cols = _SHEET_SCHEMAS[sheet_name]
    new_df = pd.DataFrame(rows)
    # Coerce every schema column to exist so concat aligns cleanly
    for c in cols:
        if c not in new_df.columns:
            new_df[c] = pd.NA
    new_df = new_df[cols].copy()

    all_sheets = read_all_sheets()
    existing = all_sheets.get(sheet_name, pd.DataFrame(columns=cols))
    combined = pd.concat([existing, new_df], ignore_index=True)
    # v3 (Aug-2026): observation_date now carries date+time. Dedup on the
    # DATE portion only (so multi-runs same day collapse), but keep the
    # ORIGINAL datetime in the persisted column so Excel shows the timestamp.
    if "observation_date" in combined.columns and "ticker" in combined.columns:
        _dedup_key = pd.to_datetime(
            combined["observation_date"], errors="coerce").dt.date
        combined = combined.assign(_dedup_date=_dedup_key)
        combined = combined.drop_duplicates(
            subset=["_dedup_date", "ticker"], keep="last"
        ).drop(columns=["_dedup_date"]).reset_index(drop=True)

    added = max(0, len(combined) - len(existing))
    all_sheets[sheet_name] = combined
    _write_all_sheets(all_sheets)
    return added


def append_signaled(rows: list) -> int:
    """Public API — append signalled-today rows to Sheet 1."""
    return _append_rows(SHEET_SIGNALED, rows)


def append_positive_news(rows: list) -> int:
    """Public API — append positive-news (non-signalling) rows to Sheet 2."""
    return _append_rows(SHEET_NEWS, rows)


# ======================================================================
#  OBSERVATIONS OUTPUT
# ======================================================================
_OBS_SCHEMAS = {
    "signaled_analysis":      OBS_SIGNALED_COLS,
    "positive_news_analysis": OBS_NEWS_COLS,
    "top_movers_analysis":    OBS_MOVERS_COLS,
}


def _read_obs_sheet(sheet_name: str) -> pd.DataFrame:
    """Read one observation sheet, returning empty schema-conformant DF if
    the file / sheet is missing (fresh install case)."""
    schema = _OBS_SCHEMAS.get(sheet_name, [])
    if not os.path.exists(OBS_XLSX):
        return pd.DataFrame(columns=schema)
    try:
        df = pd.read_excel(OBS_XLSX, sheet_name=sheet_name, engine="openpyxl")
    except Exception:
        return pd.DataFrame(columns=schema)
    for c in schema:
        if c not in df.columns:
            df[c] = pd.NA
    return df[schema].copy() if schema else df


def write_observations(analyses: dict) -> None:
    """APPEND day-wise analyses to wishlist_observations.xlsx.

    v3 (Aug-2026 — user rule "record observation day wise"): each analysis
    run APPENDS a fresh row per (ticker, signal_date, observation_date)
    rather than overwriting the workbook. Running the tracker daily builds
    a proper time-series of how each signal evolved.

    Dedup keys (per sheet):
      * signaled_analysis      → (observation_date, ticker, signal_date)
      * positive_news_analysis → (observation_date, ticker, signal_date)
      * top_movers_analysis    → (observation_date, ticker)

    `analyses` maps observation-sheet name → DataFrame of TODAY's snapshot.
    Missing sheets are written as empty (with headers) so downstream
    consumers can rely on all three tabs existing.
    """
    # Load existing history and concat new snapshots.
    _dedup_keys = {
        "signaled_analysis":      ["observation_date", "ticker", "signal_date"],
        "positive_news_analysis": ["observation_date", "ticker", "signal_date"],
        "top_movers_analysis":    ["observation_date", "ticker"],
    }
    merged = {}
    for name, cols in _OBS_SCHEMAS.items():
        existing = _read_obs_sheet(name)
        new_df   = analyses.get(name, pd.DataFrame(columns=cols)).copy()
        for c in cols:
            if c not in new_df.columns:
                new_df[c] = pd.NA
        new_df = new_df[cols]
        if not existing.empty:
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = new_df
        # v4 (Aug-2026 — BUG FIX): the previous version coerced every dedup
        # key column to a date via pd.to_datetime, which nuked STRING columns
        # like `ticker` (all became NaN, then dedup collapsed 212 rows to 1
        # nan-ticker row). Now:
        #   * DATE columns → coerced to python date via a temp column and used
        #     as dedup key (original datetime stays intact in the sheet).
        #   * STRING columns (like ticker) → normalised to upper-case in a temp
        #     column and used as dedup key (original string stays intact).
        _DATE_COLS = {"observation_date", "signal_date"}
        _dedup_temp_cols = []
        for _dc in _dedup_keys[name]:
            if _dc not in combined.columns:
                continue
            _tmp = f"_dedup_{_dc}"
            if _dc in _DATE_COLS:
                combined[_tmp] = pd.to_datetime(
                    combined[_dc], errors="coerce").dt.date
            else:
                combined[_tmp] = combined[_dc].astype(str).str.upper().str.strip()
            _dedup_temp_cols.append(_tmp)
        if _dedup_temp_cols:
            combined = combined.drop_duplicates(subset=_dedup_temp_cols, keep="last")
            combined = combined.drop(columns=_dedup_temp_cols, errors="ignore")
        merged[name] = combined.reset_index(drop=True)
    # Same .xlsx-extension trick as _write_all_sheets — see comment there.
    tmp = OBS_XLSX.replace(".xlsx", ".tmp.xlsx")
    try:
        with pd.ExcelWriter(tmp, engine="openpyxl", mode="w") as w:
            for name, cols in _OBS_SCHEMAS.items():
                df = merged.get(name, pd.DataFrame(columns=cols))  # v3: from merged, not analyses
                for c in cols:
                    if c not in df.columns:
                        df[c] = pd.NA
                df = df[cols]
                df.to_excel(w, sheet_name=name, index=False)
        # Use the same retry-aware replace so a briefly-locked observations
        # file (e.g. Excel viewer left open) doesn't crash the analysis.
        _obs_replace_target = OBS_XLSX
        for _ in range(5):
            try:
                os.replace(tmp, _obs_replace_target)
                break
            except PermissionError:
                time.sleep(0.3)
        else:
            raise WorkbookLockedError(
                f"Could not replace `{_obs_replace_target}` — close it in "
                f"Excel and re-run the analysis.")
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise


# ======================================================================
#  Convenience: quick summary of what's already in the workbook
# ======================================================================
def workbook_summary() -> dict:
    """Return {sheet: n_rows} for the Streamlit sidebar / caption."""
    out = {}
    for name in _SHEET_SCHEMAS:
        try:
            out[name] = len(read_sheet(name))
        except Exception:
            out[name] = 0
    return out


# ======================================================================
#  SUSTAINED-RANK RECURRENCE  (Aug-2026 evidence-driven addition)
# ======================================================================
def recent_top_pick_counts(days_lookback: int = 10) -> dict:
    """Return {ticker: n_appearances_in_signaled_sheet_over_last_N_trading_days}.

    Data from the 42-day Nifty-500 walk-forward showed:
      * 1-day rank pick        → +5.84% mean PnL, 76% win  (n=25, 4+ days)
      * 4+ day recurring pick  → -1.78% mean PnL, 29% win  (n=35, 1 day only)
    A 3× win-rate delta. Multi-day recurrence is the strongest single
    signal in the dataset. Callers use this dict to compute a
    sustained-rank multiplier boosting rank_score for tickers the
    scanner has repeatedly identified.
    """
    df = read_sheet(SHEET_SIGNALED)
    if df.empty or "observation_date" not in df.columns:
        return {}
    obs = pd.to_datetime(df["observation_date"], errors="coerce").dt.date
    if obs.isna().all():
        return {}
    today = dt.date.today()
    cutoff = today - dt.timedelta(days=int(days_lookback * 1.5) + 2)   # ≈ N business days
    mask = obs >= cutoff
    recent = df[mask].copy()
    if recent.empty:
        return {}
    # KEPT-only counts (SECTOR_CAPPED / RS_LAGGARD are not "picks")
    if "status" in recent.columns:
        recent = recent[recent["status"] == "KEPT"]
    counts = (recent.groupby("ticker")["observation_date"]
              .apply(lambda s: s.astype(str).nunique()).to_dict())
    return {str(k).upper(): int(v) for k, v in counts.items()}


def sustained_rank_multiplier(n_days: int) -> float:
    """Convert recurrence count → multiplier applied to rank_score.
    Evidence-calibrated (42-day walk-forward, Nifty 500):
       4+ days → ×1.20  (76% win rate, +5.8% mean PnL)
       3 days  → ×1.15  (57% win, +4.0%)
       2 days  → ×1.10  (61% win, +4.8%)
       1 day   → ×1.00  (baseline)
    """
    if n_days >= 4:  return 1.20
    if n_days == 3:  return 1.15
    if n_days == 2:  return 1.10
    return 1.00


if __name__ == "__main__":
    # Smoke test — safe to run directly
    ok = initialize_workbook()
    print(f"initialize_workbook -> {ok}")
    print(f"summary: {workbook_summary()}")
    print(f"working_days_between(2026-08-24, 2026-08-31) = "
          f"{working_days_between(dt.date(2026,8,24), dt.date(2026,8,31))}")
