"""
wishlist_app.py — WISHLIST TRACKER v2  (Aug-2026 rewrite)
=========================================================
Reads the Excel workbook that the daily scanner auto-populates
(`wishlist.xlsx`, three sheets) and produces per-sheet analysis outputs
that are:
  * displayed in Streamlit tabs
  * persisted to `wishlist_observations.xlsx` (three matching sheets)

Sheet 1 — signaled_today
  - Was the buy-limit hit within the fill window? (fill-rate check)
  - Current PnL / peak PnL, targeting the algorithm's stated objective
  - Did the stock reach its expected days-to-target on schedule?
  - Aggregate: does higher rank_score correlate with higher realised PnL?

Sheet 2 — positive_news (no signal, but news_score ≥ 0.15)
  - Assumes market-at-open buy the NEXT trading session after obs date
  - Tracks working-day PnL evolution
  - Verdict buckets: WORKING / STALLED / FAILED

Sheet 3 — top_movers (user manual entry)
  - % change on the observation date
  - Was the ticker in the signalled sheet that day? in positive-news sheet?
  - If in NEITHER, why the algorithm missed it (best-effort reason lookup)

All elapsed timings are counted in WORKING DAYS (numpy.busday_count).
The observations workbook is refreshed on every run — no CSV drift.
"""
import os
import io
import time
import importlib.util
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

# ---------------- Shared engine + store ----------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE_PATH = os.path.join(_HERE, "swing_screener_app.py")
_spec = importlib.util.spec_from_file_location("engine", _ENGINE_PATH)
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)

import wishlist_store as store
from wishlist_store import (
    WISHLIST_XLSX, OBS_XLSX,
    SHEET_SIGNALED, SHEET_NEWS, SHEET_MOVERS,
    working_days_between, add_working_days, initialize_workbook,
)


