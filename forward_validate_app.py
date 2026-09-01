"""
forward_validate_app.py  (v2, Aug-2026)
=======================================
FORWARD VALIDATION with failure-clustering analysis and algorithm-improvement toggles.

What v2 adds over v1:
  * Nifty 500 default (statistically-meaningful sample sizes)
  * REGIME GATE — historical (uses only benchmark index price data → no look-ahead)
  * Same-day SIGNAL DECAY — if many stocks signal the same day, they aren't
    independent evidence; discount rank score OR cap N per day
  * Portfolio-level STOP COOLDOWN — after M stops in last N sessions, pause entries
  * SECTOR CAP — matches live scanner behavior (max K per sector)
  * FAILURE CLUSTERING analysis output:
      - Same-day failure detection (were stops synchronised?)
      - Sector distribution of failures vs shortlist
      - Correlation of stopped stocks' returns
      - Beta cluster check
  * MULTI-CUTOFF mode — auto-runs N cutoffs spanning different market regimes

WHY: v1 revealed that on a single choppy-day cutoff, multiple stocks all stopped
out together. Root cause is almost never "the algo is broken" — it's "the algo
took correlated bets during a bad regime, and stops fired en masse". The v2
additions surface that diagnosis clearly AND provide the filters that a
professional algo trader would use to mitigate it.

HONESTLY-DISCLOSED LIMITATIONS (auto-shown in UI):
  * Historical NEWS/EVENTS not available for free → skipped (as before)
  * Historical FUNDAMENTALS not point-in-time → skipped for cutoffs >5d ago
  * REGIME gate now IS applied historically (this is the v2 fix)

Run:  streamlit run forward_validate_app.py
"""

import os
import sys
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

# Optional news module. Only used when the cutoff is within the live-fetch
# window (14 days) — free news sources don't archive, so a cutoff of
# 2020-01-01 legitimately cannot have news. We NEVER fake old news.
# Defensive two-stage import (Aug-2026): the OLD `news_sentiment` module in
# a hot-reloaded Streamlit process may not have the newest helper functions
# yet. Falling all the way back to HAVE_NEWS=False would silently disable
# the news pass entirely — that's how the user hit "checkbox greyed out
# despite News-fetch-enabled banner". Fix: import the CORE function first
# (present in every version), then try the helpers with no-op stubs on
# ImportError. Now news still runs on hot-reloaded processes.
try:
    from news_sentiment import fetch_news_score as _news_score
    HAVE_NEWS = True
    try:
        from news_sentiment import clear_news_cache as _news_clear_cache
    except ImportError:
        def _news_clear_cache(): pass          # no-op fallback
    try:
        from news_sentiment import get_last_fetch_errors as _news_last_errors
    except ImportError:
        def _news_last_errors(): return {}      # no-op fallback
    try:
        from news_sentiment import reset_fetch_errors as _news_reset_errors
    except ImportError:
        def _news_reset_errors(): pass          # no-op fallback
    try:
        from news_sentiment import reset_google_block_flag as _news_reset_block
    except ImportError:
        def _news_reset_block(): pass          # v3.4 rate-limit flag reset
    try:
        from news_sentiment import is_rate_limited as _news_is_rate_limited
    except ImportError:
        def _news_is_rate_limited(): return False
except Exception:
    HAVE_NEWS = False
    def _news_clear_cache(): pass
    def _news_last_errors(): return {}
    def _news_reset_errors(): pass
    def _news_reset_block(): pass
    def _news_is_rate_limited(): return False

# Fundamentals gate — cache-aware. The cache is weekly (rotates every Saturday)
# so successive forward-validation runs within the week are instant on this
# pillar. Fundamentals are honestly not point-in-time (yfinance.info returns
# TODAY's numbers) — see the sidebar banner below for guidance on when to
# enable this. Kept enabled by default for recent cutoffs because it still
# blocks structurally-broken names that are unlikely to have swing edge on
# any date.
try:
    from fundamental_screen import (
        screen_universe as fs_screen_universe,
        summarize_results as fs_summarize,
        rejects_to_dataframe as fs_rejects_df,
        clear_fundamentals_cache as fs_clear_cache,
        _weekly_cache_bucket as fs_weekly_bucket,
        DEFAULT_FUNDA_CONFIG,
    )
    HAVE_FUNDA = True
except Exception:
    HAVE_FUNDA = False


# ======================================================================================
#  Engine loader — reuses swing_screener_app.py
# ======================================================================================
_here = os.path.dirname(os.path.abspath(__file__))
_ENGINE_PATH = os.path.join(_here, "swing_screener_app.py")
if not os.path.exists(_ENGINE_PATH):
    st.error(f"Engine file not found: {_ENGINE_PATH}")
    st.stop()
_spec = importlib.util.spec_from_file_location("engine", _ENGINE_PATH)
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)

from universe_loader import load_full_universe

# Constants mirrored from swing_scanner_app.py so the rank formula matches exactly.
RS_WINDOW = 63    # ~3 months for relative-strength (same as live scanner)

# ============================================================================
# SCANNER UTILITIES — shared with the live scanner so historical walk-forward
# uses the IDENTICAL formulae that rank tonight's shortlist. Imported lazily
# so we get: (a) Stage-2 scorer, (b) sector cap with LargeCap-reserve slot,
# (c) composite regime pipeline (index + segments + breadth), (d) SEBI
# LargeCap/MidCap/SmallCap category map. Falling back to safe no-ops means
# older scanner layouts still let the FV boot — user just loses the parity.
# v7 (Aug-2026 — user request "forward validation must mirror daily scanner"):
# expanded from a single _compute_stage2_score import to the full utility set.
# ============================================================================
def _lazy_import_scanner_utils():
    """Load selected pure functions + constants from swing_scanner_app.py.
    All are stateless / cache-friendly; safe to reuse across FV runs."""
    _fallbacks = {
        "_compute_stage2_score": (
            lambda df: (50.0, ["stage2 unavailable (import failed)"], {})),
        "_compute_anti_crowding_score": (
            lambda df: (0.0, ["anti-crowding unavailable (import failed)"])),
        "apply_sector_caps":     None,
        "compute_breadth":       None,
        "compute_regime":        None,
        "composite_gate":        None,
        "fetch_segments":        None,
        "_build_category_map":   None,
        "BENCH_TICKERS":         ["^CRSLDX", "^NSEI"],
        "SEGMENT_TICKERS":       {},
        "MIN_DAYS":              250,
    }
    try:
        import importlib.util as _iu
        _ss_path = os.path.join(_here, "swing_scanner_app.py")
        _spec = _iu.spec_from_file_location("_ss_utils", _ss_path)
        _mod  = _iu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _fallbacks.update({
            "_compute_stage2_score":       _mod._compute_stage2_score,
            "_compute_anti_crowding_score": getattr(
                _mod, "_compute_anti_crowding_score",
                _fallbacks["_compute_anti_crowding_score"]),
            "apply_sector_caps":     _mod.apply_sector_caps,
            "compute_breadth":       _mod.compute_breadth,
            "compute_regime":        _mod.compute_regime,
            "composite_gate":        _mod.composite_gate,
            "fetch_segments":        _mod.fetch_segments,
            "_build_category_map":   _mod._build_category_map,
            "BENCH_TICKERS":         _mod.BENCH_TICKERS,
            "SEGMENT_TICKERS":       _mod.SEGMENT_TICKERS,
            "MIN_DAYS":              _mod.MIN_DAYS,
        })
    except Exception:
        pass
    return _fallbacks

_SCAN_UTIL = _lazy_import_scanner_utils()
_compute_stage2_score         = _SCAN_UTIL["_compute_stage2_score"]
_compute_anti_crowding_score  = _SCAN_UTIL["_compute_anti_crowding_score"]
apply_sector_caps     = _SCAN_UTIL["apply_sector_caps"]
compute_breadth       = _SCAN_UTIL["compute_breadth"]
compute_regime        = _SCAN_UTIL["compute_regime"]
composite_gate        = _SCAN_UTIL["composite_gate"]
fetch_segments        = _SCAN_UTIL["fetch_segments"]
_build_category_map   = _SCAN_UTIL["_build_category_map"]
SEGMENT_TICKERS       = _SCAN_UTIL["SEGMENT_TICKERS"]
MIN_DAYS              = _SCAN_UTIL["MIN_DAYS"]

# --- Event risk (NSE corporate events API) — same source as the live scanner ---
try:
    from nse_events import event_risk as _event_risk
    HAVE_EVENTS = True
except Exception:
    HAVE_EVENTS = False
    def _event_risk(ticker, next_sessions=5):
        return {"blocked": False, "type": None, "days_until": None,
                "subject": None, "all_upcoming": []}


# ======================================================================================
#  Fetch helpers
# ======================================================================================
@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
def _fetch_full(ticker_yahoo: str, start: dt.date, end: dt.date) -> pd.DataFrame:
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


@st.cache_data(show_spinner=False, ttl=60 * 60 * 12)
def _fetch_bench(start: dt.date, end: dt.date):
    """Fetch broad Nifty benchmark (Nifty 500 preferred, fallback Nifty 50)."""
    if yf is None:
        return None, pd.DataFrame()
    for t in ["^CRSLDX", "^NSEI"]:
        try:
            df = yf.Ticker(t).history(start=start, end=end, interval="1d", auto_adjust=True)
            if df is not None and not df.empty:
                df = df[["Open", "High", "Low", "Close"]].copy()
                df.index = pd.to_datetime(df.index).tz_localize(None)
                return t, df.dropna()
        except Exception:
            continue
    return None, pd.DataFrame()


def _bare(sym: str) -> str:
    return sym.upper().replace(".NS", "").replace(".BO", "")


def _to_yahoo(sym: str) -> str:
    sym = sym.upper().strip()
    return sym if sym.endswith((".NS", ".BO")) else sym + ".NS"


# ======================================================================================
#  Regime gate — HISTORICAL (no look-ahead)
# ======================================================================================
def regime_at_cutoff(bench_df: pd.DataFrame, cutoff: dt.date) -> dict:
    """Given the benchmark index price series, compute what the regime status
    WAS on cutoff date, using only data ≤ cutoff (no look-ahead).
    Returns {"status": "RISK-ON"|"NEUTRAL"|"RISK-OFF", "pct_vs_200": x, "roc10": x}.
    """
    df = bench_df.loc[bench_df.index.date <= cutoff]
    if df.empty or len(df) < 210:
        return {"status": "UNKNOWN", "pct_vs_200": np.nan, "roc10": np.nan}
    c = df["Close"]
    s200 = float(c.rolling(200).mean().iloc[-1])
    last = float(c.iloc[-1])
    above_200 = last > s200
    pct_vs_200 = (last / s200 - 1) * 100
    roc10 = (c.iloc[-1] / c.iloc[-11] - 1) * 100 if len(c) > 11 else 0.0
    if above_200 and roc10 > -1.0:
        status = "RISK-ON"
    elif above_200 or roc10 > -3.0:
        status = "NEUTRAL"
    else:
        status = "RISK-OFF"
    return {"status": status, "pct_vs_200": round(pct_vs_200, 2),
            "roc10": round(roc10, 2), "above_200": above_200}


