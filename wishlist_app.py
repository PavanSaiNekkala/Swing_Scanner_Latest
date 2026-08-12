"""
wishlist_app.py — SCANNER PREDICTION TRACKER
============================================
The "did-my-prediction-actually-work?" module.

The scanner suggests a stock might reach +15% in N days. This app:
  1. Reads that prediction from wishlist.csv
  2. Fetches today's price
  3. Compares actual behaviour to the prediction
  4. Assigns a verdict:
       ✅ TARGET_HIT / AHEAD_OF_PACE / ON_TRACK
       ⚠️  BEHIND_PACE / REVERSED
       🛑 STOP_HIT / EXPIRED
  5. APPENDS today's observation to wishlist_observations.csv (never overwrites)

Over 3-6 months of daily runs, you accumulate a track record that lets you
answer the questions no scanner can answer on Day 1:
  - What % of my scanner's predictions actually hit their target?
  - Is it more accurate on Nifty 100 vs smallcaps?
  - Are 12-day predictions more accurate than 30-day predictions?
  - Do BREAKOUT signals work better than REVERSAL signals?

USAGE
-----
    streamlit run wishlist_app.py
Or in the trading suite: Mode → 🔮 Wishlist Tracker
"""
import os
import io
import re as _re
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


# ======================================================================================
#  ENGINE & OPTIONAL HELPERS
# ======================================================================================
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE_PATH = os.path.join(_HERE, "swing_screener_app.py")
_spec = importlib.util.spec_from_file_location("engine", _ENGINE_PATH)
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)

# Reuse monitor's helpers where possible (encoding-tolerant loader, live-price
# fetcher, projection helpers) — one source of truth, no drift.
_MON_PATH = os.path.join(_HERE, "monitor_app.py")
_mspec = importlib.util.spec_from_file_location("_wl_monitor", _MON_PATH)
_monitor = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(_monitor)

try:
    from news_sentiment import fetch_news_score as _news_score
    HAVE_NEWS = True
except Exception:
    HAVE_NEWS = False

try:
    from universe_loader import load_full_universe as _ul_load
    HAVE_UNIVERSE = True
except Exception:
    HAVE_UNIVERSE = False


WISHLIST_CSV = os.path.join(_HERE, "wishlist.csv")
OBS_LOG_CSV  = os.path.join(_HERE, "wishlist_observations.csv")
POSITIONS_CSV = os.path.join(_HERE, "positions.csv")   # for promote-to-positions


# ======================================================================================
#  CSV LOADER (mirrors monitor's tolerance)
# ======================================================================================
REQUIRED_COLS = ("ticker", "signal_date")     # Only these two are truly required
OPTIONAL_COLS = ("signal_price", "buy_limit", "target_price",
                 "expected_days", "expected_days_thin",
                 "expected_confidence", "stop_price",
                 "news_score_at_signal",
                 "category", "strategy", "regime_at_signal", "trade_type",
                 "priority", "sector", "notes")

# SEBI's OFFICIAL market-cap classification (3-way, exhaustive):
#   LargeCap = top 100 stocks by market cap (Nifty 100)
#   MidCap   = ranks 101-250        (Nifty Midcap 150)
#   SmallCap = ranks 251 and beyond (everything else, ~2121 stocks)
# Every NSE-listed EQ/BE stock lands in exactly ONE of these three.
CATEGORY_PRIORITY = ("LargeCap", "MidCap", "SmallCap")