# ============================================================================
#  PRICE FETCHER  (unadjusted current + auto-adjusted history for TA)
# ============================================================================
@st.cache_data(ttl=15 * 60, show_spinner=False)
def _fetch_history(ticker_yahoo: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame()
    try:
        df = yf.Ticker(ticker_yahoo).history(start=start, end=end,
                                              interval="1d", auto_adjust=True)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.dropna()


def _to_yahoo(sym: str) -> str:
    s = str(sym).strip().upper()
    return s if s.endswith((".NS", ".BO")) else s + ".NS"


def _safe_date(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


# ============================================================================
#  ANALYSIS 1 — SIGNALED_TODAY
# ============================================================================
def analyze_signaled(sig_df: pd.DataFrame, obs_run_date: dt.date) -> pd.DataFrame:
    """One row per (observation_date, ticker) — with per-day evolution
    computed from that entry's signal_date forward using the LATEST price
    available at analysis time."""
    if sig_df.empty:
        return pd.DataFrame(columns=[
            "observation_date", "ticker", "signal_date",
            "working_days_elapsed", "working_days_remaining",
            "buy_limit", "was_limit_hit", "entry_actual_price", "entry_actual_date",
            "signal_price", "current_price", "peak_price_since_signal",
            "current_pnl_pct", "peak_pnl_pct",
            "target_price", "distance_to_target_pct",
            "stop_price", "distance_to_stop_pct",
            "expected_days_to_target",
            "rank_score", "category", "sector", "status_at_signal",
            "verdict", "note",
        ])

    out_rows = []
    prog = st.progress(0.0)
    total = len(sig_df)
    for i, (_, r) in enumerate(sig_df.iterrows()):
        prog.progress((i + 1) / total)
        ticker      = str(r["ticker"]).upper()
        sig_date    = _safe_date(r["signal_date"])
        obs_date    = _safe_date(r["observation_date"])
        if sig_date is None or obs_date is None:
            continue
        buy_limit   = float(r["buy_limit"])    if pd.notna(r.get("buy_limit"))    else np.nan
        target_p    = float(r["target_price"]) if pd.notna(r.get("target_price")) else np.nan
        stop_p      = float(r["stop_price"])   if pd.notna(r.get("stop_price"))   else np.nan
        signal_p    = float(r["signal_price"]) if pd.notna(r.get("signal_price")) else np.nan
        exp_days_s  = str(r.get("expected_days_to_target", "") or "")
        # Extract leading digits from strings like "10d" or "8d ⚠ thin"
        try:
            exp_days = int("".join(ch for ch in exp_days_s if ch.isdigit()) or "0")
        except Exception:
            exp_days = 0

        # Fetch history from signal date to today
        ty = _to_yahoo(ticker)
        hist = _fetch_history(ty, sig_date - dt.timedelta(days=3),
                              obs_run_date + dt.timedelta(days=2))
        if hist.empty:
            out_rows.append(_row_signal_no_data(r, obs_run_date, sig_date))
            continue
        # Post-signal path only (strict > sig_date). Signal-day bar itself is
        # the ENTRY-INTENT bar; fills happen next session onwards.
        post = hist[hist.index.date > sig_date]

        # ---------- LIMIT-FILL DETECTION ----------
        was_hit, fill_price, fill_date = _check_limit_fill(post, buy_limit,
                                                          fill_days=int(r.get("limit_pct", 1) or 1) or 1,
                                                          r_entry_mode=str(r.get("entry_mode", "Market open")))
        if was_hit is None:
            was_hit_lbl = "Pending"
        elif was_hit:
            was_hit_lbl = "Yes"
        else:
            was_hit_lbl = "No"

        # ---------- v4 (Aug-2026): NEXT-SESSION AUDIT ----------
        # Snapshot the FIRST post-signal session's OHLC so the user can see
        # exactly how the stock opened vs the buy_limit. Answers "did we lose
        # the stock even though it rose?" — if open > limit AND intraday_low
        # > limit, the limit never had a chance to fill; if the stock kept
        # rising after, opportunity_cost_pct quantifies the forfeited move.
        next_open = next_high = next_low = next_close = np.nan
        open_gap_pct = intraday_low_gap_pct = opportunity_cost_pct = np.nan
        if not post.empty:
            _p0 = post.iloc[0]
            next_open  = float(_p0["Open"])
            next_high  = float(_p0["High"])
            next_low   = float(_p0["Low"])
            next_close = float(_p0["Close"])
            if pd.notna(buy_limit) and buy_limit > 0:
                open_gap_pct         = (next_open / buy_limit - 1) * 100
                intraday_low_gap_pct = (next_low  / buy_limit - 1) * 100
                opportunity_cost_pct = ((curr_price if False else float(post["Close"].iloc[-1]))
                                        / buy_limit - 1) * 100

        # ---------- CURRENT / PEAK ----------
        curr_price = float(post["Close"].iloc[-1]) if not post.empty else float(hist["Close"].iloc[-1])
        peak_price = float(post["High"].max())     if not post.empty else np.nan
        # Now that curr_price is finalised, refresh opportunity_cost using it
        if not post.empty and pd.notna(buy_limit) and buy_limit > 0 and np.isfinite(curr_price):
            opportunity_cost_pct = (curr_price / buy_limit - 1) * 100

        # ---------- EFFECTIVE ENTRY  (v3 — user rule: always monitor) ----------
        # If Limit was hit → use actual fill price. If Limit was NOT hit → per
        # user rule "consider market price as buy price and monitor the stock":
        # fall back to the first post-signal open. Market entries always use
        # the first post-signal open.
        entry_source = "market"
        if pd.notna(fill_price):
            entry_effective = fill_price
            entry_source = "limit_hit"
        elif not post.empty:
            entry_effective = float(post["Open"].iloc[0])
            fill_date = fill_date or post.index[0].date()   # for display
            if str(r.get("entry_mode", "Market open")) == "Limit" and was_hit is False:
                entry_source = "market_fallback"   # limit skipped, monitoring anyway
        else:
            entry_effective = signal_p
            entry_source = "signal_close"

        curr_pnl_pct = (curr_price / entry_effective - 1) * 100 if entry_effective else np.nan
        peak_pnl_pct = (peak_price / entry_effective - 1) * 100 if (entry_effective and pd.notna(peak_price)) else np.nan
        dist_target_pct = (target_p / curr_price - 1) * 100 if (curr_price and pd.notna(target_p)) else np.nan
        dist_stop_pct   = (stop_p   / curr_price - 1) * 100 if (curr_price and pd.notna(stop_p))   else np.nan

        # ---------- WORKING-DAYS ELAPSED / REMAINING ----------
        wd_elapsed = working_days_between(sig_date, obs_run_date)
        wd_remain  = max(0, int(exp_days) - int(wd_elapsed))

        # ---------- VERDICT ----------
        verdict, note = _verdict_signaled(
            curr_price=curr_price, peak_price=peak_price,
            entry_effective=entry_effective,
            target_price=target_p, stop_price=stop_p,
            wd_elapsed=wd_elapsed, exp_days=exp_days,
            was_hit=was_hit, entry_mode=str(r.get("entry_mode", "Market open")),
            entry_source=entry_source,
        )
        if entry_source == "market_fallback":
            # v4 (Aug-2026): explicit "why the limit missed" prefix so the
            # user can see whether the stock gapped above and never returned,
            # and how much of the move was forfeited.
            _open_txt = (f"opened at ₹{next_open:.2f} "
                         f"({open_gap_pct:+.1f}% vs limit ₹{buy_limit:.2f})"
                         if pd.notna(next_open) and pd.notna(buy_limit) else "")
            _low_txt  = (f", intraday low ₹{next_low:.2f} "
                         f"({intraday_low_gap_pct:+.1f}% vs limit)"
                         if pd.notna(next_low) and pd.notna(intraday_low_gap_pct)
                         else "")
            _opp_txt  = (f", opportunity-cost {opportunity_cost_pct:+.1f}% "
                         f"(current ₹{curr_price:.2f} vs limit)"
                         if pd.notna(opportunity_cost_pct) else "")
            note = (f"[Limit NEVER filled — {_open_txt}{_low_txt}{_opp_txt}. "
                    f"Monitoring at market fallback.] ") + note
            # Escalate verdict when the limit was missed but the stock is up
            # meaningfully: user's exact scenario ("stock rising but we lost it").
            if (pd.notna(opportunity_cost_pct) and opportunity_cost_pct >= 2.0
                    and verdict in ("ON_TRACK", "AHEAD_OF_PACE", "BEHIND_PACE")):
                verdict = "MISSED_LIMIT_STOCK_ROSE"

        out_rows.append({
            "observation_date":     obs_run_date,
            "ticker":               ticker,
            "signal_date":          sig_date,
            "working_days_elapsed": int(wd_elapsed),
            "working_days_remaining": int(wd_remain),
            "buy_limit":            round(buy_limit, 2) if pd.notna(buy_limit) else None,
            "was_limit_hit":        was_hit_lbl,
            "entry_actual_price":   round(fill_price, 2) if pd.notna(fill_price) else None,
            "entry_actual_date":    fill_date,
            # v4 (Aug-2026) — next-session executability audit
            "next_session_open":       round(next_open,  2) if pd.notna(next_open)  else None,
            "next_session_high":       round(next_high,  2) if pd.notna(next_high)  else None,
            "next_session_low":        round(next_low,   2) if pd.notna(next_low)   else None,
            "next_session_close":      round(next_close, 2) if pd.notna(next_close) else None,
            "open_gap_vs_limit_pct":   round(open_gap_pct, 2)         if pd.notna(open_gap_pct)         else None,
            "intraday_low_vs_limit_pct": round(intraday_low_gap_pct, 2) if pd.notna(intraday_low_gap_pct) else None,
            "opportunity_cost_pct":    round(opportunity_cost_pct, 2) if pd.notna(opportunity_cost_pct) else None,
            "signal_price":         round(signal_p, 2) if pd.notna(signal_p) else None,
            "current_price":        round(curr_price, 2) if pd.notna(curr_price) else None,
            "peak_price_since_signal": round(peak_price, 2) if pd.notna(peak_price) else None,
            "current_pnl_pct":      round(curr_pnl_pct, 2) if pd.notna(curr_pnl_pct) else None,
            "peak_pnl_pct":         round(peak_pnl_pct, 2) if pd.notna(peak_pnl_pct) else None,
            "target_price":         round(target_p, 2) if pd.notna(target_p) else None,
            "distance_to_target_pct": round(dist_target_pct, 2) if pd.notna(dist_target_pct) else None,
            "stop_price":           round(stop_p, 2) if pd.notna(stop_p) else None,
            "distance_to_stop_pct": round(dist_stop_pct, 2) if pd.notna(dist_stop_pct) else None,
            "expected_days_to_target": int(exp_days) if exp_days else None,
            "rank_score":           float(r.get("rank_score")) if pd.notna(r.get("rank_score")) else None,
            "category":             r.get("category"),
            "sector":               r.get("sector"),
            "status_at_signal":     r.get("status"),
            "verdict":              verdict,
            "note":                 note,
        })
    prog.empty()
    return pd.DataFrame(out_rows)


def _row_signal_no_data(r, obs_run_date, sig_date):
    return {
        "observation_date":     obs_run_date,
        "ticker":               str(r["ticker"]).upper(),
        "signal_date":          sig_date,
        "working_days_elapsed": working_days_between(sig_date, obs_run_date),
        "working_days_remaining": None,
        "buy_limit":            None,
        "was_limit_hit":        "no data",
        "entry_actual_price":   None,
        "entry_actual_date":    None,
        "next_session_open":    None,
        "next_session_high":    None,
        "next_session_low":     None,
        "next_session_close":   None,
        "open_gap_vs_limit_pct": None,
        "intraday_low_vs_limit_pct": None,
        "opportunity_cost_pct": None,
        "signal_price":         None,
        "current_price":        None,
        "peak_price_since_signal": None,
        "current_pnl_pct":      None,
        "peak_pnl_pct":         None,
        "target_price":         None,
        "distance_to_target_pct": None,
        "stop_price":           None,
        "distance_to_stop_pct": None,
        "expected_days_to_target": None,
        "rank_score":           None,
        "category":             r.get("category"),
        "sector":               r.get("sector"),
        "status_at_signal":     r.get("status"),
        "verdict":              "NO_DATA",
        "note":                 "yfinance history unavailable",
    }


def _check_limit_fill(post_df: pd.DataFrame, buy_limit: float,
                      fill_days: int = 1, r_entry_mode: str = "Market open"):
    """Return (was_hit, fill_price, fill_date).
    was_hit: True/False/None (None if we can't tell — insufficient forward data)
    For Market-open trades, "was_hit" is trivially True; entry is next-day open.
    """
    if r_entry_mode != "Limit" or (buy_limit is None) or not np.isfinite(buy_limit):
        # Market entry — first post-signal open IS the fill
        if post_df.empty:
            return None, np.nan, None
        return True, float(post_df["Open"].iloc[0]), post_df.index[0].date()
    # Limit entry: walk forward up to fill_days sessions
    fill_days = max(1, int(fill_days))
    window = post_df.head(fill_days)
    if window.empty:
        return None, np.nan, None
    for ts, row in window.iterrows():
        if row["Open"] <= buy_limit:
            return True, float(row["Open"]), ts.date()   # gap fill at open
        if row["Low"] <= buy_limit:
            return True, float(buy_limit), ts.date()     # touched limit intraday
    # Window fully elapsed without a fill
    return False, np.nan, None


def _verdict_signaled(curr_price, peak_price, entry_effective,
                      target_price, stop_price,
                      wd_elapsed, exp_days,
                      was_hit, entry_mode, entry_source="market"):
    """Categorize the current outcome vs the algorithm's plan.
    v3 (Aug-2026): NOT_FILLED no longer short-circuits — we monitor via
    market-price fallback per user rule 4.i.iv."""
    if entry_effective is None or not np.isfinite(entry_effective):
        return "NO_DATA", "Missing entry price."
    # Absolute terminal
    if pd.notna(target_price) and curr_price >= target_price:
        return "TARGET_HIT", f"Reached target ₹{target_price:.2f}."
    if pd.notna(stop_price) and curr_price <= stop_price:
        return "STOP_HIT", f"Stop ₹{stop_price:.2f} triggered."
    # Time-based
    curr_pnl = (curr_price / entry_effective - 1) * 100
    total_move = ((target_price / entry_effective - 1) * 100) if pd.notna(target_price) else 15.0
    if exp_days and wd_elapsed > exp_days * 1.5:
        return "EXPIRED", (f"Held {wd_elapsed}w-days > 1.5× expected ({exp_days}w-days) "
                           f"without hitting target. Current PnL {curr_pnl:+.2f}%.")
    # Pace
    if total_move <= 0:
        return "INVALID_PLAN", "Target ≤ effective entry — check row."
    elapsed_frac = min(1.0, max(0.05, (wd_elapsed / max(1, exp_days)) if exp_days else 0.5))
    expected_pnl_by_now = total_move * elapsed_frac
    if curr_pnl < 0:
        return "REVERSED", (f"Down {curr_pnl:+.2f}% from effective entry "
                            f"({wd_elapsed}w-days elapsed of {exp_days}w-day plan).")
    if curr_pnl >= expected_pnl_by_now * 1.15:
        return "AHEAD_OF_PACE", (f"{curr_pnl:+.2f}% vs expected {expected_pnl_by_now:+.2f}% "
                                 f"by day {wd_elapsed}. Beating schedule.")
    if curr_pnl >= expected_pnl_by_now * 0.85:
        return "ON_TRACK", (f"{curr_pnl:+.2f}% vs expected {expected_pnl_by_now:+.2f}% — matching plan.")
    return "BEHIND_PACE", (f"Only {curr_pnl:+.2f}% vs expected {expected_pnl_by_now:+.2f}% "
                           f"({wd_elapsed}w-days into {exp_days}w-day plan). Watch.")


# ============================================================================
#  ANALYSIS 2 — POSITIVE_NEWS
# ============================================================================
def analyze_positive_news(news_df: pd.DataFrame, obs_run_date: dt.date) -> pd.DataFrame:
    """For each positive-news row assume a market-open BUY on the FIRST
    trading session AFTER the observation date. Report working-day PnL."""
    if news_df.empty:
        return pd.DataFrame()

    out_rows = []
    prog = st.progress(0.0)
    total = len(news_df)
    for i, (_, r) in enumerate(news_df.iterrows()):
        prog.progress((i + 1) / total)
        ticker    = str(r["ticker"]).upper()
        obs_date  = _safe_date(r["observation_date"])
        sig_price = float(r["signal_price"]) if pd.notna(r.get("signal_price")) else np.nan
        if obs_date is None:
            continue
        ty = _to_yahoo(ticker)
        hist = _fetch_history(ty, obs_date - dt.timedelta(days=3),
                              obs_run_date + dt.timedelta(days=2))
        if hist.empty:
            out_rows.append(_news_row_no_data(r, obs_run_date))
            continue
        post = hist[hist.index.date > obs_date]
        if post.empty:
            out_rows.append(_news_row_no_data(r, obs_run_date,
                                              note="No post-observation trading yet."))
            continue
        buy_open_price = float(post["Open"].iloc[0])
        buy_open_date  = post.index[0].date()
        curr_price     = float(post["Close"].iloc[-1])
        peak_price     = float(post["High"].max())

        curr_pnl = (curr_price / buy_open_price - 1) * 100 if buy_open_price else np.nan
        peak_pnl = (peak_price / buy_open_price - 1) * 100 if buy_open_price else np.nan
        wd_elapsed = working_days_between(buy_open_date, obs_run_date)

        # Verdict buckets aligned with the user's ask
        if pd.notna(curr_pnl) and curr_pnl >= 3.0:
            verdict = "WORKING"
            note = f"News thesis playing out: {curr_pnl:+.2f}% since assumed entry."
        elif pd.notna(curr_pnl) and curr_pnl <= -3.0:
            verdict = "FAILED"
            note = f"News failed to convert: {curr_pnl:+.2f}%."
        else:
            verdict = "STALLED"
            note = f"Sideways since entry: {curr_pnl:+.2f}%. Watch."

        out_rows.append({
            "observation_date":       obs_run_date,
            "ticker":                 ticker,
            "signal_date":            obs_date,
            "working_days_elapsed":   int(wd_elapsed),
            "buy_at_open_price":      round(buy_open_price, 2),
            "buy_at_open_date":       buy_open_date,
            "signal_price":           round(sig_price, 2) if pd.notna(sig_price) else None,
            "current_price":          round(curr_price, 2),
            "current_pnl_pct":        round(curr_pnl, 2) if pd.notna(curr_pnl) else None,
            "peak_pnl_pct":           round(peak_pnl, 2) if pd.notna(peak_pnl) else None,
            "news_score":             r.get("news_score"),
            "news_top_headline":      r.get("news_top_headline"),
            "signal_reject_reason":   r.get("signal_reject_reason"),
            "reject_category":        r.get("reject_category"),
            "verdict":                verdict,
            "note":                   note,
        })
    prog.empty()
    return pd.DataFrame(out_rows)


def _news_row_no_data(r, obs_run_date, note="yfinance history unavailable"):
    return {
        "observation_date":       obs_run_date,
        "ticker":                 str(r["ticker"]).upper(),
        "signal_date":            _safe_date(r["observation_date"]),
        "working_days_elapsed":   None,
        "buy_at_open_price":      None,
        "buy_at_open_date":       None,
        "signal_price":           None,
        "current_price":          None,
        "current_pnl_pct":        None,
        "peak_pnl_pct":           None,
        "news_score":             r.get("news_score"),
        "news_top_headline":      r.get("news_top_headline"),
        "signal_reject_reason":   r.get("signal_reject_reason"),
        "reject_category":        r.get("reject_category"),
        "verdict":                "NO_DATA",
        "note":                   note,
    }


# ============================================================================
#  ANALYSIS 3 — TOP_MOVERS
# ============================================================================
def analyze_top_movers(movers_df: pd.DataFrame,
                       sig_df: pd.DataFrame,
                       news_df: pd.DataFrame,
                       obs_run_date: dt.date) -> pd.DataFrame:
    """For each user-entered top mover:
      * compute % change ON the observation date (Close/Open − 1)
      * check if the ticker was in Sheet 1 that day (recognized as signal)
      * check if the ticker was in Sheet 2 that day (positive news)
      * if in NEITHER, derive a best-effort "why missed" reason:
          - insufficient history (<250 trading sessions of price data)
          - no signal fired (base filter didn't cross)
    """
    if movers_df.empty:
        return pd.DataFrame()

    out_rows = []
    prog = st.progress(0.0)
    total = len(movers_df)
    for i, (_, r) in enumerate(movers_df.iterrows()):
        prog.progress((i + 1) / total)
        ticker   = str(r["ticker"]).upper()
        obs_date = _safe_date(r["observation_date"])
        user_pct = float(r["pct_change"]) if pd.notna(r.get("pct_change")) else np.nan
        if obs_date is None:
            continue

        ty = _to_yahoo(ticker)
        hist = _fetch_history(ty, obs_date - dt.timedelta(days=5),
                              obs_run_date + dt.timedelta(days=2))

        # Day-of % change (Close vs Open) — falls back to user-entered value
        pct_day = np.nan
        curr_price = np.nan
        if not hist.empty:
            on_day = hist[hist.index.date == obs_date]
            if not on_day.empty:
                _o = float(on_day["Open"].iloc[0])
                _c = float(on_day["Close"].iloc[0])
                pct_day = (_c / _o - 1) * 100 if _o else np.nan
            curr_price = float(hist["Close"].iloc[-1])
        pct_final = pct_day if pd.notna(pct_day) else user_pct

        # Cross-reference with Sheets 1 & 2 for the same obs date
        in_sig, sig_status = _lookup_ticker(sig_df, ticker, obs_date, "status")
        in_news, news_score_val = _lookup_ticker(news_df, ticker, obs_date, "news_score")

        # ---- v3 (Aug-2026): fetch a live news snapshot to explain the RISE ----
        # User rule 4.iii.i: "reason behind the raise". We look up news for the
        # observation date via the same news_sentiment engine the scanner uses.
        # This works even if the ticker was not in Sheets 1/2.
        rise_reason = ""
        try:
            from news_sentiment import fetch_news_score as _ns
            _n = _ns(ty, as_of_date=obs_date)
            if _n.get("top_headline"):
                rise_reason = (f"[news {_n.get('score', 0):+.2f} · "
                               f"{_n.get('n_articles', 0)} articles] "
                               f"{_n['top_headline'][:120]}")
        except Exception:
            rise_reason = ""

        # Reason bucket combining recognition state + rise explanation
        if in_sig:
            reason = f"✅ Detected as signal (status: {sig_status or 'unknown'})."
            if rise_reason:
                reason += f"  Likely catalyst: {rise_reason}"
        elif in_news:
            reason = (f"📰 Detected via positive news (news_score {news_score_val}). "
                      f"Algorithm saw the catalyst but didn't fire a technical signal.")
            if rise_reason:
                reason += f"  Headline: {rise_reason}"
        else:
            reason = _guess_missed_reason(hist, obs_date)
            if rise_reason:
                reason += f"  Likely catalyst: {rise_reason}"

        out_rows.append({
            "observation_date":     obs_date,
            "ticker":               ticker,
            "pct_change_that_day":  round(pct_final, 2) if pd.notna(pct_final) else None,
            "current_price":        round(curr_price, 2) if pd.notna(curr_price) else None,
            "in_signaled_sheet":    "Y" if in_sig else "N",
            "signaled_status":      sig_status,
            "in_news_sheet":        "Y" if in_news else "N",
            "news_score_that_day":  news_score_val,
            "reason_recognized_or_missed": reason,
            "user_notes":           r.get("notes"),
        })
    prog.empty()
    return pd.DataFrame(out_rows)


def _lookup_ticker(df: pd.DataFrame, ticker: str, obs_date: dt.date, field: str):
    """Check if a (ticker, obs_date) pair exists in df; return (exists, field_value)."""
    if df.empty:
        return False, None
    mask = ((df["ticker"].astype(str).str.upper() == ticker.upper())
            & (pd.to_datetime(df["observation_date"], errors="coerce").dt.date == obs_date))
    hit = df[mask]
    if hit.empty:
        return False, None
    return True, hit.iloc[0].get(field) if field in hit.columns else None


def _guess_missed_reason(hist: pd.DataFrame, obs_date: dt.date) -> str:
    """Best-effort explanation for why a top mover was NOT captured.
    Uses only stock's OWN historical bars — no scanner re-run required."""
    if hist.empty:
        return ("❌ Not detected. yfinance had no history for this ticker — "
                "likely a recent listing or an NSE symbol Yahoo can't resolve. "
                "Engine requires ≥250 sessions before it can compute the "
                "200-DMA that every strategy conditions on.")
    prior_bars = hist[hist.index.date <= obs_date]
    n_bars = len(prior_bars)
    if n_bars < 250:
        return (f"❌ Not detected. Only {n_bars} trading sessions of history "
                f"available on {obs_date} — engine's MIN_DAYS floor is 250 "
                f"(needed for stable 200-DMA / 252-day-high indicators). "
                f"Recent listing / thin coverage.")
    # If we have enough history, the miss is more subtle — trend / vol / OBV
    if n_bars >= 200:
        recent = prior_bars.tail(200)
        close = recent["Close"]
        sma200 = close.rolling(200).mean().iloc[-1]
        last = close.iloc[-1]
        if pd.notna(sma200):
            pct = (last / sma200 - 1) * 100
            if pct < 0:
                return (f"❌ Not detected. On {obs_date} the stock was "
                        f"{pct:+.1f}% vs its 200-DMA (BELOW the long trend). "
                        f"PASS_combined defaults reject signals below the "
                        f"200-DMA unless the reversal branch qualifies — this "
                        f"day's move was likely a counter-trend pop that "
                        f"didn't meet the reversal preconditions.")
    return ("❌ Not detected. Sufficient price history exists, but the base "
            "technical filter (uptrend + OBV rising / breakout branch / "
            "reversal-with-confirmation) didn't fire on the observation "
            "date. Common causes: gap-up entry (require_confirmation blocked "
            "it), regime hard-block, or extension penalty pushed rank below "
            "the fill window.")


# ============================================================================
#  RENDERING
# ============================================================================
def body():
    """Streamlit body — auto-called by trading_suite.py."""
    st.title("🔮 Wishlist Tracker v2")
    st.caption("Reads `wishlist.xlsx` (3 sheets auto-populated by the daily scanner + your top-mover entries) "
               "and produces per-sheet analysis. All timings in working days (Mon–Fri).")

    initialize_workbook()   # self-heal on first run

    with st.sidebar:
        st.header("Wishlist v2 — settings")
        obs_run_date = st.date_input(
            "Analysis 'as of' date",
            value=dt.date.today(),
            max_value=dt.date.today(),
            help="Fixes the timestamp used for elapsed / remaining calculations. "
                 "Set to today for a live view; set to an older date to reproduce a "
                 "previous run's numbers.",
        )
        run_btn = st.button("▶️ Run analysis on all 3 sheets", type="primary",
                            use_container_width=True)
        st.caption(f"📁 Workbook: `{WISHLIST_XLSX}`")
        summary = store.workbook_summary()
        st.markdown(
            f"- Sheet 1 · **signaled_today**: `{summary.get(SHEET_SIGNALED, 0)}` rows\n"
            f"- Sheet 2 · **positive_news**: `{summary.get(SHEET_NEWS, 0)}` rows\n"
            f"- Sheet 3 · **top_movers**: `{summary.get(SHEET_MOVERS, 0)}` rows"
        )
        st.divider()
        st.markdown("### Sheet 3 — add a top mover")
        with st.form("add_mover_form", clear_on_submit=True):
            mv_date = st.date_input("Observation date", value=dt.date.today(),
                                     max_value=dt.date.today())
            mv_ticker = st.text_input("Ticker (bare NSE symbol)", "")
            mv_pct    = st.number_input("% change that day (optional)",
                                         value=0.0, step=0.1, format="%.2f")
            mv_notes  = st.text_area("Notes (optional)", "", height=60)
            submitted = st.form_submit_button("➕ Add row to Sheet 3")
            if submitted and mv_ticker.strip():
                sheets = store.read_all_sheets()
                movers = sheets[SHEET_MOVERS]
                # v3 (Aug-2026): preserve entry time so obs_date carries hh:mm:ss.
                # If user picked today, stamp NOW; historical entry uses midnight.
                _obs_ts_manual = (dt.datetime.now()
                                  if mv_date == dt.date.today()
                                  else dt.datetime.combine(mv_date, dt.time.min))
                new_row = pd.DataFrame([{
                    "observation_date": _obs_ts_manual,
                    "ticker":           mv_ticker.strip().upper(),
                    "pct_change":       mv_pct if mv_pct else None,
                    "notes":            mv_notes.strip() or None,
                }])
                combined = pd.concat([movers, new_row], ignore_index=True)
                # Dedup on the DATE portion only so multi-entries same day
                # collapse; keep the full datetime column intact.
                _key = pd.to_datetime(
                    combined["observation_date"], errors="coerce").dt.date
                combined = (combined.assign(_dedup_date=_key)
                                     .drop_duplicates(subset=["_dedup_date", "ticker"],
                                                      keep="last")
                                     .drop(columns=["_dedup_date"])
                                     .reset_index(drop=True))
                sheets[SHEET_MOVERS] = combined
                store._write_all_sheets(sheets)
                st.success(f"Added {mv_ticker.strip().upper()} on {mv_date}.")

    sheets = store.read_all_sheets()
    sig_df    = sheets[SHEET_SIGNALED]
    news_df   = sheets[SHEET_NEWS]
    movers_df = sheets[SHEET_MOVERS]

    tabs = st.tabs([
        f"1 · Signaled today ({len(sig_df)})",
        f"2 · Positive news ({len(news_df)})",
        f"3 · Top movers ({len(movers_df)})",
    ])

    if run_btn:
        # v3 (Aug-2026): compose full datetime for observation_date so
        # the persisted timestamp includes hour:min:sec. If user asked for
        # a live "as-of today" analysis, capture NOW; historical replays
        # use midnight of the picked date.
        if obs_run_date == dt.date.today():
            obs_ts = dt.datetime.now()
        else:
            obs_ts = dt.datetime.combine(obs_run_date, dt.time.min)
        st.caption(f"⏱ Analysis timestamp: **{obs_ts.strftime('%Y-%m-%d %H:%M:%S')}**")
        analyses = {}
        with tabs[0]:
            st.subheader("Analysis · Sheet 1 — signaled_today")
            with st.spinner("Fetching prices for signalled rows..."):
                a1 = analyze_signaled(sig_df, obs_ts)
            analyses["signaled_analysis"] = a1
            _render_signaled_analysis(a1, sig_df)
        with tabs[1]:
            st.subheader("Analysis · Sheet 2 — positive_news")
            with st.spinner("Fetching prices for positive-news rows..."):
                a2 = analyze_positive_news(news_df, obs_ts)
            analyses["positive_news_analysis"] = a2
            _render_news_analysis(a2)
        with tabs[2]:
            st.subheader("Analysis · Sheet 3 — top_movers")
            with st.spinner("Fetching prices for top-mover rows..."):
                a3 = analyze_top_movers(movers_df, sig_df, news_df, obs_ts)
            analyses["top_movers_analysis"] = a3
            _render_movers_analysis(a3)

        # Persist all three analyses in one workbook write
        try:
            store.write_observations(analyses)
            st.success(f"✅ Analysis persisted → `{OBS_XLSX}` "
                       f"(3 sheets · Sheet 1: {len(analyses['signaled_analysis'])} · "
                       f"Sheet 2: {len(analyses['positive_news_analysis'])} · "
                       f"Sheet 3: {len(analyses['top_movers_analysis'])} rows)")
        except store.WorkbookLockedError as _e:
            st.error(
                f"⚠️ Could not save `{OBS_XLSX}` — it's open in Excel or held "
                f"by another process. The analysis shown above is complete "
                f"and correct in memory; just close the workbook and re-run "
                f"to persist. ({_e})"
            )
    else:
        with tabs[0]:
            st.info("Click **Run analysis** to compute Sheet 1 metrics.")
            if not sig_df.empty:
                st.dataframe(sig_df, use_container_width=True, hide_index=True,
                             height=min(400, 60 + 32 * len(sig_df)))
        with tabs[1]:
            st.info("Click **Run analysis** to compute Sheet 2 metrics.")
            if not news_df.empty:
                st.dataframe(news_df, use_container_width=True, hide_index=True,
                             height=min(400, 60 + 32 * len(news_df)))
        with tabs[2]:
            st.info("Click **Run analysis** to compute Sheet 3 metrics.")
            if not movers_df.empty:
                st.dataframe(movers_df, use_container_width=True, hide_index=True,
                             height=min(400, 60 + 32 * len(movers_df)))


def _render_signaled_analysis(a: pd.DataFrame, raw: pd.DataFrame):
    if a.empty:
        st.info("No signalled rows to analyse yet — run the Daily Scanner first.")
        return
    st.dataframe(a, use_container_width=True, hide_index=True,
                 height=min(500, 60 + 32 * len(a)))

    # ---- Aggregate #1 — Fill rate for Limit entries ----
    lim_rows = a[a["was_limit_hit"].isin(["Yes", "No", "Pending"])]
    st.markdown("### Aggregate insights")
    cA, cB, cC = st.columns(3)
    if not lim_rows.empty:
        fill_yes = int((lim_rows["was_limit_hit"] == "Yes").sum())
        fill_no  = int((lim_rows["was_limit_hit"] == "No").sum())
        pending  = int((lim_rows["was_limit_hit"] == "Pending").sum())
        cA.metric("Limit-fill rate",
                  f"{100*fill_yes/max(1,(fill_yes+fill_no)):.0f}%",
                  f"{fill_yes} filled · {fill_no} missed · {pending} pending")
    verdict_counts = a["verdict"].value_counts().to_dict()
    cB.metric("Winners (target/on-track/ahead)",
              str(verdict_counts.get("TARGET_HIT", 0) + verdict_counts.get("ON_TRACK", 0) + verdict_counts.get("AHEAD_OF_PACE", 0)))
    cC.metric("Losers (stop/reversed/expired)",
              str(verdict_counts.get("STOP_HIT", 0) + verdict_counts.get("REVERSED", 0) + verdict_counts.get("EXPIRED", 0)))

    # ---- Aggregate #2 — Is rank predictive? ----
    st.markdown("#### Does rank_score predict realised PnL?")
    ranked = a.dropna(subset=["rank_score", "current_pnl_pct"])
    if len(ranked) >= 6:
        corr = ranked[["rank_score", "current_pnl_pct"]].corr().iloc[0, 1]
        # Split by rank quantile — top-third vs bottom-third
        top = ranked.nlargest(max(3, len(ranked)//3), "rank_score")["current_pnl_pct"]
        bot = ranked.nsmallest(max(3, len(ranked)//3), "rank_score")["current_pnl_pct"]
        cX, cY, cZ = st.columns(3)
        cX.metric("Correlation (rank ↔ PnL)", f"{corr:+.2f}",
                  "positive = rank predicts winners")
        cY.metric("Top-third avg PnL",  f"{top.mean():+.2f}%", f"n = {len(top)}")
        cZ.metric("Bottom-third avg PnL", f"{bot.mean():+.2f}%", f"n = {len(bot)}")
        if corr > 0.15:
            st.success("Ranking IS working — higher rank stocks have higher realised PnL.")
        elif corr < -0.15:
            st.error("Ranking is INVERTED — the score is currently mis-ordering candidates.")
        else:
            st.warning("Ranking is essentially UNCORRELATED with PnL at this sample size — "
                       "may just be small-N noise.")
    else:
        st.caption(f"Need ≥ 6 rows with rank + PnL; currently {len(ranked)}.")

    # ---- Aggregate #3 — Target-on-time rate ----
    st.markdown("#### Are targets reached on the algorithm's stated timeline?")
    with_plan = a.dropna(subset=["expected_days_to_target"])
    if not with_plan.empty:
        target_hits = with_plan[with_plan["verdict"] == "TARGET_HIT"]
        on_schedule = target_hits[target_hits["working_days_elapsed"] <= target_hits["expected_days_to_target"]]
        st.write(f"**{len(target_hits)}** targets hit; **{len(on_schedule)}** on or ahead of schedule "
                 f"({100*len(on_schedule)/max(1,len(target_hits)):.0f}% on-time hit-rate).")


def _render_news_analysis(a: pd.DataFrame):
    if a.empty:
        st.info("No positive-news rows to analyse yet.")
        return
    st.dataframe(a, use_container_width=True, hide_index=True,
                 height=min(500, 60 + 32 * len(a)))
    c1, c2, c3 = st.columns(3)
    if "current_pnl_pct" in a.columns:
        winners = int((a["current_pnl_pct"] >= 3).sum())
        losers  = int((a["current_pnl_pct"] <= -3).sum())
        avg_ret = a["current_pnl_pct"].mean()
        c1.metric("News-thesis winners (≥ +3%)", str(winners))
        c2.metric("News-thesis losers  (≤ -3%)", str(losers))
        c3.metric("Mean PnL since assumed entry", f"{avg_ret:+.2f}%" if pd.notna(avg_ret) else "—")


def _render_movers_analysis(a: pd.DataFrame):
    if a.empty:
        st.info("No top movers logged yet. Use the sidebar form to add rows.")
        return
    st.dataframe(a, use_container_width=True, hide_index=True,
                 height=min(500, 60 + 32 * len(a)))
    c1, c2, c3 = st.columns(3)
    recognized = int((a["in_signaled_sheet"] == "Y").sum()) + int((a["in_news_sheet"] == "Y").sum())
    total = len(a)
    c1.metric("Top movers RECOGNIZED", f"{recognized}/{total}",
              f"{100*recognized/max(1,total):.0f}% coverage")
    signalled = int((a["in_signaled_sheet"] == "Y").sum())
    news_only = int((a["in_news_sheet"] == "Y").sum())
    c2.metric("via Signal sheet", str(signalled))
    c3.metric("via News sheet",   str(news_only))


def main():
    st.set_page_config(page_title="Wishlist Tracker v2", layout="wide")
    body()


if __name__ == "__main__":
    main()