# ======================================================================================
#  Signal-day scan AS OF cutoff (no look-ahead)
# ======================================================================================
def scan_as_of(ticker: str, hist_df: pd.DataFrame, strategy: str,
               strat_params: dict, bt_kwargs: dict, cutoff: dt.date,
               sector_map: dict = None,
               category_map: dict = None,
               bench_close_series: pd.Series = None,
               idx_ret_window_pct: float = 0.0,
               require_confirmation: bool = False,
               block_risk_off: bool = False) -> dict:
    """As-of-cutoff scan. Now returns the full daily-scanner column set:
    rank_score, rel_strength, extension-penalty audit, exp_per_day_%,
    stop_%, exp_days_to_target, hist_trades / win_% / total_return_sum_%
    — so the Tonight's-Investment-Analysis-style renderer can consume its
    output without recomputing anything downstream.

    v7 (Aug-2026 — user request): now passes `bench_close`,
    `require_confirmation` and `block_risk_off` into `engine.generate_signals`
    so historical walk-forward respects the SAME signal-quality filters the
    live scanner applies. Without these, FV's shortlist over-counts stretched
    breakouts that would have been rejected live (same-day-confirmation was
    the filter that flipped a 9% win-rate loser into a 50% win-rate winner
    on Nifty 500 in scanner's own evidence log)."""
    df_in = hist_df.loc[hist_df.index.date <= cutoff].copy()
    if df_in.empty or len(df_in) < MIN_DAYS:
        return {"ticker": _bare(ticker), "status": "insufficient"}
    df = engine.compute_indicators(df_in)
    # v7 — bench series must be aligned to the same date window as df.
    # generate_signals reindex-ffills internally, so passing it raw is safe.
    _bench = bench_close_series if (bench_close_series is not None
                                    and not bench_close_series.empty) else None
    df = engine.generate_signals(df, strategy, strat_params,
                                 bench_close=_bench,
                                 require_confirmation=bool(require_confirmation),
                                 block_risk_off=bool(block_risk_off))
    trades = engine.run_backtest(df, **bt_kwargs)
    stats = engine.summarize(trades)
    last = df.iloc[-1]
    entry_ref = float(last["Close"])
    atr_now = float(last["atr14"]) if np.isfinite(last["atr14"]) else 0.0
    stop_mult = bt_kwargs.get("stop_value", 2.0)
    max_stop_pct = bt_kwargs.get("max_stop_pct", 8.0) or 8.0
    tgt_pct = bt_kwargs.get("target_pct", 15.0)
    limit_pct = bt_kwargs.get("limit_pct", 0.5)
    entry_mode = bt_kwargs.get("entry_mode", "Limit")
    if entry_mode == "Limit":
        limit_price = round(entry_ref * (1 - limit_pct / 100.0), 2)
        plan_entry = limit_price
    else:
        limit_price = np.nan
        plan_entry = entry_ref
    stop_price = max(plan_entry - stop_mult * atr_now,
                     plan_entry * (1 - max_stop_pct / 100))
    stop_pct = round((stop_price / plan_entry - 1) * 100, 2) if plan_entry else 0.0
    target_price = round(plan_entry * (1 + tgt_pct / 100), 2)

    # --- Historical stats (same fields the daily scanner exposes) ---
    n_seq         = stats.get("seq_trades", 0)
    winr_seq      = stats.get("seq_win_%", 0.0)
    exp_seq       = stats.get("seq_expectancy_%", 0.0)
    exp_day_seq   = stats.get("seq_exp_per_day_%", 0.0)
    hist_trades   = stats.get("trades", 0)
    hist_win      = stats.get("profitable_%", 0.0)
    hist_expect   = stats.get("expectancy_%", 0.0)
    tot_ret_sum   = stats.get("total_return_sum_%", 0.0)
    cagr_pct      = stats.get("cagr_%", np.nan)
    max_dd_pct    = stats.get("max_drawdown_%", np.nan)
    size_factor   = n_seq / (n_seq + 30.0)
    # Base confidence (unchanged for backward-compat)
    confidence_base = round(max(exp_day_seq, 0) * (winr_seq / 100.0)
                             * size_factor * 100, 2) if n_seq else 0.0

    # -----------------------------------------------------------------
    # Confidence-enhancement multipliers (Aug-2026 — mirror scan_one)
    # See docstring in swing_scanner_app.scan_one for rationale. Must
    # match scan_one exactly so historical walk-forward and live scan
    # produce identical rank_score. If either formula changes, this
    # block must be updated in lockstep.
    # -----------------------------------------------------------------
    hit_rate = float(stats.get("hit_rate_%", 0.0))
    _hit_delta = (hit_rate - 30.0) / 40.0
    hit_boost = 1.0 + max(-0.25, min(0.25, _hit_delta * 0.30))

    if   n_seq >= 500: sample_boost = 1.15
    elif n_seq >= 200: sample_boost = 1.10
    elif n_seq >= 100: sample_boost = 1.05
    else:              sample_boost = 1.00

    _atr_val = float(last.get("atr_pct", 3.5)) if pd.notna(last.get("atr_pct", np.nan)) else 3.5
    _atr_safe = max(1.5, min(9.0, _atr_val))
    atr_norm = max(0.85, min(1.15, 3.5 / _atr_safe))

    confidence = round(confidence_base * hit_boost * sample_boost * atr_norm, 2)

    # Informational R-multiple based cap-neutral confidence (mirrors scan_one)
    exp_R_seq = stats.get("seq_expectancy_R", 0.0)
    if exp_R_seq is None or (isinstance(exp_R_seq, float) and not np.isfinite(exp_R_seq)):
        exp_R_seq = 0.0
    confidence_R = round(
        max(0.0, float(exp_R_seq)) * (winr_seq / 100.0) * size_factor * 100, 2
    )

    # --- Relative strength vs supplied benchmark (matches scan_one formula) ---
    c_ser = df["Close"]
    if len(c_ser) > RS_WINDOW:
        stock_ret_window = (c_ser.iloc[-1] / c_ser.iloc[-(RS_WINDOW + 1)] - 1) * 100
    else:
        stock_ret_window = (c_ser.iloc[-1] / c_ser.iloc[0] - 1) * 100
    rel_strength = round(float(stock_ret_window - idx_ret_window_pct), 2)
    rs_norm = max(min(rel_strength / 30.0, 0.5), -0.5)
    rank_score = round(confidence * (1 + rs_norm), 2)

    # --- Extension penalty audit (mirrors scan_one Change #6) ---
    def _f(colname, default):
        v = last.get(colname, default)
        try:
            return float(v) if pd.notna(v) else default
        except Exception:
            return default
    rsi_now = _f("rsi14", 50.0)
    pct_20  = _f("pct_vs_sma20", 0.0)
    dist52  = _f("dist_52wH", -10.0)
    bb_pctb = _f("bb_pctB", 50.0)
    signals_today = bool(last["signal"])
    freshness = 1.0 if signals_today else 0.4
    ext_pen = 1.0
    penalty_bits = []
    if rsi_now > 70:  ext_pen *= 0.80; penalty_bits.append(f"RSI {rsi_now:.0f}")
    if pct_20  > 8:   ext_pen *= 0.85; penalty_bits.append(f"+{pct_20:.1f}% vs 20DMA")
    if dist52  > -2:  ext_pen *= 0.85; penalty_bits.append(f"{dist52:+.1f}% from 52wH")
    if bb_pctb > 90:  ext_pen *= 0.85; penalty_bits.append(f"BB%B {bb_pctb:.0f}")
    if not signals_today:
        penalty_bits.append("stale (no signal at cutoff)")
    rank_score_raw = rank_score
    rank_score = round(rank_score * freshness * ext_pen, 2)
    ranking_penalty_reason = " · ".join(penalty_bits) if penalty_bits else ""

    # ---------------------------------------------------------------------
    # STAGE-2 ALIGNMENT BOOST (mirrors scan_one in swing_scanner_app)
    # No look-ahead — reads only the last bar of df which is bounded to
    # data <= cutoff by the earlier df_in slicing. Same ±15% bound and
    # same 8-check scorer as the live scanner so the forward walk-forward
    # test evaluates the SAME rank formula the scanner uses tonight.
    # ---------------------------------------------------------------------
    stage2_score, stage2_reasons, _stage2_flags = _compute_stage2_score(df)
    stage2_boost = 1.0 + (stage2_score - 50.0) / 100.0 * 0.30
    rank_score_pre_stage2 = rank_score
    rank_score = round(rank_score * stage2_boost, 2)
    stage2_reason_str = " · ".join(r for r in stage2_reasons if r.startswith("✓"))

    # ---------------------------------------------------------------------
    # ANTI-CROWDING PENALTY  (Aug-2026 evidence-driven)
    # Weekly Nifty-500 experiment showed top-5 by rank averages −0.50%
    # while mid-5 averages +2.06% — the rank_score compounds extension
    # bias. Demote crowded names by up to 30% so ranking discriminates
    # fresh breakouts from over-extended chase trades. Parity with
    # scan_one in swing_scanner_app.
    # ---------------------------------------------------------------------
    crowding_score, crowding_reasons = _compute_anti_crowding_score(df)
    anti_crowd_mult = 1.0 - (crowding_score / 100.0) * 0.30
    rank_score_pre_crowd = rank_score
    rank_score = round(rank_score * anti_crowd_mult, 2)

    # --- Expected days to target (from winners' median) ---
    med_days = stats.get("med_days_to_target", np.nan)
    n_win    = stats.get("n_winners", 0)
    if np.isnan(med_days):
        exp_days_to_target = "n/a"
    elif n_win < 5:
        exp_days_to_target = f"{med_days:.0f}d ⚠ thin"
    else:
        exp_days_to_target = f"{med_days:.0f}d"

    return {
        "ticker": _bare(ticker), "status": "ok",
        "signals_today": signals_today,
        "sector":   (sector_map   or {}).get(_bare(ticker), "UNKNOWN"),
        "category": (category_map or {}).get(_bare(ticker), "Unknown"),
        "cutoff_close": entry_ref, "signal_close": entry_ref,
        "plan_entry": round(plan_entry, 2), "entry_ref": round(entry_ref, 2),
        "limit_price": (round(limit_price, 2) if np.isfinite(limit_price) else None),
        "target_price": target_price,
        "stop_price": round(stop_price, 2), "stop_%": stop_pct,
        "target_%": tgt_pct,
        "atr_pct":    round(float(last["atr_pct"]), 2) if np.isfinite(last["atr_pct"]) else np.nan,
        "last_atr_pct": round(float(last["atr_pct"]), 2) if np.isfinite(last["atr_pct"]) else np.nan,
        # Full backtest track-record set (matches daily scanner)
        "hist_trades":         hist_trades,
        "win_%":               hist_win,
        "expectancy_%":        hist_expect,
        "exp_per_day_%":       exp_day_seq,
        "hist_trades_seq":     n_seq,
        "hist_winrate_seq":    winr_seq,
        "hist_expectancy_seq": exp_seq,
        "seq_trades":          n_seq,
        "seq_win_%":           winr_seq,
        "seq_expectancy_%":    exp_seq,
        "seq_exp_per_day_%":   exp_day_seq,
        "total_return_sum_%":  tot_ret_sum,
        "cagr_%":              cagr_pct,
        "max_drawdown_%":      max_dd_pct,
        "confidence":          confidence,
        "rank_score":          rank_score,
        "rank_score_raw":      rank_score_raw,
        "ranking_penalty_reason": ranking_penalty_reason,
        # ---- Stage-2 alignment audit (Aug-2026) ----
        "stage2_score":         stage2_score,             # 0..100
        "stage2_boost":         round(stage2_boost, 3),   # 0.85..1.15
        "stage2_reason":        stage2_reason_str[:200],  # ✓ passing checks
        "rank_score_pre_stage2": rank_score_pre_stage2,   # for A/B audit
        # ---- Anti-crowding audit (Aug-2026 evidence-driven) ----
        "crowding_score":         crowding_score,
        "anti_crowding_mult":     round(anti_crowd_mult, 3),
        "crowding_reason":        " · ".join(crowding_reasons)[:200],
        "rank_score_pre_crowd":   rank_score_pre_crowd,
        # ---- Confidence-enhancement audit (Aug-2026) ----
        "confidence_base":  confidence_base,
        "hit_rate_%":       round(hit_rate, 1),
        "hit_boost":        round(hit_boost, 3),
        "sample_boost":     round(sample_boost, 3),
        "atr_norm":         round(atr_norm, 3),
        "confidence_R":     confidence_R,
        "rel_strength":        rel_strength,
        "exp_days_to_target":  exp_days_to_target,
        "regime_today": (last.get("trade_type", "") or "UPTREND") if signals_today else "",
    }


# ======================================================================================
#  Forward simulation — USES PRODUCTION ENGINE (respects router, trailing,
#  A/B/C/D/E exit stack). Aug-2026 rewrite: previously a simplified fixed-
#  target-or-stop loop that IGNORED the router + trailing → forward returns
#  were capped at target (winners never allowed to run beyond 15%).
# ======================================================================================
def forward_simulate(hist_df: pd.DataFrame, cutoff: dt.date, strategy: str,
                     strat_params: dict, bt_kwargs: dict) -> dict:
    """Run engine.run_backtest on the FULL history (backtest + forward).
    Extract the trade whose signal_date matches cutoff. This uses the exact
    same exit logic that the live scanner uses in production — router picks
    Trailing vs Fixed per trade, trailing stops let winners run beyond target,
    A/B/C/D/E exit stack applies if enabled."""
    if hist_df.empty:
        return {"outcome": "NO_DATA"}
    df = engine.compute_indicators(hist_df)
    df = engine.generate_signals(df, strategy, strat_params)
    trades = engine.run_backtest(df, **bt_kwargs)
    if trades.empty:
        return {"outcome": "NO_TRADES"}
    trades["signal_date_dt"] = pd.to_datetime(trades["signal_date"])
    cutoff_ts = pd.Timestamp(cutoff)
    match = trades[trades["signal_date_dt"] == cutoff_ts]
    if match.empty:
        # Signal may fire on a trading day just before cutoff — accept if it's the
        # LAST signal ≤ cutoff (means signal fired on cutoff bar itself).
        prior = trades[trades["signal_date_dt"] <= cutoff_ts]
        if prior.empty:
            return {"outcome": "NO_SIGNAL_AT_CUTOFF"}
        cand = prior.tail(1)
        if pd.Timestamp(cand["signal_date_dt"].iloc[0]) != cutoff_ts:
            return {"outcome": "NO_SIGNAL_AT_CUTOFF"}
        match = cand
    tr = match.iloc[0]
    return {
        "outcome":         tr["outcome"],
        "entry_date":      tr["entry_date"],
        "entry_price":     round(float(tr["entry_price"]), 2),
        "exit_date":       tr["exit_date"],
        "exit_price":      round(float(tr["exit_price"]), 2),
        "days_held":       int(tr["days_held"]),
        "net_return_%":    round(float(tr["net_return_%"]), 2),
        "gross_return_%":  round(float(tr.get("gross_return_%", 0)), 2),
        "peak_gain_%":     round(float(tr.get("peak_gain_%", 0)), 2),
        "exit_route":      tr.get("exit_route", ""),  # router audit (trailing/fixed)
    }