# Column aliases — normalise the many variants users paste from the scanner
COLUMN_ALIASES = {
    "last close":            "signal_price",
    "last_close":            "signal_price",
    "signal_price":          "signal_price",
    "signal price":          "signal_price",
    "buy limit ?":           "buy_limit",     # ₹ corrupted to ?
    "buy limit ₹":           "buy_limit",
    "buy_limit":             "buy_limit",
    "buy limit":             "buy_limit",
    "buy price":             "buy_limit",
    "target_price":          "target_price",
    "target price":          "target_price",
    "objective ₹":           "target_price",
    "objective":             "target_price",
    "stop_price":            "stop_price",
    "stop price":            "stop_price",
    "stop ₹":                "stop_price",
    "stop":                  "stop_price",
    "news score":            "news_score_at_signal",
    "news_score":            "news_score_at_signal",
    "news_score_at_signal":  "news_score_at_signal",
    "news":                  "news_score_at_signal",
    "conf":                  "expected_confidence",
    "conf(/day)":            "expected_confidence",
    "conf/day":              "expected_confidence",
    "confidence":            "expected_confidence",
    "expected_confidence":   "expected_confidence",
    "rank":                  "expected_confidence",
    "expected_days":         "expected_days",
    "exp. days→objective":   "expected_days",
    "exp days":              "expected_days",
    "days_to_target":        "expected_days",
    "ticker":                "ticker",
    "stock":                 "ticker",
    "symbol":                "ticker",
    "signal_date":           "signal_date",
    "signal date":           "signal_date",
    "category":              "category",
    "strategy":              "strategy",
    "regime_at_signal":      "regime_at_signal",
    "regime":                "regime_at_signal",
    "trade_type":            "trade_type",
    "signal":                "trade_type",
    "priority":              "priority",
    "sector":                "sector",
    "notes":                 "notes",
    "remark":                "notes",
    "remarks":               "notes",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns using COLUMN_ALIASES so downstream code sees canonical names."""
    lower_map = {c: c.strip().lower() for c in df.columns}
    rename = {c: COLUMN_ALIASES.get(lower_map[c], c) for c in df.columns}
    return df.rename(columns=rename)


def _parse_expected_days(v) -> tuple:
    """Parse strings like '14d', '2d ? thin', '11d ? thin' into (int, thin_flag).
    Returns (None, False) if parsing fails."""
    if pd.isna(v) or str(v).strip() in ("", "nan", "None"):
        return None, False
    s = str(v).strip().lower()
    thin = "thin" in s or "?" in s
    m = _re.search(r"(\d+)", s)
    if m:
        return int(m.group(1)), thin
    return None, False


def _is_news_only(row: pd.Series) -> bool:
    """A row is news-only when it has no price data (signal_price + target_price both missing)."""
    sp = row.get("signal_price"); tp = row.get("target_price")
    sp_missing = pd.isna(sp) or sp in (0, None, "")
    tp_missing = pd.isna(tp) or tp in (0, None, "")
    return sp_missing and tp_missing

_TICKER_ALLOWED = _re.compile(r"[^A-Z0-9&\-]")

def _clean_ticker(raw: str) -> str:
    if not isinstance(raw, str): return ""
    return _TICKER_ALLOWED.sub("", raw.strip().upper())

def _parse_flex_date(v):
    if pd.isna(v) or str(v).strip() in ("", "nan", "None"):
        return None
    s = str(v).strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try: return dt.datetime.strptime(s, fmt).date()
        except ValueError: continue
    try: return pd.to_datetime(s, dayfirst=True, errors="coerce").date()
    except Exception: return None


def load_wishlist(path: str = WISHLIST_CSV) -> tuple:
    """Robust loader: handles column aliases, string expected_days ('14d ? thin'),
    news-only rows (no price data), and duplicate rows."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=list(REQUIRED_COLS) + list(OPTIONAL_COLS)), \
               [f"File not found: {path}"]

    df = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(path, comment="#", skip_blank_lines=True, encoding=enc)
            break
        except Exception:
            continue
    if df is None:
        try:
            with open(path, "rb") as f: raw = f.read()
            df = pd.read_csv(io.StringIO(raw.decode("utf-8", errors="replace")),
                              comment="#", skip_blank_lines=True)
        except Exception as e:
            return pd.DataFrame(), [f"Read error: {e}"]

    # Normalise column names via aliases
    df = _normalize_columns(df)

    errors = []
    for c in REQUIRED_COLS:
        if c not in df.columns:
            errors.append(f"Missing required column: {c}")
    if errors:
        return pd.DataFrame(), errors
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = np.nan

    # Sanitize tickers
    orig_tk = df["ticker"].astype(str).copy()
    df["ticker"] = orig_tk.apply(_clean_ticker)
    cleaned = {o: n for o, n in zip(orig_tk, df["ticker"]) if o.strip() != n and n}
    if cleaned:
        errors.append("Cleaned ticker(s): " +
                       ", ".join(f"'{o.strip()}' → '{n}'" for o, n in list(cleaned.items())[:5])
                       + (" ..." if len(cleaned) > 5 else ""))
    df = df[df["ticker"].str.len() > 0]
    df = df[~df["ticker"].str.contains("EXAMPLE", na=False)]
    if df.empty:
        return df, ["No real wishlist items — edit wishlist.csv and re-run."]

    # Coerce numerics (expected_days handled specially below — it's a string like '14d')
    for c in ("signal_price", "buy_limit", "target_price", "stop_price",
              "expected_confidence", "news_score_at_signal"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Parse expected_days from strings like "14d", "2d ? thin"
    days_parsed = df["expected_days"].apply(_parse_expected_days)
    df["expected_days"]      = days_parsed.apply(lambda x: x[0])
    df["expected_days_thin"] = days_parsed.apply(lambda x: x[1])
    df["expected_days"] = pd.to_numeric(df["expected_days"], errors="coerce")

    df["signal_date"] = df["signal_date"].apply(_parse_flex_date)
    for c in ("category", "strategy", "regime_at_signal", "trade_type",
              "priority", "sector", "notes"):
        df[c] = df[c].fillna("").astype(str).str.strip()

    # Detect news-only rows and flag them explicitly
    df["is_news_only"] = df.apply(_is_news_only, axis=1)

    # Row-level validation:
    #   Every row needs: ticker + signal_date
    #   TA rows also need: signal_price + target_price
    #   News-only rows need: news_score_at_signal (non-zero, meaningful)
    bad_mask = df["signal_date"].isna() | (df["ticker"].str.len() == 0)
    # For TA rows, price data must be present
    ta_missing = (~df["is_news_only"]) & (
        df["signal_price"].isna() | df["target_price"].isna()
    )
    # For news-only rows, at least a news_score must be present
    news_missing = df["is_news_only"] & df["news_score_at_signal"].isna()
    bad_mask = bad_mask | ta_missing | news_missing

    bad = df[bad_mask]
    if not bad.empty:
        errors.append(f"⚠️ {len(bad)} row(s) dropped for missing required fields: "
                      f"{list(bad['ticker'])[:10]}"
                      + (" ..." if len(bad) > 10 else ""))
    df = df[~bad_mask].reset_index(drop=True)

    # DEDUPLICATE on (ticker, signal_date) — keep first occurrence
    n_before = len(df)
    df = df.drop_duplicates(subset=["ticker", "signal_date"], keep="first").reset_index(drop=True)
    n_dupes = n_before - len(df)
    if n_dupes:
        errors.append(f"ℹ️ Removed {n_dupes} duplicate row(s) (same ticker + signal_date).")

    # Informational flags
    n_news_only     = int(df["is_news_only"].sum())
    n_ta            = int((~df["is_news_only"]).sum())
    n_missing_stop  = int(df.loc[~df["is_news_only"], "stop_price"].isna().sum())
    n_missing_days  = int(df.loc[~df["is_news_only"], "expected_days"].isna().sum())
    n_thin          = int(df["expected_days_thin"].fillna(False).sum())
    n_missing_sector = int((df["sector"].str.strip() == "").sum())

    errors.append(f"📊 Loaded **{len(df)}** row(s): {n_ta} technical · {n_news_only} news-only.")
    if n_missing_stop:
        errors.append(f"ℹ️ {n_missing_stop} TA row(s) have no stop_price — auto-derive from ATR at signal_date.")
    if n_missing_days:
        errors.append(f"ℹ️ {n_missing_days} TA row(s) have no expected_days — auto-derive from historical median.")
    if n_thin:
        errors.append(f"⚠️ {n_thin} row(s) flagged 'thin' (limited historical sample) — treat their day estimates with caution.")
    if n_missing_sector:
        errors.append(f"ℹ️ {n_missing_sector} row(s) have no sector — auto-fill from NSE map.")
    return df, errors


# ======================================================================================
#  DATA HELPERS
# ======================================================================================
def _to_yahoo(sym: str) -> str:
    s = str(sym).strip().upper()
    return s if s.endswith((".NS", ".BO")) else s + ".NS"


@st.cache_data(ttl=30 * 60, show_spinner=False)
def _fetch_full_history(ticker_yahoo: str, start_year: int = 2015) -> pd.DataFrame:
    """Full daily OHLCV history from `start_year` to today. Used for both
    historical (at signal_date) and current TA snapshots."""
    if yf is None: return pd.DataFrame()
    try:
        df = yf.Ticker(ticker_yahoo).history(
            start=f"{start_year}-01-01",
            end=(dt.date.today() + dt.timedelta(days=1)),
            interval="1d", auto_adjust=True)
    except Exception:
        return pd.DataFrame()
    if df is None or df.empty: return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df.dropna()


def _bar_on_or_before(df: pd.DataFrame, target_date: dt.date):
    """Return the row of df on `target_date`, or the nearest preceding trading
    bar. Returns None if none exists."""
    if df is None or df.empty: return None
    ts = pd.Timestamp(target_date)
    subset = df.loc[df.index <= ts]
    return subset.iloc[-1] if not subset.empty else None


# ======================================================================================
#  DERIVE MISSING FIELDS FROM DATA AT SIGNAL DATE
# ======================================================================================
def _derive_stop_from_signal_date(df: pd.DataFrame, signal_date: dt.date,
                                    signal_price: float, atr_mult: float = 2.0,
                                    max_pct: float = 10.0) -> tuple:
    """Compute stop-loss using ATR at signal_date (not today).
    Returns (stop, method_str). Never returns None."""
    df_at = df.loc[df.index <= pd.Timestamp(signal_date)]
    if df_at.empty or len(df_at) < 30:
        return round(signal_price * (1 - max_pct / 100), 2), \
               f"{max_pct:.0f}% flat (insufficient signal-date history)"
    df_ind = engine.compute_indicators(df_at)
    if df_ind.empty:
        return round(signal_price * (1 - max_pct / 100), 2), f"{max_pct:.0f}% flat"
    atr_pct_at_signal = float(df_ind.iloc[-1].get("atr_pct", np.nan))
    if not np.isfinite(atr_pct_at_signal) or atr_pct_at_signal <= 0:
        return round(signal_price * (1 - max_pct / 100), 2), \
               f"{max_pct:.0f}% flat (ATR unavailable at signal date)"
    atr_abs = signal_price * atr_pct_at_signal / 100
    stop = signal_price - atr_mult * atr_abs
    floor = signal_price * (1 - max_pct / 100)
    stop = max(stop, floor)
    return round(stop, 2), \
        (f"2×ATR at signal date ({atr_pct_at_signal:.1f}% ATR → "
         f"{atr_mult*atr_pct_at_signal:.1f}% risk), capped at {max_pct:.0f}%")


def _derive_category(ticker: str, universe_buckets: dict) -> str:
    """SEBI's OFFICIAL 3-way market-cap classification — every NSE-listed
    stock lands in exactly ONE of LargeCap / MidCap / SmallCap.

    Rules (checked in order):
      1. LargeCap  — in Nifty 100 (top 100 by market cap)
      2. MidCap    — in Nifty Midcap 150 (ranks 101-250)
      3. SmallCap  — everything else (SEBI: ranks 251+ = ALL are small caps)
                     Includes both the curated Nifty Smallcap 250 AND the
                     ~1,871 microcap-territory stocks beyond Nifty 500.
      4. Unknown   — not in any NSE bucket (delisted / renamed / typo)
    """
    if not universe_buckets: return "Unknown"

    # Tier 1: LargeCap (top 100)
    if ticker in universe_buckets.get("LargeCap", []):
        return "LargeCap"
    # Tier 2: MidCap (ranks 101-250)
    if ticker in universe_buckets.get("MidCap", []):
        return "MidCap"
    # Tier 3: SmallCap — SEBI's definition = everything else that trades
    #   Includes: Nifty Smallcap 250 (curated top 250 smallcaps) + all
    #   microcap-tier stocks beyond Nifty 500. If it's in AllNSE at all,
    #   it counts as a small cap per SEBI.
    if ticker in universe_buckets.get("AllNSE", []):
        return "SmallCap"
    return "Unknown"


def _derive_regime_at_signal(bench_hist: pd.DataFrame, signal_date: dt.date) -> str:
    """Compute what market regime was in effect on signal_date, using only
    benchmark bars <= signal_date (no look-ahead). Same convention as
    monitor_app._regime_from_bench.
    Returns: 'RISK-ON' / 'NEUTRAL' / 'RISK-OFF' / 'UNKNOWN'."""
    if bench_hist is None or bench_hist.empty:
        return "UNKNOWN"
    sub = bench_hist.loc[bench_hist.index <= pd.Timestamp(signal_date)]
    if len(sub) < 210:
        return "UNKNOWN"
    c = sub["Close"]
    s200 = float(c.rolling(200).mean().iloc[-1])
    last = float(c.iloc[-1])
    above = last > s200
    roc10 = (c.iloc[-1] / c.iloc[-11] - 1) * 100 if len(c) > 11 else 0.0
    if above and roc10 > -1.0: return "RISK-ON"
    if above or roc10 > -3.0:  return "NEUTRAL"
    return "RISK-OFF"


@st.cache_data(ttl=30 * 60, show_spinner=False)
def _fetch_bench_history(bench_ticker: str = "^CRSLDX") -> pd.DataFrame:
    """Bench history for regime lookup — cached separately from stock history."""
    if yf is None: return pd.DataFrame()
    for tick in (bench_ticker, "^NSEI"):
        try:
            df = yf.Ticker(tick).history(start="2015-01-01",
                                          end=dt.date.today() + dt.timedelta(days=1),
                                          interval="1d", auto_adjust=True)
            if df is not None and not df.empty:
                df = df[["Open", "High", "Low", "Close"]].copy()
                df.index = pd.to_datetime(df.index).tz_localize(None)
                return df.dropna()
        except Exception:
            continue
    return pd.DataFrame()


def _derive_expected_days(df: pd.DataFrame, signal_date: dt.date,
                           target_pct: float) -> int:
    """Use historical median days-to-target on THIS stock as-of signal_date.
    Falls back to 15 sessions."""
    df_at = df.loc[df.index <= pd.Timestamp(signal_date)]
    if len(df_at) < 100:
        return 15
    df_ind = engine.compute_indicators(df_at)
    hist = _monitor._historical_target_stats(df_ind, target_pct=target_pct,
                                              window_days=30, lookback=500)
    if hist and hist.get("med_days"):
        return int(hist["med_days"])
    return 15


# ======================================================================================
#  VERDICT ENGINE
# ======================================================================================
def _news_only_verdict(orig_news_score: float, current_news_score: float,
                        price_at_signal: float, current_price: float,
                        days_elapsed: int) -> dict:
    """Verdict engine for news-only rows (no price target, only sentiment).

    Two dimensions:
      A. NEWS EVOLUTION — has sentiment shifted since signal date?
      B. PRICE DRIFT — did the market actually move in the news direction?

    Verdicts:
      NEWS_CONFIRMED    — market moved in same direction as news signal (+ for pos, - for neg)
      NEWS_STALLED      — market flat; news didn't catalyze
      NEWS_FAILED       — market moved OPPOSITE to news signal (contrarian)
      NEWS_FADED        — original signal strong but current news score has weakened
      NEWS_INTENSIFIED  — original signal strong and current news even stronger
      NEWS_NEUTRAL      — original signal wasn't strong enough to track
    """
    if price_at_signal and price_at_signal > 0:
        drift_pct = (current_price / price_at_signal - 1) * 100
    else:
        drift_pct = 0

    # Categorize original signal strength
    positive = orig_news_score >= 0.15
    negative = orig_news_score <= -0.15

    if not (positive or negative):
        return {"status": "NEWS_NEUTRAL", "label": "ℹ️ NEWS_NEUTRAL",
                "on_track_pct": 50, "drift_pct": drift_pct,
                "note": (f"Original news score {orig_news_score:+.2f} "
                         f"below tracking threshold (±0.15).")}

    # Positive news signal
    if positive:
        if drift_pct > 3:
            status, label = "NEWS_CONFIRMED", "✅ NEWS_CONFIRMED"
            note = (f"Positive news ({orig_news_score:+.2f}) confirmed — "
                    f"price up {drift_pct:+.1f}% since signal.")
            on_track = 90
        elif drift_pct > -1:
            status, label = "NEWS_STALLED", "🟡 NEWS_STALLED"
            note = (f"Positive news ({orig_news_score:+.2f}) but price flat "
                    f"({drift_pct:+.1f}%) — market didn't buy the story.")
            on_track = 40
        else:
            status, label = "NEWS_FAILED", "🔴 NEWS_FAILED"
            note = (f"Positive news ({orig_news_score:+.2f}) FAILED — "
                    f"price fell {drift_pct:+.1f}% despite the headline.")
            on_track = 5
    else:  # negative news
        if drift_pct < -3:
            status, label = "NEWS_CONFIRMED", "✅ NEWS_CONFIRMED"
            note = (f"Negative news ({orig_news_score:+.2f}) confirmed — "
                    f"price down {drift_pct:+.1f}% since signal.")
            on_track = 90
        elif drift_pct < 1:
            status, label = "NEWS_STALLED", "🟡 NEWS_STALLED"
            note = (f"Negative news ({orig_news_score:+.2f}) but price flat "
                    f"({drift_pct:+.1f}%) — market ignored it.")
            on_track = 40
        else:
            status, label = "NEWS_FAILED", "🔴 NEWS_FAILED"
            note = (f"Negative news ({orig_news_score:+.2f}) FAILED — "
                    f"price ROSE {drift_pct:+.1f}% despite the headline.")
            on_track = 5

    # Overlay: has current news score weakened / intensified?
    news_delta = current_news_score - orig_news_score
    if abs(news_delta) > 0.2:
        if (positive and news_delta < -0.2) or (negative and news_delta > 0.2):
            note += (f" · NEWS_FADED (score moved from {orig_news_score:+.2f} "
                     f"to {current_news_score:+.2f})")
        elif (positive and news_delta > 0.2) or (negative and news_delta < -0.2):
            note += (f" · NEWS_INTENSIFIED (score moved from {orig_news_score:+.2f} "
                     f"to {current_news_score:+.2f})")

    return {"status": status, "label": label,
            "on_track_pct": on_track, "drift_pct": drift_pct,
            "note": note}


def _verdict(signal_price: float, target_price: float, current_price: float,
              stop_price: float, expected_days: int, days_elapsed: int,
              ta_now: dict) -> dict:
    """Compute the verdict for one wishlist observation.
    Returns {status, label, on_track_pct, note}.
    Status is one of:
      TARGET_HIT / STOP_HIT / EXPIRED
      AHEAD_OF_PACE / ON_TRACK / BEHIND_PACE / REVERSED
    """
    # Absolute terminal conditions first
    if current_price >= target_price:
        return {"status": "TARGET_HIT", "label": "✅ TARGET_HIT",
                "on_track_pct": 100,
                "note": (f"Target ₹{target_price:.2f} reached — "
                         f"prediction correct in {days_elapsed}d "
                         f"(expected {expected_days}d).")}
    if current_price <= stop_price:
        return {"status": "STOP_HIT", "label": "🛑 STOP_HIT",
                "on_track_pct": 0,
                "note": (f"Stop ₹{stop_price:.2f} hit — signal invalidated. "
                         f"Would have lost {100*(stop_price/signal_price-1):+.1f}%.")}

    # Time budget check (allow 50% overrun before EXPIRED)
    if days_elapsed > expected_days * 1.5:
        return {"status": "EXPIRED", "label": "⏰ EXPIRED",
                "on_track_pct": 0,
                "note": (f"Beyond {expected_days}d expected duration "
                         f"({days_elapsed}d elapsed). No target hit — "
                         f"consider dropping from wishlist.")}

    # Pace analysis
    total_move = target_price - signal_price
    if total_move <= 0:
        return {"status": "REVERSED", "label": "⚠️ INVALID_TARGET",
                "on_track_pct": 0,
                "note": "Target is at or below signal price — check the CSV row."}

    elapsed_frac = min(1.0, max(0.01, days_elapsed / max(1, expected_days)))
    expected_price_by_now = signal_price + total_move * elapsed_frac
    actual_move = current_price - signal_price
    expected_move = expected_price_by_now - signal_price
    move_ratio = actual_move / max(expected_move, 0.001)
    progress_pct = 100 * actual_move / total_move       # 0..100 (or negative)

    if actual_move < 0:
        status = "REVERSED"
        label = "⚠️ REVERSED"
        note = (f"Down {100*actual_move/signal_price:+.1f}% from signal — "
                f"signal weakening. TA: RSI {ta_now.get('rsi14', np.nan):.0f} · "
                f"MACD {'+' if ta_now.get('macd_hist', 0) > 0 else '-'}.")
    elif move_ratio >= 1.15:
        status = "AHEAD_OF_PACE"
        label = "🚀 AHEAD_OF_PACE"
        note = (f"{progress_pct:.0f}% done in {100*elapsed_frac:.0f}% of expected time — "
                f"prediction beating schedule.")
    elif move_ratio >= 0.85:
        status = "ON_TRACK"
        label = "✅ ON_TRACK"
        note = (f"{progress_pct:.0f}% done in {100*elapsed_frac:.0f}% of expected time — "
                f"matching schedule closely.")
    else:
        status = "BEHIND_PACE"
        label = "⚠️ BEHIND_PACE"
        note = (f"Only {progress_pct:.0f}% done in {100*elapsed_frac:.0f}% of expected "
                f"time — slower than predicted. Watch for signal fade.")
    return {"status": status, "label": label,
            "on_track_pct": round(min(100, max(0, progress_pct)), 1),
            "note": note}


# ======================================================================================
#  OBSERVATION LOG (append-only, never overwrites)
# ======================================================================================
OBS_FIELDS = ("observation_date", "ticker",
              # segmentation metadata — for downstream analytics
              "category", "sector", "strategy",
              "regime_at_signal", "trade_type", "priority",
              # time & price
              "signal_date", "days_elapsed", "expected_days", "days_remaining",
              "signal_price", "current_price", "peak_price_since_signal",
              "current_return_pct", "peak_return_pct",
              "expected_return_pct_by_now", "deviation_pct",
              # verdict + supporting data
              "verdict", "on_track_pct",
              "rsi14", "macd_hist", "adx14", "news_score", "note")


def _load_observation_log(path: str = OBS_LOG_CSV) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=list(OBS_FIELDS))
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.DataFrame(columns=list(OBS_FIELDS))


def _append_observation(row: dict, path: str = OBS_LOG_CSV) -> None:
    """Append one row to the observation log. Creates header if new file."""
    file_exists = os.path.exists(path)
    df_row = pd.DataFrame([{k: row.get(k, "") for k in OBS_FIELDS}])
    df_row.to_csv(path, mode="a", header=not file_exists, index=False,
                   encoding="utf-8")


def _dedupe_today(obs_df: pd.DataFrame, ticker: str, today: dt.date) -> pd.DataFrame:
    """Return obs_df with any existing row for (ticker, today) removed —
    prevents duplicate rows if the user runs the app twice in one day."""
    if obs_df.empty: return obs_df
    obs_df = obs_df.copy()
    obs_df["observation_date"] = pd.to_datetime(obs_df["observation_date"],
                                                  errors="coerce").dt.date
    mask = (obs_df["ticker"] == ticker) & (obs_df["observation_date"] == today)
    return obs_df[~mask]


def _rewrite_observation_log(df: pd.DataFrame, path: str = OBS_LOG_CSV) -> None:
    df.to_csv(path, index=False, encoding="utf-8")


# ======================================================================================
#  PER-STOCK ANALYSIS
# ======================================================================================
def analyze_wishlist_item(row: pd.Series, sector_map: dict,
                            universe_buckets: dict = None,
                            bench_history: pd.DataFrame = None,
                            use_news: bool = True) -> dict:
    """Full analysis for one wishlist item. Fetches history, derives missing
    fields (category, regime, sector, stop, expected_days), computes
    current state + verdict. Handles BOTH technical rows and news-only rows."""
    ticker = str(row["ticker"]).upper()
    ty = _to_yahoo(ticker)
    signal_date = row["signal_date"]

    is_news_only = bool(row.get("is_news_only", False))
    signal_price = float(row["signal_price"]) if pd.notna(row.get("signal_price")) else None
    target_price = float(row["target_price"]) if pd.notna(row.get("target_price")) else None
    buy_limit    = float(row["buy_limit"])    if pd.notna(row.get("buy_limit"))    else None
    news_score_at_signal = (float(row["news_score_at_signal"])
                              if pd.notna(row.get("news_score_at_signal")) else 0.0)

    result = {
        "ticker": ticker, "yahoo": ty,
        "signal_date": signal_date, "signal_price": signal_price,
        "target_price": target_price,
        "buy_limit": buy_limit,
        "news_score_at_signal": news_score_at_signal,
        "is_news_only": is_news_only,
        "expected_days_thin": bool(row.get("expected_days_thin", False)),
        "stop_price": row.get("stop_price"),
        "expected_days": row.get("expected_days"),
        "expected_confidence": row.get("expected_confidence"),
        "category": (row.get("category") or "").strip(),
        "strategy": (row.get("strategy") or "").strip(),
        "regime_at_signal": (row.get("regime_at_signal") or "").strip(),
        "trade_type": (row.get("trade_type") or "").strip(),
        "priority": (row.get("priority") or "").strip(),
        "sector": (row.get("sector") or "").strip(),
        "notes": row.get("notes", ""),
    }

    # ---- Auto-derive category from universe buckets ----
    if not result["category"] and universe_buckets:
        result["category"] = _derive_category(ticker, universe_buckets)
        result["category_source"] = "auto (NSE bucket)"
    elif not result["category"]:
        result["category"] = "Unknown"
        result["category_source"] = "unknown"
    else:
        result["category_source"] = "user"

    # ---- Auto-derive regime at signal date ----
    if not result["regime_at_signal"]:
        if bench_history is not None and not bench_history.empty:
            result["regime_at_signal"] = _derive_regime_at_signal(
                bench_history, signal_date)
            result["regime_source"] = "auto (bench at signal_date)"
        else:
            result["regime_at_signal"] = "UNKNOWN"
            result["regime_source"] = "unavailable"
    else:
        result["regime_source"] = "user"

    # ---- Default strategy & trade_type ----
    if not result["strategy"]:
        result["strategy"] = "PASS_combined"
        result["strategy_source"] = "default"
    else:
        result["strategy_source"] = "user"

    if not result["trade_type"]:
        result["trade_type"] = "UPTREND"

    if not result["priority"]:
        result["priority"] = "medium"

    # Fetch full price history
    hist = _fetch_full_history(ty)
    if hist.empty:
        result.update({"status": "NO_DATA", "label": "⚪ NO_DATA",
                        "note": "no yfinance data",
                        "current_price": None,
                        "days_elapsed": (dt.date.today() - signal_date).days,
                        "current_return_pct": 0,
                        "expected_return_pct_by_now": 0,
                        "deviation_pct": 0,
                        "peak_price_since_signal": None, "peak_return_pct": 0,
                        "days_remaining": 0,
                        "stop_source": "n/a", "sector_source": "unavailable",
                        "expected_days_source": "n/a",
                        "expected_days": result.get("expected_days") or 15})
        return result

    # Auto-derive sector (applies to both TA + news-only rows)
    if not result["sector"]:
        result["sector"] = sector_map.get(ticker, "-") or "-"
        result["sector_source"] = "auto (NSE map)" if result["sector"] != "-" else "unknown"
    else:
        result["sector_source"] = "user"

    # =====================================================================
    # NEWS-ONLY BRANCH — no price target, only sentiment tracking
    # =====================================================================
    if is_news_only:
        # Fetch price at signal_date + today's price
        sig_bar = _bar_on_or_before(hist, signal_date)
        price_at_signal = float(sig_bar["Close"]) if sig_bar is not None else None
        live = _monitor._fetch_live_price(ty)
        current_price = float(live.get("price") or hist["Close"].iloc[-1])
        result.update({
            "signal_price": price_at_signal,   # backfill from actual close
            "current_price": round(current_price, 2),
            "price_asof": live.get("as_of"),
            "price_source": live.get("source", "daily close"),
            "stop_source": "n/a (news-only)",
            "expected_days_source": "n/a (news-only)",
            "expected_days": result.get("expected_days") or 30,
            "days_elapsed": (dt.date.today() - signal_date).days,
        })
        result["days_remaining"] = max(0, result["expected_days"] - result["days_elapsed"])
        # Live news score for comparison
        current_news = {"score": 0.0, "n_articles": 0, "top_headline": None}
        if use_news and HAVE_NEWS:
            try: current_news = _news_score(ty)
            except Exception: pass
        result["news"] = current_news
        # Peak / return since signal
        if price_at_signal:
            peak_bar = hist.loc[hist.index >= pd.Timestamp(signal_date)]
            if not peak_bar.empty:
                result["peak_price_since_signal"] = round(float(peak_bar["High"].max()), 2)
                result["peak_return_pct"] = round(
                    (peak_bar["High"].max() / price_at_signal - 1) * 100, 2)
            else:
                result["peak_price_since_signal"] = current_price
                result["peak_return_pct"] = 0
            result["current_return_pct"] = round((current_price/price_at_signal - 1) * 100, 2)
        else:
            result["peak_price_since_signal"] = None
            result["peak_return_pct"] = 0
            result["current_return_pct"] = 0
        result["expected_return_pct_by_now"] = 0
        result["deviation_pct"] = 0
        # News-only verdict
        v = _news_only_verdict(
            orig_news_score=news_score_at_signal,
            current_news_score=current_news.get("score", 0.0),
            price_at_signal=price_at_signal or 0,
            current_price=current_price,
            days_elapsed=result["days_elapsed"])
        result.update(v)
        return result

    # =====================================================================
    # TECHNICAL BRANCH — full analysis with target/stop/verdict
    # =====================================================================
    # Auto-derive stop from ATR at signal_date
    if pd.isna(result["stop_price"]) or not result["stop_price"]:
        stop_val, stop_method = _derive_stop_from_signal_date(
            hist, signal_date, signal_price)
        result["stop_price"] = stop_val
        result["stop_source"] = f"auto: {stop_method}"
    else:
        result["stop_source"] = "user"

    # Auto-derive expected_days from historical median (as-of signal_date)
    if pd.isna(result["expected_days"]) or not result["expected_days"]:
        tgt_pct = (target_price / signal_price - 1) * 100
        result["expected_days"] = _derive_expected_days(hist, signal_date, tgt_pct)
        result["expected_days_source"] = "auto: historical median"
    else:
        result["expected_days"] = int(result["expected_days"])
        result["expected_days_source"] = "user"

    # Live price + TA snapshot (uses monitor's fetcher for consistency)
    live = _monitor._fetch_live_price(ty)
    if live.get("price") is not None:
        current_price = float(live["price"])
    else:
        current_price = float(hist["Close"].iloc[-1])
    result["current_price"] = round(current_price, 2)
    result["price_asof"] = live.get("as_of")
    result["price_source"] = live.get("source", "daily close")

    # TA snapshot from today's bar
    df_ind_now = engine.compute_indicators(hist)
    ta_now = _monitor._ta_snapshot(df_ind_now)
    ta_now["close"] = current_price      # override with live price
    result["ta"] = ta_now

    # Days elapsed & remaining
    days_elapsed = (dt.date.today() - signal_date).days
    result["days_elapsed"] = days_elapsed
    result["days_remaining"] = max(0, result["expected_days"] - days_elapsed)

    # Peak price since signal
    peak_bar = hist.loc[hist.index >= pd.Timestamp(signal_date)]
    if not peak_bar.empty:
        result["peak_price_since_signal"] = round(float(peak_bar["High"].max()), 2)
        result["peak_return_pct"] = round(
            (peak_bar["High"].max() / signal_price - 1) * 100, 2)
    else:
        result["peak_price_since_signal"] = current_price
        result["peak_return_pct"] = (current_price / signal_price - 1) * 100

    # Current & expected returns
    result["current_return_pct"] = round(
        (current_price / signal_price - 1) * 100, 2)
    target_pct = (target_price / signal_price - 1) * 100
    elapsed_frac = min(1.0, max(0.0, days_elapsed / max(1, result["expected_days"])))
    result["expected_return_pct_by_now"] = round(target_pct * elapsed_frac, 2)
    result["deviation_pct"] = round(
        result["current_return_pct"] - result["expected_return_pct_by_now"], 2)

    # News
    news = {"score": 0.0, "n_articles": 0, "top_headline": None}
    if use_news and HAVE_NEWS:
        try: news = _news_score(ty)
        except Exception: pass
    result["news"] = news

    # Verdict
    v = _verdict(signal_price=signal_price, target_price=target_price,
                  current_price=current_price, stop_price=result["stop_price"],
                  expected_days=result["expected_days"],
                  days_elapsed=days_elapsed, ta_now=ta_now)
    result.update(v)

    return result


# ======================================================================================
#  UI
# ======================================================================================
VERDICT_STYLE = {
    # Technical verdicts
    "TARGET_HIT":     ("✅", "#16a34a", "success"),
    "AHEAD_OF_PACE":  ("🚀", "#0891b2", "info"),
    "ON_TRACK":       ("🟢", "#16a34a", "success"),
    "BEHIND_PACE":    ("⚠️", "#f97316", "warning"),
    "REVERSED":       ("🔻", "#dc2626", "error"),
    "STOP_HIT":       ("🛑", "#dc2626", "error"),
    "EXPIRED":        ("⏰", "#64748b", "info"),
    # News-only verdicts
    "NEWS_CONFIRMED": ("✅", "#16a34a", "success"),
    "NEWS_STALLED":   ("🟡", "#f97316", "warning"),
    "NEWS_FAILED":    ("🔴", "#dc2626", "error"),
    "NEWS_NEUTRAL":   ("ℹ️", "#64748b", "info"),
    # Generic
    "NO_DATA":        ("⚪", "#64748b", "info"),
}


def body():
    """Render logic; safe inside trading_suite.py (no set_page_config)."""
    with st.sidebar:
        st.markdown("## 🔮 Wishlist Tracker")
        st.caption("Track scanner predictions vs actual market behaviour.")

        st.divider()
        st.markdown("**⚙️ Data**")
        use_news = st.checkbox("📰 Use news sentiment",
                                value=HAVE_NEWS, disabled=not HAVE_NEWS,
                                help="Adds a `news_score` column to each observation.")

        st.divider()
        st.markdown("**📁 Files**")
        with st.expander("Wishlist path"):
            st.code(WISHLIST_CSV, language="text")
        with st.expander("Observation log path"):
            st.code(OBS_LOG_CSV, language="text")
            st.caption("Append-only log — one row per (stock × day) each time you run.")
        if st.button("🔄 Refresh (re-fetch prices)", type="primary",
                     use_container_width=True):
            _fetch_full_history.clear()
            _monitor._fetch_live_price.clear()
            st.rerun()

        st.divider()
        with st.expander("📖 Verdict legend"):
            for status, (ico, _, _) in VERDICT_STYLE.items():
                st.markdown(f"- {ico} **{status}**")

    st.title("🔮 Wishlist Tracker — did the prediction pan out?")
    st.caption("Each stock is a hypothesis. Every run appends an observation "
                "to `wishlist_observations.csv` so you build a track record "
                "of the scanner's accuracy over time.")

    wl, errors = load_wishlist(WISHLIST_CSV)
    for e in errors:
        (st.caption if e.startswith("ℹ️") else st.warning)(e)

    if wl.empty:
        st.info("Wishlist is empty. Edit **wishlist.csv** and click Refresh.")
        with st.expander("Show wishlist.csv template"):
            try:
                with open(WISHLIST_CSV, "r", encoding="utf-8") as f:
                    st.code(f.read(), language="csv")
            except Exception as ex:
                st.error(f"Can't read template: {ex}")
        return

    # Sector map + universe buckets (for category auto-derive)
    sector_map = {}
    universe_buckets = {}
    if HAVE_UNIVERSE:
        try:
            bundle = _ul_load()
            sector_map = bundle.get("sector_map", {})
            universe_buckets = bundle.get("buckets", {})
        except Exception:
            sector_map = {}
            universe_buckets = {}

    # Benchmark history (for regime_at_signal auto-derive)
    with st.spinner("📡 Fetching benchmark for regime auto-derive..."):
        bench_history = _fetch_bench_history()

    # ============================================================
    # ANALYZE EACH ITEM
    # ============================================================
    st.markdown(f"Analyzing **{len(wl)}** wishlist item(s) …")
    prog = st.progress(0.0); status = st.empty()
    results = []
    for k, (_, row) in enumerate(wl.iterrows(), 1):
        status.markdown(f"🔍 Analyzing **{row['ticker']}** ({k}/{len(wl)})…")
        r = analyze_wishlist_item(row, sector_map,
                                    universe_buckets=universe_buckets,
                                    bench_history=bench_history,
                                    use_news=use_news)
        results.append(r)
        prog.progress(k / len(wl))
        time.sleep(0.05)
    status.empty(); prog.empty()

    # ============================================================
    # APPEND TO OBSERVATION LOG (idempotent per day)
    # ============================================================
    today = dt.date.today()
    obs_df = _load_observation_log()
    # De-dupe today's entries for these tickers so we can safely re-write
    for r in results:
        obs_df = _dedupe_today(obs_df, r["ticker"], today)
    _rewrite_observation_log(obs_df)
    for r in results:
        if r.get("status") == "NO_DATA": continue
        ta = r.get("ta", {}) or {}
        obs_row = {
            "observation_date": today.isoformat(),
            "ticker": r["ticker"],
            # NEW metadata — enables per-category / per-strategy / per-regime analytics
            "category":         r.get("category", ""),
            "sector":           r.get("sector", ""),
            "strategy":         r.get("strategy", ""),
            "regime_at_signal": r.get("regime_at_signal", ""),
            "trade_type":       r.get("trade_type", ""),
            "priority":         r.get("priority", ""),
            # time & price
            "signal_date":  r["signal_date"].isoformat() if r.get("signal_date") else "",
            "days_elapsed": r["days_elapsed"],
            "expected_days": r["expected_days"],
            "days_remaining": r["days_remaining"],
            "signal_price": r["signal_price"],
            "current_price": r["current_price"],
            "peak_price_since_signal": r["peak_price_since_signal"],
            "current_return_pct": r["current_return_pct"],
            "peak_return_pct": r["peak_return_pct"],
            "expected_return_pct_by_now": r["expected_return_pct_by_now"],
            "deviation_pct": r["deviation_pct"],
            # verdict + supporting
            "verdict": r["status"],
            "on_track_pct": r.get("on_track_pct", 0),
            "rsi14": round(float(ta.get("rsi14", 0)), 1) if ta.get("rsi14") else "",
            "macd_hist": round(float(ta.get("macd_hist", 0)), 3) if ta.get("macd_hist") else "",
            "adx14": round(float(ta.get("adx14", 0)), 1) if ta.get("adx14") else "",
            "news_score": r.get("news", {}).get("score", 0),
            "note": r.get("note", ""),
        }
        _append_observation(obs_row)
    st.caption(f"✏️ Appended {len(results)} observation(s) to "
                f"`wishlist_observations.csv` for **{today.isoformat()}**.")

    # ============================================================
    # SUMMARY CARDS
    # ============================================================
    st.divider()
    st.markdown("### 📊 Wishlist Summary")

    counts = {s: 0 for s in VERDICT_STYLE}
    for r in results:
        counts[r.get("status", "NO_DATA")] += 1

    # Split TA vs news-only for cleaner display
    st.markdown("**📈 Technical predictions**")
    cs = st.columns(7)
    order = ["TARGET_HIT", "AHEAD_OF_PACE", "ON_TRACK", "BEHIND_PACE",
             "REVERSED", "STOP_HIT", "EXPIRED"]
    for i, s in enumerate(order):
        ico = VERDICT_STYLE[s][0]
        cs[i].metric(f"{ico} {s.replace('_', ' ').title()}", counts.get(s, 0))

    # News-only summary row (only shown if any news-only rows exist)
    news_verdicts = ["NEWS_CONFIRMED", "NEWS_STALLED", "NEWS_FAILED", "NEWS_NEUTRAL"]
    n_news_total = sum(counts.get(s, 0) for s in news_verdicts)
    if n_news_total > 0:
        st.markdown("**📰 News-only predictions**")
        nc = st.columns(4)
        for i, s in enumerate(news_verdicts):
            ico = VERDICT_STYLE[s][0]
            nc[i].metric(f"{ico} {s.replace('_', ' ').title()}", counts.get(s, 0))

    # Overall on-track %
    active = [r for r in results if r.get("status") not in
              ("TARGET_HIT", "STOP_HIT", "EXPIRED", "NO_DATA")]
    active_ok = [r for r in active if r.get("status") in
                 ("ON_TRACK", "AHEAD_OF_PACE")]
    on_track_pct = int(100 * len(active_ok) / len(active)) if active else 0

    hit_rate_pct = int(100 * counts["TARGET_HIT"] /
                       max(1, counts["TARGET_HIT"] + counts["STOP_HIT"] +
                           counts["EXPIRED"])) if any(
                               counts[s] for s in ("TARGET_HIT", "STOP_HIT", "EXPIRED")) else None

    scc = st.columns(3)
    scc[0].metric("🎯 On-track (of active)", f"{on_track_pct}%")
    scc[1].metric("✅ Final hit rate",
                   f"{hit_rate_pct}%" if hit_rate_pct is not None else "n/a",
                   help="Of closed predictions (target/stop/expired), % that hit target.")
    scc[2].metric("📊 Total observations logged",
                   len(_load_observation_log()))

    # ------------- Category / regime / strategy breakdown -------------
    st.markdown("### 🧮 Breakdown by segment")
    br1, br2, br3 = st.columns(3)

    def _bucket_summary(rows, field: str, empty_label: str = "unknown"):
        """Return a small dataframe of counts by field value."""
        vals = {}
        for r in rows:
            v = r.get(field) or empty_label
            vals.setdefault(v, {"count": 0, "on_track": 0, "hits": 0, "stops": 0})
            vals[v]["count"] += 1
            if r.get("status") in ("ON_TRACK", "AHEAD_OF_PACE"): vals[v]["on_track"] += 1
            if r.get("status") == "TARGET_HIT": vals[v]["hits"] += 1
            if r.get("status") == "STOP_HIT":   vals[v]["stops"] += 1
        return pd.DataFrame(
            [{field: k, "count": d["count"],
              "on_track": d["on_track"], "target_hits": d["hits"],
              "stops": d["stops"]}
             for k, d in vals.items()])

    with br1:
        st.caption("**By category (market cap)**")
        cat_df = _bucket_summary(results, "category")
        if not cat_df.empty:
            st.dataframe(cat_df, hide_index=True, use_container_width=True)
    with br2:
        st.caption("**By regime at signal**")
        reg_df = _bucket_summary(results, "regime_at_signal")
        if not reg_df.empty:
            st.dataframe(reg_df, hide_index=True, use_container_width=True)
    with br3:
        st.caption("**By strategy**")
        strat_df = _bucket_summary(results, "strategy")
        if not strat_df.empty:
            st.dataframe(strat_df, hide_index=True, use_container_width=True)
    st.caption("Over 3-6 months of daily runs, these tables show WHICH segments the "
                "scanner is genuinely accurate on — informs future universe selection.")

    st.divider()

    # ============================================================
    # 📊 QUICK VIEW — ALL STOCKS AT A GLANCE
    # (see everything without expanding cards)
    # ============================================================
    st.divider()
    st.markdown("### 📊 Quick view — all stocks at a glance")
    st.caption("Every wishlist stock's key stats in one table + a visual return chart. "
                "Scan quickly to spot winners, losers, and stalled predictions. "
                "Expand any card below for full detail.")

    # Build a comprehensive at-a-glance dataframe
    _order = {"TARGET_HIT": 0, "AHEAD_OF_PACE": 1, "ON_TRACK": 2,
              "NEWS_CONFIRMED": 3, "BEHIND_PACE": 4, "NEWS_STALLED": 5,
              "REVERSED": 6, "NEWS_FAILED": 7, "STOP_HIT": 8,
              "EXPIRED": 9, "NEWS_NEUTRAL": 10, "NO_DATA": 11}
    qv_rows = []
    for r in results:
        v_ico = VERDICT_STYLE.get(r.get("status", "NO_DATA"), ("•",))[0]
        qv_rows.append({
            "Stock":     r["ticker"],
            "Type":      "📰 news" if r.get("is_news_only") else "📈 TA",
            "Category":  r.get("category", "?") or "?",
            "Sector":    (r.get("sector", "-") or "-")[:24],
            "Verdict":   f"{v_ico} {r.get('status','?')}",
            "_ord":      _order.get(r.get("status", "NO_DATA"), 99),
            "Signal ₹":  r.get("signal_price"),
            "Now ₹":     r.get("current_price"),
            "Return %":  r.get("current_return_pct", 0) or 0,
            "Peak %":    r.get("peak_return_pct", 0) or 0,
            "Deviation %": r.get("deviation_pct", 0) or 0,
            "Target ₹":  r.get("target_price"),
            "Stop ₹":    r.get("stop_price"),
            "Days":      (f"{r.get('days_elapsed','?')}/"
                          f"{r.get('expected_days','?')}"),
            "News (sig→now)": (f"{r.get('news_score_at_signal', 0) or 0:+.2f}→"
                                f"{(r.get('news') or {}).get('score', 0) or 0:+.2f}"),
            "Note":      (r.get("note", "") or "")[:80],
        })
    qv_df = pd.DataFrame(qv_rows).sort_values("_ord").drop(columns=["_ord"]).reset_index(drop=True)

    # Filter controls
    fc1, fc2, fc3 = st.columns([2, 2, 4])
    with fc1:
        type_filter = st.multiselect("Type", ["📈 TA", "📰 news"], default=[],
                                        placeholder="both", label_visibility="collapsed")
    with fc2:
        verdict_filter = st.multiselect(
            "Verdicts",
            sorted({v["Verdict"] for v in qv_rows}),
            default=[], placeholder="all verdicts", label_visibility="collapsed")
    with fc3:
        stock_search = st.text_input("Search stock", placeholder="🔍 filter by ticker",
                                        label_visibility="collapsed")

    view_df = qv_df.copy()
    if type_filter:    view_df = view_df[view_df["Type"].isin(type_filter)]
    if verdict_filter: view_df = view_df[view_df["Verdict"].isin(verdict_filter)]
    if stock_search:   view_df = view_df[view_df["Stock"].str.contains(stock_search.upper(), na=False)]

    if view_df.empty:
        st.info("No stocks match the filter.")
    else:
        st.dataframe(
            view_df, hide_index=True, use_container_width=True,
            height=min(60 + 35*len(view_df), 600),
            column_config={
                "Stock":       st.column_config.TextColumn("Stock", width="small"),
                "Type":        st.column_config.TextColumn("Type", width="small"),
                "Category":    st.column_config.TextColumn("Cat", width="small"),
                "Sector":      st.column_config.TextColumn("Sector", width="medium"),
                "Verdict":     st.column_config.TextColumn("Verdict", width="medium"),
                "Signal ₹":    st.column_config.NumberColumn("Signal ₹", format="₹%.2f", width="small"),
                "Now ₹":       st.column_config.NumberColumn("Now ₹",    format="₹%.2f", width="small"),
                "Return %":    st.column_config.NumberColumn("Return %",  format="%+.1f%%", width="small"),
                "Peak %":      st.column_config.NumberColumn("Peak %",    format="%+.1f%%", width="small"),
                "Deviation %": st.column_config.NumberColumn("Dev pp",    format="%+.1f", width="small"),
                "Target ₹":    st.column_config.NumberColumn("Target ₹",  format="₹%.2f", width="small"),
                "Stop ₹":      st.column_config.NumberColumn("Stop ₹",    format="₹%.2f", width="small"),
                "Days":        st.column_config.TextColumn("Days", width="small"),
                "News (sig→now)": st.column_config.TextColumn("News", width="small"),
                "Note":        st.column_config.TextColumn("Note", width="large"),
            })

        st.download_button("⬇️ Download quick view CSV",
                            view_df.to_csv(index=False).encode(),
                            file_name=f"wishlist_quick_view_{dt.date.today()}.csv",
                            mime="text/csv")

    # -------- Visual return chart (bar chart of current return %, sorted) --------
    if not view_df.empty:
        st.markdown("**📊 Current return % — all stocks (sorted best → worst)**")
        chart_df = view_df[["Stock", "Return %"]].copy().set_index("Stock")
        chart_df = chart_df.sort_values("Return %", ascending=False)
        st.bar_chart(chart_df, height=max(300, min(20 * len(chart_df), 700)))
        st.caption("Green bars = gains since signal · Red bars = losses. "
                    "Longer bars = larger moves in either direction.")

    st.divider()

    # ============================================================
    # PER-STOCK CARDS (drill-down)
    # ============================================================
    st.markdown("### 🔍 Per-stock verdicts (expand for full detail)")

    for r in results:
        _render_wishlist_card(r)

    # ============================================================
    # OBSERVATION LOG DOWNLOAD + PROMOTE HELPERS
    # ============================================================
    st.divider()
    st.markdown("### 📜 Observation log (append-only)")
    obs_all = _load_observation_log()
    if not obs_all.empty:
        st.caption(f"{len(obs_all)} total observations across "
                    f"{obs_all['ticker'].nunique()} tickers, "
                    f"{obs_all['observation_date'].nunique()} distinct days.")
        st.dataframe(obs_all.tail(200), use_container_width=True, hide_index=True,
                      height=min(60 + 32*min(len(obs_all), 20), 500))
        st.download_button("⬇️ Download full observation log",
                            obs_all.to_csv(index=False).encode(),
                            file_name="wishlist_observations.csv",
                            mime="text/csv")
    else:
        st.info("Observation log is empty — first run adds today's entries.")


def _render_wishlist_card(r):
    """Detail card per wishlist stock, tabbed."""
    if r.get("status") == "NO_DATA":
        with st.expander(f"⚪ {r['ticker']} — NO DATA"):
            st.warning(r.get("note", "No data available"))
        return

    ico, colour, _ = VERDICT_STYLE.get(r["status"], ("•", "#374151", "info"))
    label = r["label"]
    ret = r.get("current_return_pct", 0)
    dev = r.get("deviation_pct", 0)
    cat = r.get("category") or "?"
    reg = r.get("regime_at_signal") or "?"
    regime_emoji = {"RISK-ON": "🟢", "NEUTRAL": "🟡", "RISK-OFF": "🔴", "UNKNOWN": "⚪"}.get(reg, "⚪")
    header = (f"{ico} **{r['ticker']}** · 📦 {cat} · "
              f"🏭 {r.get('sector','-') or '-'} · "
              f"{regime_emoji} regime {reg} · "
              f"**{label}** · return {ret:+.1f}% "
              f"(dev {dev:+.1f}pp) · "
              f"{r['days_elapsed']}/{r['expected_days']}d")
    with st.expander(header):
        # Provenance
        src_bits = []
        if r.get("price_source"):
            asof = r.get("price_asof")
            asof_str = (asof.strftime("%Y-%m-%d %H:%M") if hasattr(asof, "strftime")
                        else str(asof) if asof else "n/a")
            src_bits.append(f"💰 {r['price_source']} ({asof_str})")
        if r.get("stop_source"):        src_bits.append(f"🛑 {r['stop_source']}")
        if r.get("expected_days_source"): src_bits.append(
            f"⏱️ expected_days: {r['expected_days_source']}")
        if r.get("sector_source"):      src_bits.append(f"🏭 sector: {r['sector_source']}")
        if src_bits: st.caption("Data → " + "  ·  ".join(src_bits))

        # Safe format helpers — guard against None on news-only rows
        def _fp(v, prefix="₹", fmt=".2f"):
            if v is None or pd.isna(v): return "—"
            return f"{prefix}{v:{fmt}}"
        def _fpct(v, fmt="+.1f"):
            if v is None or pd.isna(v): return "—"
            return f"{v:{fmt}}%"

        # Tabs (news-only rows skip the Progress tab which needs target/stop)
        if r.get("is_news_only"):
            tab_ov, tab_ne, tab_hist = st.tabs([
                "📊 Overview", "📰 News detail", "📜 History",
            ])
            tab_prog = tab_ta = None
        else:
            tab_ov, tab_prog, tab_ta, tab_hist = st.tabs([
                "📊 Overview", "📈 Progress", "🧮 Technical", "📜 History",
            ])
            tab_ne = None

        # -------------------- OVERVIEW TAB --------------------
        with tab_ov:
            cA, cB, cC, cD = st.columns(4)
            cA.metric("Signal price", _fp(r.get("signal_price")),
                       f"{r.get('days_elapsed','?')}d ago")
            cB.metric("Now", _fp(r.get("current_price")),
                       _fpct(r.get("current_return_pct")))
            cC.metric("Target", _fp(r.get("target_price")))
            cD.metric("Stop",   _fp(r.get("stop_price")))

            # Verdict banner
            note = r.get("note", "")
            status_class = r.get("status", "")
            if status_class in ("TARGET_HIT", "AHEAD_OF_PACE", "ON_TRACK",
                                  "NEWS_CONFIRMED"):
                st.success(f"{ico} {label} — {note}")
            elif status_class in ("BEHIND_PACE", "NEWS_STALLED"):
                st.warning(f"{ico} {label} — {note}")
            elif status_class in ("NEWS_NEUTRAL",):
                st.info(f"{ico} {label} — {note}")
            else:
                st.error(f"{ico} {label} — {note}")

            # Peak-since-signal callout (only if we have valid price data)
            peak = r.get("peak_price_since_signal")
            cur = r.get("current_price")
            if peak and cur and peak > cur * 1.005:
                pk_ret = r.get("peak_return_pct", 0)
                st.info(f"🏔️ Peak since signal: **{_fp(peak)}** ({pk_ret:+.1f}%). "
                         f"Currently {_fp(cur)} — pulled back "
                         f"{100*(cur/peak-1):+.1f}% from peak.")

            # News score line (both TA and news-only rows have news info)
            news_at_sig = r.get("news_score_at_signal", 0) or 0
            news_now = (r.get("news") or {}).get("score", 0) or 0
            if news_at_sig or news_now:
                delta = news_now - news_at_sig
                arrow = "↗" if delta > 0.05 else "↘" if delta < -0.05 else "→"
                st.markdown(f"**📰 News:** at signal `{news_at_sig:+.2f}` "
                             f"{arrow} now `{news_now:+.2f}` "
                             f"(delta {delta:+.2f})")

            # Notes
            if r.get("notes"):
                st.caption(f"📝 Your notes: {r['notes']}")

            # Promote-to-positions helper (only for TA rows with real target/stop)
            if not r.get("is_news_only") and r.get("target_price") and r.get("stop_price"):
                with st.expander("🛒 Ready to buy? Promote to positions.csv"):
                    st.markdown(
                        f"Copy this row into `positions.csv` to start monitoring "
                        f"this position for real:\n\n"
                        f"```csv\n"
                        f"{r['ticker']},{dt.date.today().strftime('%d-%m-%Y')},"
                        f"{r['current_price']:.2f},<qty>,{r['stop_price']:.2f},"
                        f"{r['target_price']:.2f},"
                        f"{r['signal_date'].strftime('%d-%m-%Y')},"
                        f"{r.get('sector','')},{r.get('notes','')}"
                        f"\n```\n"
                        f"Or open `positions.csv` and add manually. "
                        f"Then delete this row from `wishlist.csv`."
                    )

        # -------------------- PROGRESS TAB (TA rows only) --------------------
        if tab_prog is not None:
            with tab_prog:
                target_price = r.get("target_price")
                signal_price = r.get("signal_price")
                current_price = r.get("current_price")
                stop_price = r.get("stop_price")
                if not (target_price and signal_price and current_price):
                    st.info("Insufficient price data to project progress.")
                else:
                    total_move = target_price - signal_price
                    actual_move = current_price - signal_price
                    progress_pct = 100 * actual_move / max(total_move, 0.01)
                    progress_clamped = max(0.0, min(1.0, actual_move / max(total_move, 0.01)))
                    st.markdown(f"**Progress to target: {progress_pct:.0f}%** "
                                f"({_fp(signal_price)} → {_fp(target_price)})")
                    st.progress(progress_clamped)

                    exp_days = r.get("expected_days") or 15
                    days_el = r.get("days_elapsed") or 0
                    time_pct = min(100, 100 * days_el / max(1, exp_days))
                    st.markdown(f"**Time elapsed: {time_pct:.0f}%** "
                                f"({days_el}d of {exp_days}d expected)")
                    st.progress(min(1.0, time_pct / 100))

                    colP1, colP2, colP3 = st.columns(3)
                    colP1.metric("Expected return by now",
                                  _fpct(r.get("expected_return_pct_by_now")))
                    colP2.metric("Actual return", _fpct(r.get("current_return_pct")))
                    dev = r.get("deviation_pct", 0)
                    dev_color = "normal" if dev >= 0 else "inverse"
                    colP3.metric("Deviation", f"{dev:+.1f}pp",
                                  "AHEAD" if dev > 0 else
                                  ("ON PACE" if abs(dev) < 1 else "BEHIND"),
                                  delta_color=dev_color)

                    st.markdown("**📐 Scenarios (from current price)**")
                    scen_rows = [
                        {"Scenario": f"🎯 Hits target ({_fp(target_price)})",
                         "Move needed": f"{100*(target_price/current_price-1):+.1f}%",
                         "Return from signal": f"{100*(target_price/signal_price-1):+.1f}%"},
                    ]
                    if stop_price:
                        scen_rows.append({
                            "Scenario": f"🛑 Hits stop ({_fp(stop_price)})",
                            "Move needed": f"{100*(stop_price/current_price-1):+.1f}%",
                            "Return from signal": f"{100*(stop_price/signal_price-1):+.1f}%",
                        })
                    st.dataframe(pd.DataFrame(scen_rows), hide_index=True,
                                  use_container_width=True)

        # -------------------- NEWS DETAIL TAB (news-only rows) --------------------
        if tab_ne is not None:
            with tab_ne:
                news_at_sig = r.get("news_score_at_signal", 0) or 0
                news_now = (r.get("news") or {}).get("score", 0) or 0
                n_articles = (r.get("news") or {}).get("n_articles", 0)
                delta = news_now - news_at_sig
                nc = st.columns(3)
                nc[0].metric("📰 News score at signal", f"{news_at_sig:+.2f}")
                nc[1].metric("📰 News score now", f"{news_now:+.2f}",
                              f"{delta:+.2f}",
                              delta_color=("normal" if delta > 0 else "inverse"))
                nc[2].metric("Articles now", n_articles)

                # Price drift since signal
                cur = r.get("current_price"); sig = r.get("signal_price")
                if cur and sig:
                    drift = 100 * (cur/sig - 1)
                    st.markdown(f"**Price drift since signal:** "
                                 f"{_fp(sig)} → {_fp(cur)}  =  **{drift:+.2f}%**")

                st.markdown(f"**Original notes:** {r.get('notes','—')}")

                # Interpretation
                if abs(news_at_sig) >= 0.15:
                    if abs(delta) > 0.2:
                        st.warning("🔄 **News sentiment has shifted materially** since signal — "
                                    "re-evaluate before acting.")
                    if r.get("status") == "NEWS_CONFIRMED":
                        st.success("✅ Market followed the news direction. Signal was predictive.")
                    elif r.get("status") == "NEWS_FAILED":
                        st.error("❌ Market moved AGAINST the news. Consider news scorer may over-read this stock's headlines.")
                    else:
                        st.info("🟡 Market hasn't reacted to the news yet. Watch for delayed response over next 3-5 sessions.")

        # -------------------- TECHNICAL TAB (TA rows only) --------------------
        if tab_ta is not None:
            with tab_ta:
                ta = r.get("ta") or {}
                if ta:
                    cols = st.columns(6)
                    def _mv(col, label, key, fmt="{:.1f}"):
                        v = ta.get(key)
                        if v is None or (isinstance(v, float) and not np.isfinite(v)):
                            col.metric(label, "—")
                        else:
                            col.metric(label, fmt.format(float(v)))
                    _mv(cols[0], "RSI(14)",    "rsi14")
                    _mv(cols[1], "%vs 20DMA",  "pct_vs_sma20", "{:+.1f}%")
                    _mv(cols[2], "%vs 50DMA",  "pct_vs_sma50", "{:+.1f}%")
                    _mv(cols[3], "%vs 200DMA", "pct_vs_sma200","{:+.1f}%")
                    _mv(cols[4], "ATR%",       "atr_pct",      "{:.1f}%")
                    _mv(cols[5], "ADX(14)",    "adx14")
                    st.caption("TA state at last close. Compare to the state that "
                                "was expected when the signal fired.")
                news = r.get("news") or {}
                if news.get("n_articles", 0) > 0:
                    st.markdown(f"**📰 News score:** {news['score']:+.2f} "
                                 f"({news['n_articles']} articles)")
                    if news.get("top_headline"):
                        st.caption(f"Top: \"{news['top_headline'][:200]}\"")

        with tab_hist:
            # Historical observations for THIS ticker only
            obs_all = _load_observation_log()
            if obs_all.empty:
                st.info("No observations logged yet.")
            else:
                mine = obs_all[obs_all["ticker"] == r["ticker"]].copy()
                if mine.empty:
                    st.info("No prior observations for this ticker.")
                else:
                    mine["observation_date"] = pd.to_datetime(mine["observation_date"])
                    mine = mine.sort_values("observation_date", ascending=False)
                    st.markdown(f"**{len(mine)} observation(s) logged for {r['ticker']}**")

                    show_cols = ["observation_date", "days_elapsed",
                                 "current_price", "current_return_pct",
                                 "expected_return_pct_by_now", "deviation_pct",
                                 "verdict", "on_track_pct", "note"]
                    show_cols = [c for c in show_cols if c in mine.columns]
                    st.dataframe(mine[show_cols], hide_index=True,
                                  use_container_width=True,
                                  height=min(50 + 32*len(mine), 400))

                    # Little price/return sparkline
                    if len(mine) > 1:
                        chart_df = mine.sort_values("observation_date").set_index("observation_date")
                        st.markdown("**Return trend over observations:**")
                        st.line_chart(chart_df[["current_return_pct",
                                                  "expected_return_pct_by_now"]],
                                       height=200)


def main():
    st.set_page_config(page_title="Wishlist Tracker", layout="wide")
    body()


if __name__ == "__main__":
    main()