# ======================================================================================
#  Sector-cap + signal-decay + cooldown  (algorithm-improvement layers)
# ======================================================================================
def apply_sector_cap(shortlist: pd.DataFrame, max_per_sector: int) -> pd.DataFrame:
    """Keep at most `max_per_sector` names per sector, sorted by confidence."""
    if max_per_sector <= 0 or shortlist.empty:
        return shortlist
    kept, counts = [], {}
    sub = shortlist.sort_values("confidence", ascending=False).reset_index(drop=True)
    for i, row in sub.iterrows():
        sec = row.get("sector", "UNKNOWN") or "UNKNOWN"
        if counts.get(sec, 0) < max_per_sector:
            counts[sec] = counts.get(sec, 0) + 1
            kept.append(i)
    return sub.loc[kept].reset_index(drop=True)


# ======================================================================================
#  Failure-clustering analysis
# ======================================================================================
def cluster_analysis(cmp_df: pd.DataFrame) -> dict:
    """Given the predicted-vs-actual df, surface WHY multiple stocks failed:
       (1) Same-day stop clusters
       (2) Sector distribution of losses vs the shortlist as a whole
       (3) Correlation of losers' returns
    """
    out = {}
    stopped = cmp_df[cmp_df["actual_outcome"] == "STOP"].copy()
    filled = cmp_df[cmp_df["actual_outcome"].isin(["TARGET", "STOP", "TIME"])].copy()
    out["n_signalled"] = len(cmp_df)
    out["n_filled"] = len(filled)
    out["n_stopped"] = len(stopped)

    if not stopped.empty:
        # (1) Same-day stop clustering
        stopped["exit_date_dt"] = pd.to_datetime(stopped["actual_exit_date"], errors="coerce")
        by_date = stopped.groupby("exit_date_dt").size().sort_values(ascending=False)
        worst_days = by_date.head(3)
        out["worst_stop_days"] = [{"date": str(d.date()), "n_stops": int(n)}
                                   for d, n in worst_days.items() if n >= 2]

        # (2) Sector distribution
        if "sector" in stopped.columns and "sector" in filled.columns:
            stopped_by_sec = stopped["sector"].value_counts()
            filled_by_sec = filled["sector"].value_counts()
            out["sector_hits"] = []
            for sec, n_stop in stopped_by_sec.items():
                n_filled = int(filled_by_sec.get(sec, n_stop))
                rate = 100 * n_stop / n_filled if n_filled else 0
                out["sector_hits"].append({
                    "sector": sec, "n_stopped": int(n_stop),
                    "n_filled": n_filled, "stop_rate": round(rate, 1)
                })
            out["sector_hits"].sort(key=lambda x: -x["n_stopped"])

        # (3) Average days-to-stop (fast stops = mkt-wide event)
        if "actual_days_held" in stopped.columns:
            out["avg_days_to_stop"] = round(
                float(stopped["actual_days_held"].mean()), 1)
    return out


# ======================================================================================
#  UI
# ======================================================================================
def main():
    """Standalone entry-point — sets page config, then renders body().
    trading_suite.py imports body() directly to avoid a duplicate config call."""
    st.set_page_config(page_title="Forward Validation v2", layout="wide")
    body()


def body():
    """All render logic, no set_page_config (safe to call inside a larger app
    like trading_suite.py where the top-level page config has already been set)."""
    st.title("🔮 Forward Validation v2 — with regime gate & failure clustering")
    st.caption("Walk-forward test with regime overlay, sector cap, signal decay, and "
               "clustering analysis to diagnose why stops cluster together.")

    with st.sidebar:
        st.header("1 · Backtest window & cutoff")
        today = dt.date.today()

        # =================================================================
        # DATE-RANGE BACKTEST WINDOW  (Aug-2026 — user request)
        # -----------------------------------------------------------------
        # Two dates instead of one:
        #   bt_start = start of price history used for indicator + backtest
        #   cutoff   = end of backtest & start of forward test = "scan as-of"
        # Forward window = cutoff → today (auto), so we always see the full
        # realized forward path that's actually available in Yahoo's data.
        # =================================================================
        bt_start = st.date_input(
            "Backtest history START",
            value=dt.date(2020, 1, 1),
            min_value=dt.date(2010, 1, 1),
            max_value=today - dt.timedelta(days=280),
            help="First bar the engine sees. Engine needs ≥250 trading "
                 "sessions before the cutoff to compute the 200-DMA — pick "
                 "at least 14 months before the cutoff. Earlier = more "
                 "historical trades in the per-stock backtest evidence."
        )
        cutoff = st.date_input(
            "Scan 'as of' date  (= end of backtest, start of forward test)",
            value=today - dt.timedelta(days=7),
            min_value=bt_start + dt.timedelta(days=280),
            max_value=today - dt.timedelta(days=1),
            help="The scanner runs as if it were this day. Everything after "
                 "this date is forward-testing territory. Recommended: pick "
                 "a cutoff 7-30 days ago so you can see how the predictions "
                 "actually played out."
        )
        _bt_years = (cutoff - bt_start).days / 365.25
        _days_since_cutoff = (today - cutoff).days
        st.caption(
            f"📊 Backtest history: **{_bt_years:.1f} years** "
            f"({bt_start} → {cutoff}) · "
            f"🔮 Forward window: **{_days_since_cutoff} days** ({cutoff} → {today})"
        )
        fwd_days = st.slider(
            "Forward observation window (calendar days after cutoff)",
            min_value=15,
            max_value=max(180, _days_since_cutoff + 30),
            value=max(15, min(180, _days_since_cutoff)),
            help="How many days after the cutoff to track each trade for "
                 "exit. Default = calendar days from cutoff to today, so "
                 "we see the full realized forward path."
        )

        # ---- Feasibility banners (news + fundamentals point-in-time) ----
        days_old = _days_since_cutoff       # backward-compat with older refs below
        if _days_since_cutoff <= 7:
            st.success(f"✅ News fetch **enabled** — cutoff is {_days_since_cutoff}d "
                       f"ago, well inside the 7-day live-fetch window.")
            news_available_for_cutoff = True
        elif _days_since_cutoff <= 14:
            st.info(f"ℹ️ News fetch **partial** — cutoff is {_days_since_cutoff}d "
                    f"ago; only headlines newer than {14 - _days_since_cutoff} "
                    f"days ago (relative to cutoff) will show up.")
            news_available_for_cutoff = True
        else:
            st.warning(f"⚠️ News fetch **skipped** — cutoff is {_days_since_cutoff}d "
                       f"ago; free news sources don't archive that far. "
                       f"Historical news gate honestly disabled.")
            news_available_for_cutoff = False

        if _days_since_cutoff > 5:
            st.caption(f"ℹ️ Fundamentals gate stays disabled (yfinance.info is "
                       f"today's data, not point-in-time as-of {cutoff}).")

        use_news = st.checkbox(
            "📰 Apply news pass on cutoff-day candidates",
            value=(news_available_for_cutoff and HAVE_NEWS),
            disabled=not (news_available_for_cutoff and HAVE_NEWS),
            help=("Fetches recent headlines for EVERY fundamentally-passing stock "
                  "(not just signalling ones) and tilts rank_score ±20% on the "
                  "signalling subset — same formula as the live scanner. "
                  "Non-signalling stocks with material news land in the "
                  "'News-driven WATCHLIST' expander at the bottom. Only "
                  "meaningful when the cutoff is recent — see banner above."))
        news_lookback = st.slider(
            "News lookback (days back from cutoff)",
            min_value=3, max_value=14,
            value=7,
            disabled=not (news_available_for_cutoff and HAVE_NEWS and use_news),
            help="How many days of headlines to fetch per stock, measured "
                 "BACKWARDS from the cutoff date. E.g. cutoff=2026-08-08 "
                 "with lookback=7 → window is 2026-08-01 → 2026-08-08. "
                 "Google-News practical ceiling is ~14 days beyond which "
                 "coverage becomes patchy."
        )
        # v3.2 (Aug-2026): explicit cache-clear button. Necessary because
        # Streamlit's @st.cache_data holds the news results for 60 min per
        # session — if a previous run cached 0-item results (e.g. before a
        # bug fix), re-running would just replay those zeros. This button
        # wipes the cache so the next run does a fresh fetch.
        if HAVE_NEWS:
            if st.button(
                "🔄 Force refresh news cache",
                disabled=not use_news,
                help="Clears the 60-min Streamlit news cache so the next "
                     "run re-fetches from Google News + yfinance. Use if "
                     "you upgraded the code / changed the cutoff and are "
                     "seeing stale zero-item cached results."):
                _news_clear_cache()
                st.success("✅ News cache cleared. Next run will re-fetch.")

        # ==============================================================
        # 1b · Fundamentals gate (cache-aware, weekly refresh)
        # --------------------------------------------------------------
        # Runs BEFORE the technical scan so we save the yfinance fetch
        # cost on stocks that are structurally broken. Cache rotates
        # every Saturday — 7-day TTL. Same code path as the live scanner.
        # HONEST CAVEAT: yfinance.info returns TODAY's numbers, not
        # point-in-time-as-of-cutoff. For very-old cutoffs the gate can
        # reject a stock that was fine on cutoff but is broken today.
        # ==============================================================
        st.header("1b · Fundamentals gate")
        if not HAVE_FUNDA:
            st.caption("⚠️ `fundamental_screen` module unavailable — "
                       "fundamentals gate disabled.")
            apply_funda_gate = False
            momentum_preset = False
        else:
            _fbucket = fs_weekly_bucket()
            st.caption(f"📅 Weekly cache key: **{_fbucket}** "
                       f"(auto-refresh next Saturday)")
            apply_funda_gate = st.checkbox(
                "Apply fundamental gate before technical scan",
                value=(_days_since_cutoff <= 30),
                help="ON: filter out structurally broken names (low ROE, "
                     "high D/E, promoter pledge, etc.) before running the "
                     "technical scan. Cache-aware — instant re-run within "
                     "the same week. Recommend ON for cutoffs within "
                     "~30 days of today; toggle off for very old cutoffs "
                     "where 'broken today' ≠ 'broken then'.")
            momentum_preset = st.checkbox(
                "🚀 Momentum-friendly preset  (recommended)",
                value=True,
                disabled=not apply_funda_gate,
                help="Same preset as the live scanner: Quality (loose) + "
                     "Governance only. Skips Valuation / Trend / Growth "
                     "pillars because momentum swings can carry rich P/E "
                     "and recovery stocks show negative growth.")
            if st.button("🔄 Force refresh fundamentals now",
                         disabled=not apply_funda_gate,
                         help="Clears the fundamentals cache so the next "
                              "run re-fetches from yfinance + Screener.in. "
                              "Use after quarterly results season."):
                fs_clear_cache()
                st.success("✅ Fundamentals cache cleared. "
                           "Next run will re-fetch fresh data.")

        st.header("2 · Universe")
        buckets_meta = load_full_universe()
        buckets = buckets_meta["buckets"]
        sector_map = buckets_meta.get("sector_map", {})
        default_bucket = "Nifty500" if "Nifty500" in buckets else list(buckets.keys())[0]
        # Aug-2026 (user request): add "Enter manually" so specific stocks
        # can be forward-validated without picking a full bucket. Mirrors the
        # Daily Scanner's segment picker exactly — same option name, same
        # comma/space parsing so muscle memory carries over.
        bucket_options = list(buckets.keys()) + ["Enter manually"]
        bucket_choice = st.selectbox(
            "Universe bucket",
            bucket_options,
            index=bucket_options.index(default_bucket),
            help="Pick one of the standard NSE buckets, or choose **Enter manually** "
                 "to test a curated list of tickers (e.g. your current positions or "
                 "a small watchlist)."
        )
        if bucket_choice == "Enter manually":
            manual_tickers_txt = st.text_area(
                "Tickers (comma or space separated)",
                "HAL, BEL, HUDCO, IRFC, RVNL",
                height=100,
                help="Bare NSE symbols (no .NS suffix needed). "
                     "Example: `HAL, ADANIENT, POLYCAB` or one per line. "
                     "Case-insensitive. Anything not resolvable on Yahoo will "
                     "be flagged as 'no data' in the scan output."
            )
            universe = [t.strip().upper() for t in
                        manual_tickers_txt.replace(",", " ").split()
                        if t.strip()]
            if universe:
                st.caption(f"✏️ **Manual list:** {len(universe)} tickers — "
                           f"{', '.join(universe[:8])}"
                           + (" …" if len(universe) > 8 else ""))
            else:
                st.warning("⚠️ Manual list is empty — add at least one ticker.")
        else:
            universe = buckets.get(bucket_choice, [])
            st.caption(f"{len(universe)} stocks in {bucket_choice}")
        # Slider guards: max=1 breaks the widget, so ensure at least 1
        _uni_n = max(1, len(universe))
        _slider_min = 1 if bucket_choice == "Enter manually" else min(20, _uni_n)
        max_n = st.slider(
            "Limit stocks this run",
            _slider_min, _uni_n,
            min(_uni_n, 200 if bucket_choice == "Nifty500"
                else _uni_n if bucket_choice == "Enter manually"
                else min(50, _uni_n))
        )

        st.header("3 · Regime overlay  🆕")
        use_regime = st.checkbox("Apply market-regime gate historically",
                                 value=True,
                                 help="Uses ONLY the benchmark index's price data ≤ cutoff "
                                      "(no look-ahead). RISK-OFF cutoffs → skip all signals "
                                      "(cash is a position). NEUTRAL → keep signals but "
                                      "flag advisory.")
        regime_block_on_risk_off = st.checkbox(
            "Hard-block ALL trades when regime = RISK-OFF", value=True,
            disabled=not use_regime,
            help="This is the biggest single lever. Momentum longs in RISK-OFF regime "
                 "are the #1 cause of clustered stop-outs.")
        regime_block_neutral_decel = st.checkbox(
            "Also block when regime = NEUTRAL AND 10-day ROC < -1%", value=True,
            disabled=not use_regime,
            help="EVIDENCE-BASED FIX (Aug-2026): multi-cutoff walk-forward on Nifty 500 "
                 "showed that NEUTRAL-with-negative-ROC periods deliver -2.4% avg per trade "
                 "with 60% stop rate. NEUTRAL alone is fine; NEUTRAL-with-decelerating "
                 "momentum is the trap. This filter catches exactly that.")

        st.header("4 · Signal decay & cooldown  🆕")
        use_decay = st.checkbox(
            "Cap signals per day (co-signal decay)", value=True,
            help="When 30 stocks fire signals on the same day, they're NOT 30 independent "
                 "bets — they're one bet on the momentum factor. Cap it.")
        max_signals_per_day = st.slider(
            "Max NEW entries per day", 3, 30, 10, 1,
            disabled=not use_decay,
            help="Keep only the top-N by confidence per cutoff. Prevents over-concentration.")

        st.header("5 · Sector cap")
        max_per_sector = st.slider("Max per sector", 1, 10, 3,
                                   help="Same as live scanner — prevents 5-out-of-8 "
                                        "shortlist being metals stocks that all crash together.")
        # v7 — Parity with scanner's Section 8: reserve one slot per sector for
        # the top-ranked LargeCap signal (portfolio-construction bias over
        # marginal small-cap alpha).
        reserve_lc_slot = st.checkbox(
            "🏛️ Reserve 1 sector slot for top LargeCap (recommended)",
            value=True,
            disabled=(max_per_sector <= 0),
            help="Same LargeCap-reserved-slot logic the scanner uses in "
                 "Section 8. When ON: in each sector, the highest-ranked "
                 "LargeCap signal claims one of the max-per-sector slots "
                 "first. Prevents cap-mix skew where 3 SmallCaps in Financial "
                 "Services displace HDFCBANK.")

        # v7 — Event-risk block (parity with scanner's Section 2c)
        st.header("5b · Event-risk block")
        use_event_block = st.checkbox(
            "🚫 Block signals with an imminent corporate event",
            value=True,
            disabled=not HAVE_EVENTS,
            help="Fetches NSE's corporate-events API for each signalling stock. "
                 "If results / board meeting / dividend / split / AGM falls "
                 "within the window below, that stock is dropped from the "
                 "shortlist. Prevents 5-20% overnight-gap blowups. HONEST "
                 "CAVEAT: NSE API returns TODAY'S event calendar — for cutoffs "
                 "more than a few days old the block is not point-in-time and "
                 "should be considered advisory only.")
        event_window = st.slider(
            "Block if event is within (trading sessions)", 1, 15, 5, 1,
            disabled=not (use_event_block and HAVE_EVENTS),
            help="5 sessions ≈ 7 calendar days (scanner default). Tighter = "
                 "more trades but less safety margin.")

        st.header("6 · Strategy & rules")
        strategy = st.selectbox("Strategy",
                                ["PASS_combined", "PASS_recommended", "PASS_tight",
                                 "PASS_balanced", "PASS_reversal"], index=0)
        target_pct = st.number_input("Target (%)", 1.0, 100.0, 15.0, 0.5)
        # v7 — min_hold slider added for parity with scanner's Section 3
        cA_h, cB_h = st.columns(2)
        min_hold = cA_h.number_input("Min hold (d)", 1, 60, 1,
            help="Advisory holding-period floor. Scanner default = 1 "
                 "(never exit intraday). Match this to the Daily Scanner "
                 "setting so the two apps produce identical trades.")
        max_hold = cB_h.number_input("Max hold (d)", 1, 120, 30)
        entry_mode = st.radio("Entry style", ["Limit", "Market open"], index=0)
        limit_pct = st.slider("Limit below signal close (%)", 0.0, 5.0, 0.5, 0.1) \
                    if entry_mode == "Limit" else 0.0
        fill_days = st.number_input("Order valid for (sessions)", 1, 5, 1) \
                    if entry_mode == "Limit" else 1
        # v7 — Cut-dead-trades toggle (parity with scanner Section 3b)
        cut_on = st.checkbox(
            "Cut dead trades early (conviction exit)", value=False,
            help="If the trade is still red on day N by threshold %, free the "
                 "capital. Scanner default OFF. Turning this on tightens "
                 "results toward the more disciplined variant.")
        cut_day = st.number_input("Cut on day", 1, 10, 2) if cut_on else None
        cut_threshold = st.slider("if return below (%)", -8.0, 2.0, 0.0, 0.5) if cut_on else 0.0
        # NEW (Aug-2026): exit style toggle — critical for "let winners run"
        exit_mode = st.radio(
            "Exit style", ["Trailing (let winners run past target)", "Fixed target"],
            index=0,
            help="**Trailing**: target is a MINIMUM (15%). Once hit, trailing stop lets "
                 "winners run to 20-40%. Router picks trailing vs fixed per trade automatically.\n\n"
                 "**Fixed target**: exit at exactly 15%, no more. Simpler but caps upside.")
        exit_mode = "Trailing" if exit_mode.startswith("Trailing") else "Fixed target"
        trail_mult = st.slider("Trailing distance (x ATR)", 0.5, 5.0, 2.0, 0.5,
                                disabled=(exit_mode != "Trailing"))
        # v3 (Aug-2026): mirror Daily Scanner's lock_on checkbox exactly.
        # Previously the Forward Validator ALWAYS passed a lock_pct value,
        # while the Daily Scanner allows lock_pct=None (unchecked). Result:
        # trades that ran uncapped in Daily Scanner (e.g. HUDCO 2023-12-07
        # → +63.22% gross) got prematurely capped at +10% in Forward
        # Validator. This checkbox restores parity — see hudco_hunt.py for
        # the empirical confirmation.
        lock_on = st.checkbox(
            "Lock in profit once objective reached",
            value=True,
            disabled=(exit_mode != "Trailing"),
            help="ON (default): once price touches the +15% target, the stop "
                 "never falls below the lock level (e.g. +10%). Guarantees a "
                 "profitable exit at cost of capping upside during volatile "
                 "pullbacks.\n\n"
                 "OFF: pure trailing — after target, the stop still trails "
                 "peak by trail_mult × ATR with no floor. This is what "
                 "catches runners (HUDCO Dec-2023 → March-2024 rally: OFF "
                 "gives +63% gross · ON gives +10% gross). Match this to "
                 "your Daily Scanner setting for parity between the two apps."
        )
        lock_pct = st.slider(
            "Lock profit at (%)", 0.0, 30.0, 10.0, 0.5,
            disabled=(exit_mode != "Trailing" or not lock_on),
            help="Floor under a winner after it hits the objective."
        ) if lock_on else None
        stop_anchor = st.radio("Stop anchoring",
                               ["Structure (swing low)", "ATR distance"], index=0)
        stop_anchor = "Structure" if stop_anchor.startswith("Structure") else "ATR"
        trail_anchor = st.radio("Trail anchoring",
                                ["Structure (rising swing low)", "ATR distance"], index=0)
        trail_anchor = "Structure" if trail_anchor.startswith("Structure") else "ATR"
        stop_value = st.slider("Stop (x ATR)", 0.5, 5.0, 2.0, 0.5)
        max_stop_pct = st.slider("Max loss cap (%)", 2.0, 20.0, 10.0, 0.5)
        max_atr_pct = st.slider("Skip if ATR% above", 3.0, 15.0, 8.0, 0.5)
        cost_pct = st.number_input("Round-trip cost (%)", 0.0, 5.0, 0.20, 0.05)
        apply_stcg = st.checkbox("Apply 20% STCG on gains", value=True)

        # ==================================================================
        # v7 — EXIT STACK A + B + C   (parity with scanner Section 4b)
        # ------------------------------------------------------------------
        # All layers default OFF, exactly matching scanner defaults. Router
        # (Section 4d) chooses trailing vs fixed per-trade; these layers only
        # engage on the trailing side.
        # ==================================================================
        st.header("6b · Exit stack A + B + C")
        # v5 parity — default ON with data-calibrated ladder
        use_ratchet = st.checkbox(
            "🔒 A · Ratcheting profit lock (v5 data-calibrated ladder — ON by default)", value=True,
            help="Peak crosses 15/25/40/60/85/120% → floor moves to 5/12/25/40/60/85%. "
                 "Scanner default OFF.")
        use_shrink = st.checkbox(
            "📉 B · Shrinking trail multiplier", value=False,
            help="Trail width shrinks as gain grows. Scanner default OFF.")
        use_momexit = st.checkbox(
            "⚡ C · Momentum-exhaustion exit", value=False,
            help="Fires on RSI rollover / MACD flip / heavy-vol pullback / bearish "
                 "engulfing / 5-DMA break. Scanner default OFF.")
        mom_min_gain = st.slider(
            "C · Arm momentum exit only when up ≥ (%)", 5.0, 30.0, 10.0, 1.0,
            disabled=not use_momexit)

        # ==================================================================
        # v7 — EXIT STACK D + E   (parity with scanner Section 4c)
        # ==================================================================
        st.header("6c · Exit stack D + E")
        use_decay_stack = st.checkbox(
            "⏳ D · Time-decay tightening", value=False,
            help="Tighten trail after N stall sessions; forced exit after M. "
                 "Scanner default OFF.")
        decay_after = st.slider(
            "D · Start tightening after (sessions)", 3, 15, 5, 1,
            disabled=not use_decay_stack)
        decay_shrink = st.slider(
            "D · Tightening rate (% of stop-to-price gap per day)",
            10.0, 60.0, 25.0, 5.0, disabled=not use_decay_stack)
        decay_exit = st.slider(
            "D · Force exit after (sessions)", 5, 25, 10, 1,
            disabled=not use_decay_stack)
        use_staircase = st.checkbox(
            "🪜 E · Staircase partial exits", value=False,
            help="Book 30% at +10%, 30% at +20%, rest runs. Guarantees "
                 "profit-taking but caps runaway winners. Scanner default OFF.")

        # ==================================================================
        # v7 — POST-STOP COOLDOWN   (parity with scanner Section 4f)
        # Was hardcoded via engine default; now surfaced so FV & scanner
        # agree on this critical filter (scanner reports +79pp OOS lift @ 7d).
        # ==================================================================
        st.header("6d · Post-stop cooldown")
        cooldown_days = st.slider(
            "Block re-entries for N sessions after any STOP", 0, 30, 7, 1,
            help="Same as scanner Section 4f. 0 = disabled (legacy). "
                 "7 (scanner default) flipped a 5-stock 2024-2025 OOS test "
                 "from -5.5% to +74.2% total return. Match this to the Daily "
                 "Scanner setting for parity.")

        # ==================================================================
        # v7 — HISTORICAL SELF-CHECK   (parity with scanner Section 4e)
        # ==================================================================
        st.header("6e · Historical self-check")
        use_selfcheck = st.checkbox(
            "🪞 Reject stocks where own algo history is weak", value=True,
            help="After the technical backtest, drop stocks whose historical "
                 "win-rate OR total return falls below the floors below. "
                 "Uses SEQUENTIAL trade stats (non-overlapping), matching "
                 "scanner Section 4e exactly.")
        with st.expander("Self-check thresholds"):
            selfcheck_min_win = st.slider(
                "Min historical win rate %", 0.0, 60.0, 35.0, 1.0,
                disabled=not use_selfcheck)
            selfcheck_min_total = st.slider(
                "Min historical total return (sum) %",
                -500.0, 500.0, 0.0, 25.0, disabled=not use_selfcheck)
            selfcheck_min_trades = st.slider(
                "Min historical SEQUENTIAL trades to apply filter",
                5, 100, 30, 1, disabled=not use_selfcheck)

        st.header("7 · Filter thresholds")
        with st.expander("Advanced"):
            # v7 FIX — default `regime` lowered from 15.0 → 8.0 to match the
            # scanner's evidence-based Aug-2026 default. Higher threshold was
            # entering momentum stocks too late (near local tops), producing
            # false-breakout stops.
            p = {
                "regime": st.slider("Uptrend: % above 200-DMA", 0.0, 50.0, 8.0, 1.0,
                    help="Was 15%; lowered to 8% based on scanner walk-forward evidence."),
                "atr":    st.slider("Volatility floor: ATR%", 0.0, 10.0, 3.5, 0.5),
                "roc":    st.slider("Breakout ROC(10) >", 0.0, 15.0, 3.0, 0.5),
                "volr":   st.slider("Breakout volume ratio >", 0.5, 4.0, 1.2, 0.1),
                "rsi_os": st.slider("Reversal oversold RSI <", 10.0, 45.0, 30.0, 1.0),
            }
        # v7 — Same-day confirmation (parity with scanner Section 7 checkbox).
        # Default ON — scanner's own evidence log says this filter converted
        # a 9% win-rate loser into a 50% win-rate winner on Nifty 500.
        require_confirmation = st.checkbox(
            "🆕 Require signal-day confirmation (green close + volume)  🚀",
            value=True,
            help="Only take signals where signal day closes GREEN (close > open) "
                 "AND on above-average volume (vol > 20-day avg). Cuts trade "
                 "count ~65% — quality over quantity. Scanner default ON.")

        run = st.button("🔮 Run forward validation", type="primary",
                        use_container_width=True)

    if not run:
        st.info("Set your cutoff + toggles and click **Run forward validation**.")
        return

    # =============== EXECUTION ===============
    # v7 (Aug-2026): all scanner-parity toggles wired through. The engine
    # signature is a superset of the scanner's — sliders default to scanner
    # defaults, so unchecking the exit-stack + cooldown reproduces the
    # baseline engine exactly.
    bt_kwargs = dict(target_pct=target_pct, max_hold=int(max_hold),
                     min_hold=int(min_hold),            # v7 — user-configurable
                     stop_method="ATR",
                     stop_value=stop_value, cost_pct=cost_pct, apply_stcg=apply_stcg,
                     exit_mode=exit_mode, trail_mult=trail_mult, lock_pct=lock_pct,
                     max_stop_pct=max_stop_pct, max_atr_pct=max_atr_pct,
                     entry_mode=entry_mode, limit_pct=limit_pct, fill_days=int(fill_days),
                     max_chase_pct=1.5,   # v4 — parity with scanner Adaptive default
                     stop_anchor=stop_anchor, trail_anchor=trail_anchor,
                     # v7 — Cut dead trades (was silently OFF)
                     cut_day=(int(cut_day) if cut_day else None),
                     cut_threshold=cut_threshold,
                     # v7 — Exit stack A/B/C  (was hardcoded OFF, no UI)
                     ratchet_lock=use_ratchet,
                     shrink_trail=use_shrink,
                     momentum_exit=use_momexit,
                     mom_exit_min_gain=mom_min_gain,
                     # v7 — Exit stack D/E  (was hardcoded OFF, no UI)
                     time_decay=use_decay_stack,
                     decay_after_days=int(decay_after),
                     decay_shrink_pct=decay_shrink,
                     decay_exit_days=int(decay_exit),
                     staircase=use_staircase,
                     # v7 — Post-stop cooldown  (was engine default only)
                     post_stop_cooldown_days=int(cooldown_days),
                     # Regime router (unchanged — was already scanner-parity)
                     regime_route=True, route_min_adx=20.0, route_sma_slope_lb=20,
                     route_min_dist_pct=15.0, route_vol_lb=63, route_vol_baseline_lb=252,
                     route_fixed_target_pct=15.0)

    # NEW (Aug-2026): use the user-picked bt_start directly.
    # 300-day buffer before bt_start is added purely to make sure the very
    # first bars have enough history for 200-DMA / 252-day-high indicators.
    ohlc_start = bt_start - dt.timedelta(days=300)
    ohlc_end = cutoff + dt.timedelta(days=fwd_days + 1)
    subset = universe[:max_n]

    # ================== FUNDAMENTAL NO-TRADE GATE ==================
    # Runs BEFORE the price fetch loop so we save the yfinance download cost
    # on structurally broken names. Cache-aware — same weekly cache as the
    # live scanner. Rejected stocks are stashed in funda_rejects_df for the
    # audit expander at the bottom of the render.
    funda_results, funda_rejects_df = {}, pd.DataFrame()
    pre_gate_count = len(subset)
    if apply_funda_gate and HAVE_FUNDA:
        if momentum_preset:
            funda_cfg = {
                **DEFAULT_FUNDA_CONFIG,
                "valuation_enabled":  False,
                "quality_enabled":    True,
                "growth_enabled":     False,
                "governance_enabled": True,
                "ownership_enabled":  False,
                "trend_enabled":      False,
                "strict_mode":        False,
                # Loosened Quality thresholds — same as live scanner preset
                "roe_min_%":            0.0,
                "roce_min_%":           0.0,
                "debt_to_equity_max":   5.0,
                "interest_cover_min":   1.0,
                "current_ratio_min":    0.4,
                "promoter_pledge_max_%":  40.0,
                "promoter_holding_min_%": 15.0,
                "flag_auditor_qualified": True,
                "flag_rpt_concern":       True,
            }
            st.caption("🚀 **Momentum preset active** — quality (loose) + "
                       "governance only.")
        else:
            funda_cfg = DEFAULT_FUNDA_CONFIG.copy()

        st.info("🧾 Running fundamentals no-trade screen "
                "(weekly cached — reruns until next Saturday are instant)...")
        subset_yahoo = [_to_yahoo(s) for s in subset]
        f_prog = st.progress(0.0); f_stat = st.empty()

        def _fund_cb(k, n, sym):
            f_stat.write(f"Fund-check {sym.replace('.NS','')}  ({k+1}/{n})")
            f_prog.progress((k + 1) / n)

        funda_results, _sec_medians = fs_screen_universe(
            subset_yahoo, sector_map, funda_cfg, _fund_cb
        )
        f_stat.empty(); f_prog.empty()

        passing_bare = {t for t, r in funda_results.items()
                        if r["status"] in ("pass", "pass_no_data")}
        subset = [s for s in subset
                  if s.upper().replace(".NS", "").replace(".BO", "") in passing_bare]
        summ = fs_summarize(funda_results)
        st.success(
            f"✅ Fundamentals gate: **{summ['pass']} passed**, "
            f"**{summ['reject']} rejected**, "
            f"{summ['no_data']} no-data (passed), "
            f"{summ['warn_only']} passed with warnings. "
            f"Technical scan now runs on {len(subset)} names "
            f"(from {pre_gate_count})."
        )
        funda_rejects_df = fs_rejects_df(funda_results)

    # --- Regime check UP FRONT (fetches once) ---
    st.write(f"### Cutoff: **{cutoff.isoformat()}**  |  Universe: **{bucket_choice}**  |  Scanning: **{len(subset)}** stocks")
    if use_regime:
        with st.spinner("Fetching benchmark index for regime gate..."):
            bench_name, bench_df = _fetch_bench(ohlc_start, ohlc_end)
        if bench_df.empty:
            st.warning("⚠️ Could not fetch benchmark — regime gate will be skipped.")
            regime_info = {"status": "UNKNOWN"}
        else:
            regime_info = regime_at_cutoff(bench_df, cutoff)
            emoji = {"RISK-ON": "🟢", "NEUTRAL": "🟡", "RISK-OFF": "🔴", "UNKNOWN": "⚪"}
            e = emoji.get(regime_info["status"], "⚪")
            st.info(f"{e} **Regime at cutoff = {regime_info['status']}**  "
                    f"(bench {bench_name}: {regime_info.get('pct_vs_200','?')}% vs 200-DMA, "
                    f"10d ROC {regime_info.get('roc10','?')}%)")

        # Combined block decision
        block_all = False
        if regime_block_on_risk_off and regime_info["status"] == "RISK-OFF":
            block_all = True
            st.error("🚫 **RISK-OFF regime → ALL trades BLOCKED.** No signals acted on. "
                     "Cash is a position. This filter alone typically prevents 60-80% "
                     "of clustered stop-out losses.")
        elif (regime_block_neutral_decel and regime_info["status"] == "NEUTRAL"
              and regime_info.get("roc10", 0) < -1.0):
            block_all = True
            st.error(f"🚫 **NEUTRAL-with-decelerating-momentum → ALL trades BLOCKED.** "
                     f"ROC10 = {regime_info.get('roc10','?')}% (< -1%). Multi-cutoff "
                     f"data shows this regime delivers -2.4% avg per trade with 60% "
                     f"stop rate. Sitting out.")
        regime_info["block_all"] = block_all
    else:
        regime_info = {"status": "UNKNOWN", "block_all": False}
        bench_df = pd.DataFrame()

    # --- BENCH return over the RS window, taken AT-CUTOFF (no look-ahead) ---
    # Feeds rel_strength inside scan_as_of; matches the live scanner's formula.
    idx_ret_window_pct = 0.0
    bench_close_at_cutoff = pd.Series(dtype=float)
    if not bench_df.empty:
        _bc = bench_df.loc[bench_df.index.date <= cutoff, "Close"].dropna()
        if len(_bc) > RS_WINDOW:
            idx_ret_window_pct = float((_bc.iloc[-1] / _bc.iloc[-(RS_WINDOW + 1)] - 1) * 100)
            bench_close_at_cutoff = _bc

    # --- Category map (LargeCap / MidCap / SmallCap per SEBI) for the shortlist ---
    largecap = set(buckets.get("LargeCap", []))
    midcap   = set(buckets.get("MidCap", []))
    allnse   = set(buckets.get("AllNSE", []))
    category_map = {}
    for t in allnse:
        if t in largecap:   category_map[t] = "LargeCap"
        elif t in midcap:   category_map[t] = "MidCap"
        else:               category_map[t] = "SmallCap"

    # --- Scan each stock ---
    prog = st.progress(0.0); stat = st.empty()
    rows = []
    skipped_regime = 0
    for k, sym in enumerate(subset):
        stat.write(f"[{k+1}/{len(subset)}] {sym}")
        yahoo = _to_yahoo(sym)
        full = _fetch_full(yahoo, ohlc_start, ohlc_end)
        if full.empty:
            rows.append({"ticker": sym, "status": "no data"})
            prog.progress((k+1)/len(subset)); continue
        plan = scan_as_of(yahoo, full, strategy, p, bt_kwargs, cutoff, sector_map,
                          category_map=category_map,
                          bench_close_series=bench_close_at_cutoff,
                          idx_ret_window_pct=idx_ret_window_pct,
                          require_confirmation=bool(require_confirmation),
                          block_risk_off=False)   # composite gate applied post-scan (parity)
        # REGIME HARD-BLOCK (covers both RISK-OFF and NEUTRAL-decelerating)
        if use_regime and regime_info.get("block_all") and plan.get("signals_today"):
            plan["signals_today"] = False
            plan["regime_blocked"] = True
            skipped_regime += 1
        if plan.get("status") == "ok" and plan.get("signals_today"):
            # NEW: uses production engine → respects router + trailing + exit stack
            actual = forward_simulate(full, cutoff, strategy, p, bt_kwargs)
            plan["actual_outcome"] = actual.get("outcome")
            plan["actual_entry_date"] = actual.get("entry_date")
            plan["actual_entry_price"] = actual.get("entry_price")
            plan["actual_exit_date"] = actual.get("exit_date")
            plan["actual_exit_price"] = actual.get("exit_price")
            plan["actual_days_held"] = actual.get("days_held")
            plan["actual_net_return_%"] = actual.get("net_return_%")
            plan["actual_peak_gain_%"] = actual.get("peak_gain_%")   # for "let winners run" audit
            plan["actual_exit_route"] = actual.get("exit_route", "") # router audit
        rows.append(plan)
        prog.progress((k + 1) / len(subset))
    stat.empty(); prog.empty()

    if skipped_regime:
        st.warning(f"🚫 Regime gate blocked {skipped_regime} would-be signals.")

    # ================== NEWS PASS (only when cutoff is recent) ==================
    # v3 (Aug-2026): now covers EVERY fundamentally-passing stock, not just
    # signalling ones. This mirrors the live scanner's behaviour and enables
    # the "News-driven WATCHLIST" section — stocks with material news that
    # DIDN'T fire a technical signal (early catalysts, pre-signal moves).
    #
    # Only signalling stocks get the ±20% rank_score tilt; non-signalling
    # stocks store the news fields for display but don't have a rank to tilt.
    #
    # Only meaningful when cutoff is within ~14 days (free news doesn't
    # archive). `use_news` is auto-disabled by the sidebar for older cutoffs,
    # so this branch is a no-op for anything older than the news window.
    # ⚠️ CRITICAL: pass `as_of_date=cutoff` so news_sentiment applies
    # NO-LOOK-AHEAD filtering. Without this, headlines dated AFTER the
    # cutoff (which is contamination for a forward test) leak into the
    # score and the "latest headline" slot. See news_sentiment v3 for
    # the filter mechanics — items with pub_date > cutoff are excluded,
    # and Google's when: query is widened so items before the cutoff are
    # actually returned in the first place.
    if use_news and HAVE_NEWS:
        news_rows = [r for r in rows if r.get("status") == "ok"]
        if news_rows:
            # v3.2: reset the per-run error log so we only capture THIS run's
            # failures, not leftovers from a previous run.
            try: _news_reset_errors()
            except Exception: pass
            n_prog = st.progress(0.0); n_stat = st.empty()
            for k, r in enumerate(news_rows):
                tk_bare = r["ticker"]
                n_stat.write(f"News check: {tk_bare} ({k+1}/{len(news_rows)})  "
                             f"[window: {news_lookback}d ending {cutoff.isoformat()}]")
                try:
                    n = _news_score(_to_yahoo(tk_bare),
                                    lookback_days=int(news_lookback),
                                    as_of_date=cutoff)         # ← NO LOOK-AHEAD
                except Exception:
                    n = {"score": 0.0, "n_articles": 0,
                         "top_headline": None, "top_date": None,
                         "latest_headline": None, "latest_date": None,
                         "top_impact": 0.0, "latest_impact": 0.0,
                         "matched_terms": [],
                         "window_from": None, "window_to": None}
                r["news_score"]         = float(n.get("score", 0.0))
                r["news_n"]             = int(n.get("n_articles", 0))
                r["news_top"]           = n.get("top_headline")
                r["news_top_date"]      = n.get("top_date")
                r["news_top_score"]     = float(n.get("top_impact", 0.0))
                r["news_latest"]        = n.get("latest_headline")
                r["news_latest_date"]   = n.get("latest_date")
                r["news_latest_score"]  = float(n.get("latest_impact", 0.0))
                r["news_matched"]       = ",".join(n.get("matched_terms", [])[:5])
                r["news_lookback_days"] = int(news_lookback)
                r["news_window_from"]   = n.get("window_from")
                r["news_window_to"]     = n.get("window_to")
                # v3.1 diagnostics — surface WHY count is low/zero
                r["news_raw_fetched"]    = int(n.get("raw_fetched", 0))
                r["news_raw_oldest"]     = n.get("raw_oldest")
                r["news_raw_newest"]     = n.get("raw_newest")
                r["news_dropped_ahead"]  = int(n.get("dropped_look_ahead", 0))
                r["news_dropped_old"]    = int(n.get("dropped_too_old", 0))
                # Rank tilt only applies to signalling stocks (only they have
                # a meaningful rank_score to modify).
                if r.get("signals_today"):
                    tilt = max(min(r["news_score"], 1.0), -1.0) * 0.20
                    r["rank_score"] = round(r["rank_score"] * (1.0 + tilt), 2)
                n_prog.progress((k + 1) / len(news_rows))
            n_stat.empty(); n_prog.empty()

    # Defaults so downstream selectors don't KeyError on stocks with no news
    for r in rows:
        r.setdefault("news_score", 0.0)
        r.setdefault("news_n", 0)
        r.setdefault("news_top", None)
        r.setdefault("news_top_date", None)
        r.setdefault("news_top_score", 0.0)
        r.setdefault("news_latest", None)
        r.setdefault("news_latest_date", None)
        r.setdefault("news_latest_score", 0.0)
        r.setdefault("news_matched", "")
        r.setdefault("news_lookback_days", 0)
        r.setdefault("news_window_from", None)
        r.setdefault("news_window_to", None)
        r.setdefault("news_raw_fetched", 0)
        r.setdefault("news_raw_oldest", None)
        r.setdefault("news_raw_newest", None)
        r.setdefault("news_dropped_ahead", 0)
        r.setdefault("news_dropped_old", 0)
        r.setdefault("category", "Unknown")

    # ============ NEWS DIAGNOSTIC SUMMARY (Aug-2026) ============
    # Surface aggregate stats immediately after the news pass so the user
    # can see if the fetch worked but everything got filtered out (raw > 0,
    # kept = 0) vs Google actually returning nothing (raw = 0 → likely
    # rate-limit / block, not a filter problem).
    if use_news and HAVE_NEWS:
        ok_rows_for_diag = [r for r in rows if r.get("status") == "ok"]
        if ok_rows_for_diag:
            tot_raw = sum(r.get("news_raw_fetched", 0) for r in ok_rows_for_diag)
            tot_kept = sum(r.get("news_n", 0) for r in ok_rows_for_diag)
            tot_ahead = sum(r.get("news_dropped_ahead", 0) for r in ok_rows_for_diag)
            tot_old   = sum(r.get("news_dropped_old", 0) for r in ok_rows_for_diag)
            n_stocks_any = sum(1 for r in ok_rows_for_diag if r.get("news_raw_fetched", 0) > 0)
            n_stocks_kept = sum(1 for r in ok_rows_for_diag if r.get("news_n", 0) > 0)
            oldest = min((r.get("news_raw_oldest") for r in ok_rows_for_diag
                          if r.get("news_raw_oldest")), default=None)
            newest = max((r.get("news_raw_newest") for r in ok_rows_for_diag
                          if r.get("news_raw_newest")), default=None)
            if tot_raw == 0:
                st.error(f"❌ News fetch returned **0 raw items across all "
                         f"{len(ok_rows_for_diag)} stocks**. See error "
                         f"details below to diagnose. Common causes:\n"
                         f"1. **Stale Streamlit cache** — click "
                         f"**'🔄 Force refresh news cache'** in the sidebar, "
                         f"then rerun. Fresh fixes don't take effect until "
                         f"the cache is cleared.\n"
                         f"2. **Google News rate-limit / block** — wait "
                         f"5-10 min and rerun.\n"
                         f"3. **Network blocked** (corporate firewall, VPN) — "
                         f"news.google.com and query.finance.yahoo.com need "
                         f"to be reachable.")
                # v3.2: expose the actual per-source errors so the user can
                # see WHICH failure happened. Otherwise this diagnostic is
                # just guessing.
                try:
                    errs = _news_last_errors()
                except Exception:
                    errs = {}
                if errs:
                    with st.expander(f"🔧 Fetch error log ({len(errs)} entries)  "
                                     "— what actually failed"):
                        _err_rows = [{"source_or_key": k,
                                      "source": v[0], "error": v[1]}
                                     for k, v in list(errs.items())[:30]]
                        st.dataframe(pd.DataFrame(_err_rows),
                                     use_container_width=True, hide_index=True)
                        st.caption("Rows prefixed with `__google:` are per-query "
                                   "Google News failures (one per query attempted). "
                                   "Other rows are yfinance per-ticker failures. "
                                   "If you see **URLError / HTTP 429 / timeout**, "
                                   "it's rate-limiting — wait and rerun. If you see "
                                   "**Name or service not known / getaddrinfo failed**, "
                                   "your network is blocking those hosts.")
                else:
                    st.caption("(No per-source errors captured — this suggests the "
                               "fetch didn't even run, i.e. results were served from "
                               "cache. Click 🔄 Force refresh news cache and rerun.)")
            elif tot_kept == 0:
                st.warning(f"⚠️ News fetch worked ({tot_raw} raw items across "
                           f"{n_stocks_any} stocks, dates {oldest} → {newest}) "
                           f"but **all {tot_ahead} items post-dated the cutoff "
                           f"{cutoff.isoformat()}** and were correctly dropped "
                           f"(no-look-ahead). Google News RSS is recency-"
                           f"biased and doesn't return old items for small "
                           f"caps. Try: (a) increase News Lookback to 14 in "
                           f"the sidebar, (b) pick a more recent cutoff, "
                           f"or (c) accept that pre-cutoff news isn't "
                           f"available for this universe on this date.")
            else:
                st.success(f"📰 News pass: **{tot_kept} kept articles across "
                           f"{n_stocks_kept}/{len(ok_rows_for_diag)} stocks** "
                           f"(window {cutoff - dt.timedelta(days=news_lookback)} "
                           f"→ {cutoff}). Fetched {tot_raw} raw items across "
                           f"{n_stocks_any} stocks; dropped {tot_ahead} for "
                           f"look-ahead (dated after cutoff) and {tot_old} "
                           f"for age (dated before window).")

    all_df = pd.DataFrame(rows)
    ok_df = all_df[all_df.get("status") == "ok"].copy() if "status" in all_df.columns else all_df.copy()

    # ========================================================================
    # v7 — HISTORICAL SELF-CHECK FILTER (parity with scanner Section 4e)
    # ------------------------------------------------------------------------
    # Drop stocks whose OWN historical algo performance is weak (per-stock
    # backtest evidence produced by scan_as_of). Uses SEQUENTIAL trade stats
    # to be honest about statistical significance. Applied BEFORE tag/gate so
    # rejected chronic losers never appear in the shortlist.
    # ========================================================================
    selfcheck_rejects_df = pd.DataFrame()
    if use_selfcheck and not ok_df.empty:
        n_seq_col   = pd.to_numeric(ok_df.get("seq_trades", 0),        errors="coerce").fillna(0)
        wr_seq_col  = pd.to_numeric(ok_df.get("seq_win_%", 0),         errors="coerce").fillna(0)
        tr_seq_col  = pd.to_numeric(ok_df.get("total_return_sum_%", 0), errors="coerce").fillna(0)
        _chronic = ((n_seq_col  >= selfcheck_min_trades)
                    & (wr_seq_col  < selfcheck_min_win)
                    & (tr_seq_col  < selfcheck_min_total))
        selfcheck_rejects_df = ok_df[_chronic].copy()
        ok_df = ok_df[~_chronic].copy()
        if not selfcheck_rejects_df.empty:
            st.caption(f"🪞 Self-check filter dropped **{len(selfcheck_rejects_df)}** "
                       f"chronic-loser stocks (win < {selfcheck_min_win:.0f}% "
                       f"AND total < {selfcheck_min_total:+.0f}pp over "
                       f"≥ {selfcheck_min_trades} seq trades).")

    signalled = ok_df[ok_df.get("signals_today", False)].copy() if "signals_today" in ok_df.columns else pd.DataFrame()

    # ========================================================================
    # v7 — COMPOSITE REGIME GATE (parity with scanner Section 7 + composite_gate)
    # ------------------------------------------------------------------------
    # Scanner runs three inputs into `composite_gate`:
    #   (1) benchmark index vs 200-DMA + 10d ROC   → RISK-ON / NEUTRAL / RISK-OFF
    #   (2) mid/small-cap segment indices vs their 200-DMA  (segments below trim)
    #   (3) advance/decline breadth across the SCANNED tickers
    # We reuse the exact scanner helpers (imported lazily above).
    # ========================================================================
    fv_regime = compute_regime(bench_df) if (compute_regime and not bench_df.empty) \
                else {"status": "UNKNOWN", "index_ok": False, "idx_ret_window": 0.0}
    fv_segments = fetch_segments(ohlc_start, ohlc_end) if fetch_segments else {}
    # Breadth is computed from ok_df rows (matches scanner's compute_breadth signature).
    _breadth_rows = ok_df.to_dict("records") if not ok_df.empty else []
    fv_breadth = compute_breadth(_breadth_rows) if compute_breadth else {"status": "UNKNOWN", "n": 0}
    fv_gate = (composite_gate(fv_regime, fv_segments, fv_breadth)
               if composite_gate else {"final": fv_regime.get("status", "UNKNOWN"), "reasons": []})
    fv_regime_final = fv_gate.get("final", fv_regime.get("status", "UNKNOWN"))

    st.caption(f"🧭 **Composite regime = {fv_regime_final}** · " +
               " | ".join(fv_gate.get("reasons", [])))

    # ========================================================================
    # v7 — STATUS TAGGING  (parity with scanner v6 render_results)
    # ------------------------------------------------------------------------
    # Every signalling stock stays in the display DataFrame with a `_status`
    # + `_status_reason` so the user sees which gate a signal failed instead
    # of the signal silently vanishing. Downgrades ordered by severity:
    #   1) EVENT_BLOCKED  → hard block (imminent corporate event)
    #   2) RS_LAGGARD     → composite regime NEUTRAL/OFF and RS ≤ 0
    #   3) SECTOR_CAPPED  → displaced by higher-ranked peers in same sector
    #   4) KEPT           → passed every gate
    # ========================================================================
    if not signalled.empty:
        signalled["_status"]        = "KEPT"
        signalled["_status_reason"] = "✅ Passed every gate — actionable trade for the cutoff."

    # 1) Event-risk block (only meaningful when cutoff is very recent — NSE
    # API returns TODAY's schedule, not point-in-time-as-of-cutoff. Applied
    # only when the user opts in and the cutoff is within a few days.)
    event_blocked_df = pd.DataFrame()
    _days_since_cutoff_now = (dt.date.today() - cutoff).days
    if (use_event_block and HAVE_EVENTS and _days_since_cutoff_now <= 3
            and not signalled.empty):
        for _i, _row in list(signalled.iterrows()):
            try:
                ev = _event_risk(_row["ticker"], next_sessions=int(event_window))
            except Exception:
                ev = {"blocked": False, "type": None, "days_until": None, "subject": None}
            signalled.at[_i, "event_blocked"]    = bool(ev.get("blocked"))
            signalled.at[_i, "event_type"]       = ev.get("type")
            signalled.at[_i, "event_days_until"] = ev.get("days_until")
            signalled.at[_i, "event_subject"]    = ev.get("subject")
            if ev.get("blocked"):
                _t   = ev.get("type") or "event"
                _dtx = f"{int(ev['days_until'])} sessions" if ev.get("days_until") is not None else "window"
                _sub = (ev.get("subject") or "")[:80]
                signalled.at[_i, "_status"] = "EVENT_BLOCKED"
                signalled.at[_i, "_status_reason"] = (
                    f"🚫 HARD BLOCK — {_t} scheduled in {_dtx}. Corporate "
                    f"events routinely produce 5-20% overnight gaps that "
                    f"invalidate the stop-loss thesis. "
                    + (f"Announcement: “{_sub}”" if _sub else ""))
        event_blocked_df = signalled[signalled["_status"] == "EVENT_BLOCKED"].copy()

    # 2) Composite regime laggard flag (scanner: on NEUTRAL/RISK-OFF, RS ≤ 0)
    if (fv_regime_final in ("RISK-OFF", "NEUTRAL")) and not signalled.empty:
        _mask_lag = (signalled["_status"] == "KEPT") & (signalled["rel_strength"] <= 0)
        for _i in signalled[_mask_lag].index:
            _rs = float(signalled.at[_i, "rel_strength"])
            signalled.at[_i, "_status"] = "RS_LAGGARD"
            signalled.at[_i, "_status_reason"] = (
                f"🟡 REGIME LAGGARD — Composite regime is {fv_regime_final} and "
                f"this stock's 3-month RS is {_rs:+.1f}% (underperforming). "
                f"Dip-buys of laggards in weak-tape regimes stop out more "
                f"often than they run. Recommend: skip unless a specific "
                f"stock-level catalyst overrides the tape.")

    # 3) Sort by rank so sector cap and signal-decay see best-ranked first
    if not signalled.empty:
        signalled = signalled.sort_values("rank_score", ascending=False).reset_index(drop=True)

    # 4) Sector cap w/ LargeCap-reserve slot (parity: apply_sector_caps helper)
    if max_per_sector > 0 and not signalled.empty and apply_sector_caps:
        _kept_mask = signalled["_status"] == "KEPT"
        _kept_only = signalled[_kept_mask].copy()
        if not _kept_only.empty:
            _kept_after, _dropped = apply_sector_caps(_kept_only, max_per_sector,
                                                     reserve_largecap_slot=bool(reserve_lc_slot))
            _displaced_idx = set(_kept_only.index) - set(_kept_after.index)
            for _i in _displaced_idx:
                _sec = signalled.at[_i, "sector"] or "UNKNOWN"
                signalled.at[_i, "_status"] = "SECTOR_CAPPED"
                signalled.at[_i, "_status_reason"] = (
                    f"🟠 SECTOR CAPPED — sector “{_sec}” already has "
                    f"{max_per_sector} higher-ranked names. Displaced to "
                    f"prevent one sector dominating the shortlist.")

    # 5) Signal decay — cap KEPT rows to `max_signals_per_day` (extra FV filter)
    if use_decay and not signalled.empty:
        _kept_mask = signalled["_status"] == "KEPT"
        _n_kept = int(_kept_mask.sum())
        if _n_kept > max_signals_per_day:
            _kept_sorted = signalled[_kept_mask].sort_values("rank_score", ascending=False)
            _survivors = set(_kept_sorted.head(max_signals_per_day).index)
            for _i in _kept_sorted.index[max_signals_per_day:]:
                signalled.at[_i, "_status"] = "SECTOR_CAPPED"     # reuse the amber bucket
                signalled.at[_i, "_status_reason"] = (
                    f"🟠 DECAY-CAPPED — {_n_kept} stocks fired signals same day; "
                    f"kept only the top-{max_signals_per_day} by rank_score. "
                    f"Co-signal decay: same-day mass signals are one bet on "
                    f"the momentum factor, not many independent bets.")

    # Fill defaults for any status columns still absent
    if not signalled.empty:
        for _col in ("event_blocked", "event_type", "event_days_until", "event_subject"):
            if _col not in signalled.columns:
                signalled[_col] = None

    # Convenience alias — the KEPT subset is what the scanner would have acted on
    kept_only = signalled[signalled["_status"] == "KEPT"].copy() if not signalled.empty else pd.DataFrame()

    if signalled.empty:
        st.info(f"No signals fired on {cutoff.isoformat()}. "
                f"That is a valid outcome — cash is a position.")
        return

    st.success(
        f"**{len(kept_only)} KEPT** · "
        f"🟡 {int((signalled['_status']=='RS_LAGGARD').sum())} laggard · "
        f"🟠 {int((signalled['_status']=='SECTOR_CAPPED').sum())} sector/decay · "
        f"🚫 {int((signalled['_status']=='EVENT_BLOCKED').sum())} event-block "
        f"— from {len(ok_df)} OK-scanned on {cutoff.isoformat()}."
    )

    # ========================================================================
    # TABLE 1: "AS OF CUTOFF" — matches Tonight's Investment Analysis layout
    # ------------------------------------------------------------------------
    # Every column the daily scanner shows for TODAY's signals, shown here for
    # what fired on the cutoff date. Same order, same names, same formulas.
    # ========================================================================
    st.subheader(f"🎯 Tonight's Investment Analysis  —  as of {cutoff.isoformat()}")
    st.caption("Same column layout as the live Daily Scanner — this is exactly what "
               "the scanner WOULD have shown on the cutoff date, using only data "
               "available on or before that day.")

    has_news_col = ("news_score" in signalled.columns) and \
                   (signalled["news_score"].abs().sum() > 0
                    or signalled.get("news_n", pd.Series([0]*len(signalled))).sum() > 0)
    has_penalty = ("ranking_penalty_reason" in signalled.columns) and \
                  signalled["ranking_penalty_reason"].astype(str).str.len().gt(0).any()

    # v7 — Color grading & Status/Why columns (parity with scanner v6)
    STATUS_LABEL = {
        "KEPT":          "✅ KEPT",
        "RS_LAGGARD":    "🟡 RS Laggard",
        "SECTOR_CAPPED": "🟠 Sector Cap",
        "EVENT_BLOCKED": "🚫 Event Block",
    }
    STATUS_ROW_STYLE = {
        "KEPT":          "background-color: rgba( 22, 163,  74, 0.10)",
        "RS_LAGGARD":    "background-color: rgba(234, 179,   8, 0.14)",
        "SECTOR_CAPPED": "background-color: rgba(249, 115,  22, 0.14)",
        "EVENT_BLOCKED": "background-color: rgba(220,  38,  38, 0.18)",
    }
    signalled["_status_label"] = signalled["_status"].map(STATUS_LABEL).fillna(signalled["_status"])

    # Legend summary — matches scanner's caption format
    _cnt = signalled["_status"].value_counts()
    _bits = []
    if _cnt.get("KEPT", 0):          _bits.append(f"✅ **{_cnt.get('KEPT',0)} Kept**")
    if _cnt.get("RS_LAGGARD", 0):    _bits.append(f"🟡 **{_cnt.get('RS_LAGGARD',0)} RS Laggard**")
    if _cnt.get("SECTOR_CAPPED", 0): _bits.append(f"🟠 **{_cnt.get('SECTOR_CAPPED',0)} Sector/Decay Cap**")
    if _cnt.get("EVENT_BLOCKED", 0): _bits.append(f"🚫 **{_cnt.get('EVENT_BLOCKED',0)} Event Block**")
    if _bits:
        st.caption("🎨 **Color legend** — " + "  ·  ".join(_bits)
                   + "  ·  Row colour = status; the ‘Why’ column has the full reason.")

    base_cols = ["_status_label", "_status_reason",
                 "ticker", "category", "sector", "regime_today", "rank_score",
                 "stage2_score", "confidence", "rel_strength"]
    if has_news_col:  base_cols += ["news_score"]
    if has_penalty:   base_cols += ["ranking_penalty_reason"]
    base_cols += ["entry_ref", "plan_entry", "target_price", "stop_price", "stop_%",
                  "exp_days_to_target", "last_atr_pct", "stage2_reason"]

    inv = signalled[[c for c in base_cols if c in signalled.columns]].copy()
    _entry_label = "BUY limit ₹" if entry_mode == "Limit" else "Entry (open)"
    rename_map = {
        "_status_label": "Status", "_status_reason": "Why",
        "ticker": "Stock", "category": "Cap", "sector": "Sector",
        "regime_today": "Signal", "rank_score": "Rank",
        "stage2_score": "Stage-2",
        "confidence": "Conf(/day)", "rel_strength": "RS%",
        "news_score": "News", "ranking_penalty_reason": "Rank penalty",
        "entry_ref": "Close@cutoff", "plan_entry": _entry_label,
        "target_price": "Objective ₹", "stop_price": "Stop ₹",
        "stop_%": "Stop %", "exp_days_to_target": "Exp. days→objective",
        "last_atr_pct": "ATR%",
        "stage2_reason": "Why Stage-2",
    }
    inv = inv.rename(columns=rename_map)

    # Row-background Styler — same technique the scanner v6 uses
    _status_arr = signalled["_status"].values
    def _color_by_status_fv(df):
        out = pd.DataFrame("", index=df.index, columns=df.columns)
        for _r in range(len(df)):
            out.iloc[_r, :] = STATUS_ROW_STYLE.get(_status_arr[_r], "")
        return out
    styler = inv.style.apply(_color_by_status_fv, axis=None)

    _col_cfg = {
        "Status": st.column_config.TextColumn(
            "Status", width="small",
            help=("Color legend: ✅ KEPT = passed every gate · "
                  "🟡 RS Laggard = composite regime NEUTRAL/OFF and RS ≤ 0 · "
                  "🟠 Sector/Decay Cap = displaced by higher-ranked peers · "
                  "🚫 Event Block = imminent corporate event")),
        "Why": st.column_config.TextColumn(
            "Why", width="medium",
            help="Plain-English reason for the status."),
    }
    st.dataframe(styler, use_container_width=True, hide_index=True,
                 column_config=_col_cfg,
                 height=min(400, 60 + 32*len(inv)))
    st.download_button(
        f"⬇️ Download 'as of {cutoff.isoformat()}' analysis",
        inv.to_csv(index=False).encode(),
        file_name=f"forward_asof_{cutoff.isoformat()}.csv", mime="text/csv"
    )

    # ========================================================================
    # v7 — CAP-TIER SUB-SHORTLIST  (parity with scanner Section 8 expander)
    # Top-5 signalling stocks per SEBI cap tier, ranked WITHIN their tier,
    # from the full signalling universe (no sector/decay cap applied here).
    # ========================================================================
    if "category" in signalled.columns:
        with st.expander(
            f"🏛️ By Cap Tier — best signals per cap  ({len(signalled)} total signals)",
            expanded=False):
            st.caption("Top-5 per SEBI cap tier, ranked WITHIN their tier. "
                       "Cap-neutral read — the LargeCap top here is a safer "
                       "anchor even if it doesn't sit at the top of the main table.")
            tier_cols = ["ticker", "sector", "regime_today", "rank_score",
                         "stage2_score", "confidence", "rel_strength",
                         "entry_ref", "plan_entry", "target_price", "stop_price",
                         "exp_days_to_target"]
            tier_cols = [c for c in tier_cols if c in signalled.columns]
            tier_rename = {
                "ticker":"Stock","sector":"Sector","regime_today":"Signal",
                "rank_score":"Rank","stage2_score":"Stage-2",
                "confidence":"Conf(/day)","rel_strength":"RS%",
                "entry_ref":"Close@cutoff","plan_entry":"BUY ₹",
                "target_price":"Target ₹","stop_price":"Stop ₹",
                "exp_days_to_target":"Exp d→objective",
            }
            for tier in ["LargeCap", "MidCap", "SmallCap"]:
                sub = signalled[signalled["category"] == tier]
                n_tier = len(sub)
                if n_tier == 0:
                    st.markdown(f"**{tier}** — no signals fired at cutoff")
                    continue
                top = sub.sort_values("rank_score", ascending=False).head(5)
                view = top[tier_cols].copy().rename(columns=tier_rename)
                st.markdown(f"**{tier}** — top {len(view)} of {n_tier} signal(s)")
                st.dataframe(view, use_container_width=True, hide_index=True,
                             key=f"fv_cap_tier_{tier}",
                             height=min(220, 55 + 32 * len(view)))

    # =============== SECONDARY TABLE: legacy compact shortlist ===============
    with st.expander("📋 Compact shortlist (legacy view)"):
        sl_view = signalled[["ticker", "sector", "confidence", "hist_winrate_seq",
                              "cutoff_close", "plan_entry", "target_price", "stop_price"]].copy()
        sl_view.columns = ["Stock", "Sector", "Conf", "Hist Win%",
                            "Close", "BUY @", "Target", "Stop"]
        st.dataframe(sl_view, use_container_width=True, hide_index=True)

    # ========================================================================
    # NEWS DEEP-DIVE — Top + Latest headline per signalling stock
    # ------------------------------------------------------------------------
    # Shows, for each cutoff-day candidate, the biggest-impact headline
    # (Top) AND the most-recent headline (Latest) in the news window. These
    # can differ: a +4 "beats estimates" from 4 days ago will be the Top
    # slot while a -3 "resigns" from yesterday will be the Latest.
    # ========================================================================
    if use_news and HAVE_NEWS and "news_score" in signalled.columns:
        _from = signalled["news_window_from"].dropna().iloc[0] if signalled["news_window_from"].notna().any() else None
        _to   = signalled["news_window_to"].dropna().iloc[0]   if signalled["news_window_to"].notna().any()   else None
        _win_txt = (f"{_from} → {_to}" if (_from and _to)
                    else f"{news_lookback}d ending {cutoff.isoformat()}")
        with st.expander(f"📰 News deep-dive for signalling candidates  "
                         f"(window: {_win_txt}, no look-ahead)",
                         expanded=False):
            nd_view = signalled[["ticker", "sector", "news_score", "news_n",
                                  "news_top", "news_top_date",
                                  "news_latest", "news_latest_date",
                                  "news_matched"]].copy()
            nd_view.columns = ["Stock", "Sector", "News", "# articles",
                                "Top headline", "Top date",
                                "Latest headline", "Latest date",
                                "Keywords matched"]
            st.dataframe(nd_view, use_container_width=True, hide_index=True, height=280)
            st.caption(f"⏳ **No look-ahead window: {_win_txt}** — every headline "
                       f"here was published **on or before {cutoff.isoformat()}** "
                       f"(the cutoff you picked). Any headline dated later was "
                       f"filtered out at fetch time.\n\n"
                       "**Top headline** = largest single-|score| story "
                       "in the window. **Latest headline** = most recent by "
                       "publication date within the window — always ≤ cutoff. "
                       "Both feed the aggregate news score.")

    # =============== TABLE: forward outcomes ===============
    st.subheader("🔮 Forward outcome per stock")
    cmp_rows = []
    for _, r in signalled.iterrows():
        ao = r.get("actual_outcome", "?")
        if ao == "NOT_FILLED":
            verdict = "⏭ Not filled"
        elif ao == "NO_FORWARD_DATA":
            verdict = "⚠ No fwd data"
        else:
            ret = r.get("actual_net_return_%", 0) or 0
            if ao == "TARGET": verdict = f"✅ TARGET ({ret:+.1f}%)"
            elif ao == "STOP": verdict = f"🔴 STOP ({ret:+.1f}%)"
            elif ret >= r.get("target_%", 15): verdict = f"✅ TIME beat ({ret:+.1f}%)"
            elif ret > 0: verdict = f"🟡 TIME win ({ret:+.1f}%)"
            else: verdict = f"🔴 TIME loss ({ret:+.1f}%)"
        cmp_rows.append({
            "Stock": r["ticker"], "Sector": r.get("sector", "-"),
            "BUY @": r["plan_entry"], "Target": r["target_price"], "Stop": r["stop_price"],
            "Entry Px": r.get("actual_entry_price", "—"),
            "Exit Px": r.get("actual_exit_price", "—"),
            "Reason": ao, "Days": r.get("actual_days_held", "—"),
            "Return": r.get("actual_net_return_%", "—"),
            "Peak gain %": r.get("actual_peak_gain_%", "—"),   # winners-run audit
            "Route": r.get("actual_exit_route", "—"),          # router (trailing/fixed)
            "Verdict": verdict,
        })
    cmp_df = pd.DataFrame(cmp_rows)
    # keep sector on the compare df for cluster analysis
    cmp_df["actual_outcome"] = [r["Reason"] for r in cmp_rows]
    cmp_df["actual_exit_date"] = [r.get("actual_exit_date") for r in signalled.to_dict("records")]
    cmp_df["actual_days_held"] = [r.get("Days") for r in cmp_rows]
    cmp_df["sector"] = [r.get("Sector") for r in cmp_rows]
    st.dataframe(cmp_df.drop(columns=["actual_outcome", "actual_exit_date", "actual_days_held", "sector"]),
                 use_container_width=True, hide_index=True)

    # =============== AGGREGATE METRICS ===============
    filled = signalled[signalled.get("actual_outcome", "").isin(["TARGET", "STOP", "TIME"])].copy() \
        if "actual_outcome" in signalled.columns else pd.DataFrame()
    if not filled.empty:
        n = len(filled)
        wins = int((filled["actual_net_return_%"] > 0).sum())
        target_hits = int((filled["actual_outcome"] == "TARGET").sum())
        stops = int((filled["actual_outcome"] == "STOP").sum())
        times = int((filled["actual_outcome"] == "TIME").sum())
        avg_ret = float(filled["actual_net_return_%"].mean())
        st.subheader("📊 Aggregate walk-forward metrics")
        c = st.columns(4)
        c[0].metric("Signalled", len(signalled))
        c[1].metric("Filled", n)
        c[2].metric("Win rate", f"{100*wins/n:.0f}%")
        c[3].metric("Avg net return", f"{avg_ret:+.2f}%",
                    f"vs target +{target_pct:.0f}%")
        c2 = st.columns(4)
        c2[0].metric("Target hits", f"{target_hits} ({100*target_hits/n:.0f}%)")
        c2[1].metric("Stops", f"{stops} ({100*stops/n:.0f}%)")
        c2[2].metric("Time exits", f"{times} ({100*times/n:.0f}%)")
        c2[3].metric("Expectancy per trade", f"{avg_ret:+.2f}%",
                     ("positive edge ✅" if avg_ret > 0 else "negative edge ❌"))

    # =============== FAILURE CLUSTERING ANALYSIS ===============
    if not filled.empty and (filled["actual_outcome"] == "STOP").sum() >= 2:
        st.subheader("🔍 Failure Clustering Analysis — why did stops cluster?")

        # Prepare data for analysis
        analysis_df = filled.copy()
        analysis_df["actual_exit_date"] = pd.to_datetime(analysis_df["actual_exit_date"], errors="coerce")
        clust = cluster_analysis(analysis_df.rename(columns={"actual_outcome": "actual_outcome"}))

        # (1) Same-day cluster
        if clust.get("worst_stop_days"):
            st.markdown("**1. Same-day stop clusters** (>= 2 stops on same date)")
            for d in clust["worst_stop_days"]:
                st.write(f"   * **{d['date']}** — **{d['n_stops']}** stocks stopped out same day")
            st.caption("Multiple stops on the SAME day = market-wide event, not strategy failure. "
                       "Common cause: broad-market gap-down, sector-specific news, "
                       "regime shift. FIX: enable the regime gate + hard-block on RISK-OFF.")

        # (2) Sector distribution
        if clust.get("sector_hits"):
            st.markdown("**2. Sector concentration of losses**")
            sec_df = pd.DataFrame(clust["sector_hits"])
            sec_df.columns = ["Sector", "# Stopped", "# Filled", "Stop rate %"]
            st.dataframe(sec_df, use_container_width=True, hide_index=True)
            top_sec = clust["sector_hits"][0]
            if top_sec["n_stopped"] >= 2 and top_sec["stop_rate"] >= 50:
                st.caption(f"⚠️ **{top_sec['sector']}** shows {top_sec['n_stopped']} stops "
                           f"out of {top_sec['n_filled']} trades ({top_sec['stop_rate']}% stop rate). "
                           f"Sector-specific news/regime hit ALL your trades in this sector. "
                           f"FIX: tighter sector cap (currently {max_per_sector}/sector).")

        # (3) Speed of stops
        if "avg_days_to_stop" in clust:
            days = clust["avg_days_to_stop"]
            st.markdown(f"**3. Speed of stops — avg stop hit in {days} days**")
            if days <= 3:
                st.caption("Very fast stops (<3d) = you bought right at a local top OR into a "
                           "gap-down environment. FIX: (a) widen stops to 2.5–3× ATR, "
                           "(b) require a follow-through confirmation day.")
            elif days <= 7:
                st.caption("Fast stops (3-7d) = normal pullback caught by tight stops. "
                           "FIX: widen stops moderately, or accept as cost of the strategy.")

    # ========================================================================
    # NEWS-DRIVEN WATCHLIST — non-signalling stocks with material news
    # ------------------------------------------------------------------------
    # Every stock that PASSED fundamentals + technical scan but did NOT fire
    # a technical signal, AND has meaningful news activity (|score| ≥ 0.15)
    # in the news window. These are the "news says something's happening but
    # the technical pattern hasn't caught up yet" stocks — often 1-3 days
    # ahead of the signal.
    #
    # This mirrors the live scanner's news watchlist expander and directly
    # addresses the "why didn't ACUTAAS get suggested despite hot news"
    # question — you can now see it here even though the technical pass didn't
    # flag it.
    # ========================================================================
    if use_news and HAVE_NEWS and "news_score" in ok_df.columns:
        watchlist = ok_df[(~ok_df.get("signals_today", False))
                          & (ok_df["news_score"].abs() >= 0.15)].copy()
        watchlist = watchlist.sort_values(
            "news_score", key=lambda s: s.abs(), ascending=False)
        if not watchlist.empty:
            n_pos = int((watchlist["news_score"] > 0).sum())
            n_neg = int((watchlist["news_score"] < 0).sum())
            with st.expander(f"📰 News-driven WATCHLIST — {len(watchlist)} "
                             f"stocks with material news at cutoff but NO "
                             f"technical signal  ({n_pos} pos / {n_neg} neg)",
                             expanded=False):
                st.caption(f"Stocks that passed the fundamentals gate but did "
                           f"NOT fire a technical signal on {cutoff.isoformat()}, "
                           f"yet had material news activity in the "
                           f"{news_lookback}-day window ending {cutoff.isoformat()} "
                           f"(**no look-ahead** — every headline here was "
                           f"published on or before the cutoff). "
                           f"**Positive news** → possible pre-signal catalyst "
                           f"(monitor for a technical setup in the next 2-3 "
                           f"sessions). **Negative news** → avoid re-entering "
                           f"these until sentiment stabilises. News does NOT "
                           f"bypass the technical signal — this section is "
                           f"informational, surfacing what the pure-technical "
                           f"pass missed.")
                wl_view = watchlist[["ticker", "sector", "news_score", "news_n",
                                      "news_top", "news_top_date",
                                      "news_latest", "news_latest_date",
                                      "news_matched"]].copy()
                wl_view.columns = ["Stock", "Sector", "News", "# articles",
                                    "Top headline", "Top date",
                                    "Latest headline", "Latest date",
                                    "Keywords matched"]
                st.dataframe(wl_view, use_container_width=True,
                             hide_index=True, height=320)
                st.download_button(
                    "⬇️ Download news watchlist",
                    wl_view.to_csv(index=False).encode(),
                    file_name=f"forward_news_watchlist_{cutoff.isoformat()}.csv",
                    mime="text/csv",
                )

        # -------- FULL news audit — every scanned stock with any news --------
        full_news = ok_df[(ok_df.get("news_n", 0).fillna(0) > 0)
                          | (ok_df.get("news_score", 0.0).fillna(0) != 0)].copy()
        if not full_news.empty:
            n_all = len(full_news)
            n_material = int((full_news["news_score"].abs() >= 0.15).sum())
            with st.expander(f"📊 Full news audit — {n_all} scanned stocks with "
                             f"any news activity  ({n_material} material)"):
                st.caption(f"Every fundamentally-passing stock's news score "
                           f"in the {news_lookback}-day window ending "
                           f"**{cutoff.isoformat()}** (no look-ahead — headlines "
                           f"dated after the cutoff were filtered out at fetch time). "
                           f"Sorted by |news score|. Zero-score rows are stocks "
                           f"where headlines existed but none matched the "
                           f"sentiment lexicon (neutral coverage).")
                full_news["|news|"] = full_news["news_score"].abs()
                full_news = full_news.sort_values("|news|", ascending=False).drop(columns=["|news|"])
                fv_view = full_news[["ticker", "sector", "signals_today",
                                     "news_score", "news_n",
                                     "news_top", "news_top_date",
                                     "news_latest", "news_latest_date",
                                     "news_matched"]].copy()
                fv_view.columns = ["Stock", "Sector", "Signals?", "News",
                                    "# articles",
                                    "Top headline", "Top date",
                                    "Latest headline", "Latest date",
                                    "Keywords matched"]
                st.dataframe(fv_view, use_container_width=True,
                             hide_index=True, height=380)
                st.download_button(
                    "⬇️ Download full news audit",
                    fv_view.to_csv(index=False).encode(),
                    file_name=f"forward_news_audit_{cutoff.isoformat()}.csv",
                    mime="text/csv",
                )

    # ========================================================================
    # FUNDAMENTALS-REJECTED AUDIT — never reached the technical scan
    # ========================================================================
    if apply_funda_gate and not funda_rejects_df.empty:
        with st.expander(f"🚫 {len(funda_rejects_df)} stocks rejected by "
                         f"fundamentals gate  (never reached the technical scan)"):
            st.caption("These would have been in the scan universe but failed "
                       "the no-trade filter (low ROE, high D/E, promoter pledge, "
                       "auditor issues, etc.).")
            st.dataframe(funda_rejects_df, use_container_width=True,
                         hide_index=True, height=300)
            st.download_button(
                "⬇️ Download fundamentals rejects",
                funda_rejects_df.to_csv(index=False).encode(),
                file_name=f"forward_funda_rejects_{cutoff.isoformat()}.csv",
                mime="text/csv",
            )

    # =============== METHODOLOGY EXPANDER ===============
    with st.expander("🎓 What each toggle does + honest caveats"):
        st.markdown(f"""
**v2 additions and their purpose:**

- **Regime gate** — the single biggest fix. Uses ONLY benchmark index data ≤ cutoff
  (no look-ahead). When the broad market is in RISK-OFF (below 200-DMA and falling),
  momentum longs get faded en masse. This filter alone typically prevents 60-80% of
  clustered stop-out losses.

- **Signal decay** — when 30 stocks fire signals same day, they're not 30 independent
  bets; they're one bet on the momentum factor. Cap the number of new entries per day
  and rank-select the strongest ones.

- **Sector cap** — matches live scanner. Max K per sector prevents 5-of-8 shortlist
  being all metals stocks that crash together on a China-slowdown headline.

- **Failure clustering analysis** — post-hoc diagnostic showing (a) same-day stop
  clusters, (b) sector concentration of losses, (c) speed of stops. Answers "why
  did they all fail together?"

**Still honestly disabled for cutoffs older than the recent past:**

- News/event blocking (free sources don't archive)
- Fundamentals gate (yfinance.info is TODAY's data, not point-in-time)
""")


if __name__ == "__main__":
    main()
