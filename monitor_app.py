"""
Position Monitor (v1, Aug-2026)
================================
Daily position-management dashboard — the missing "SELL SIDE" of the swing
trading loop.

While `swing_scanner_app.py` finds NEW setups (buy side), this app looks at
YOUR EXISTING HOLDINGS and asks, for each one:
   * Should I hold?
   * Should I raise my stop?
   * Should I take some off?
   * Should I get out entirely?
   * Should I add more?

Uses the same engine (swing_screener_app.py), same news scorer, same event
fetcher as the scanner — but with position-management decision logic instead
of new-signal generation.

USAGE
-----
    streamlit run monitor_app.py

INPUT
-----
    positions.csv (next to this file) — one row per open long position.
    See the header comment inside positions.csv for the exact schema and how
    to populate it from your scanner output.

DECISION LOGIC (evaluated top-down; first match wins for the ACTION):
    ┌─────────────────────────────────────────────────────────────────────┐
    │ TIER 1 — URGENT EXIT (no override, protects capital)               │
    │   1a  Stop-loss hit                                                 │
    │   1b  Scheduled event (results/AGM/split/etc.) within 2 sessions   │
    │   1c  Severe negative news (score < -0.5 AND >= 2 articles)         │
    │                                                                     │
    │ TIER 2 — EXIT (trend broken)                                        │
    │   2a  >= 2 technical breakdown signals                              │
    │                                                                     │
    │ TIER 3 — REDUCE (book half)                                         │
    │   3a  Moderate negative news (score < -0.3, >= 2 articles)          │
    │   3b  Exactly 1 breakdown signal AND position in loss               │
    │                                                                     │
    │ TIER 4 — HOLD  (position stays; refinements applied below)          │
    │   4a  Ratchet stop suggestion (see ladder)                          │
    │   4b  Add-on signal (only for winners in a favourable regime)       │
    │                                                                     │
    │ TIER 5 — HOLD (default, TA intact)                                  │
    └─────────────────────────────────────────────────────────────────────┘

RATCHET LADDER (as-you-earn stop tightening):
    +5%  gain → raise stop to break-even
    +10% gain → raise stop to +3%
    +20% gain → raise stop to +12%
    +30% gain → raise stop to +20%
    +40% gain → raise stop to +28%
    +50% gain → raise stop to +37%
    +75% gain → raise stop to +60%
   +100% gain → raise stop to +80%
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


# ======================================================================================
#  ENGINE LOADER — reuse the swing engine
# ======================================================================================
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINE_PATH = os.path.join(_HERE, "swing_screener_app.py")
_spec = importlib.util.spec_from_file_location("engine", _ENGINE_PATH)
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)

# Optional modules — news + events + sector
try:
    from news_sentiment import fetch_news_score as _news_score
    HAVE_NEWS = True
except Exception:
    HAVE_NEWS = False

try:
    from nse_events import event_risk as _event_risk
    HAVE_EVENTS = True
except Exception:
    HAVE_EVENTS = False

try:
    from universe_loader import load_full_universe as _ul_load
    HAVE_UNIVERSE = True
except Exception:
    HAVE_UNIVERSE = False


POSITIONS_CSV = os.path.join(_HERE, "positions.csv")
BENCH_TICKERS = ["^CRSLDX", "^NSEI"]


# ======================================================================================
#  DATA HELPERS
# ======================================================================================
def _to_yahoo(sym: str) -> str:
    s = str(sym).strip().upper()
    return s if s.endswith((".NS", ".BO")) else s + ".NS"


@st.cache_data(ttl=15 * 60, show_spinner=False)   # 15 min (was 60) — fresher price
def _fetch_stock(ticker_yahoo: str, days: int = 400) -> pd.DataFrame:
    """SPLIT-ADJUSTED daily history (auto_adjust=True) — used for indicator
    computation (RSI, MACD, ATR etc. need adjusted series so ratios are
    correct across corporate actions). This is NOT the series used for
    the 'current price' display — see `_fetch_live_price()` below."""
    if yf is None:
        return pd.DataFrame()
    end = dt.date.today() + dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
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


@st.cache_data(ttl=5 * 60, show_spinner=False)   # 5 min — live-ish price
def _fetch_live_price(ticker_yahoo: str) -> dict:
    """Fetch the CURRENT (or last-tick) UNADJUSTED market price.
    This is what appears on your broker screen — it matches your buy_price
    apples-to-apples. Falls back gracefully through:
       1. Ticker.fast_info.last_price       (live-ish; sub-minute)
       2. 1-minute intraday history         (most recent bar)
       3. Daily close (unadjusted)          (yesterday's close)
    Returns {price: float, as_of: date/datetime, source: str}.
    """
    if yf is None:
        return {"price": None, "as_of": None, "source": "yfinance unavailable"}
    try:
        t = yf.Ticker(ticker_yahoo)
    except Exception as e:
        return {"price": None, "as_of": None, "source": f"error: {str(e)[:40]}"}

    # 1. fast_info.last_price — the freshest source
    try:
        fi = t.fast_info
        p = float(getattr(fi, "last_price", None) or fi["lastPrice"])
        if p and p > 0:
            return {"price": round(p, 2), "as_of": dt.datetime.now(),
                    "source": "live (fast_info)"}
    except Exception:
        pass

    # 2. 1-minute intraday — most recent complete bar
    try:
        intra = t.history(period="1d", interval="1m")
        if intra is not None and not intra.empty:
            last = intra.iloc[-1]
            return {"price": round(float(last["Close"]), 2),
                    "as_of":  intra.index[-1].to_pydatetime(),
                    "source": "1-min intraday"}
    except Exception:
        pass

    # 3. Daily unadjusted close — fallback
    try:
        daily = t.history(period="5d", interval="1d", auto_adjust=False)
        if daily is not None and not daily.empty:
            last = daily.iloc[-1]
            return {"price": round(float(last["Close"]), 2),
                    "as_of":  daily.index[-1].to_pydatetime().date(),
                    "source": "daily close (unadjusted)"}
    except Exception:
        pass

    return {"price": None, "as_of": None, "source": "no data"}


@st.cache_data(ttl=60 * 60, show_spinner=False)
def _fetch_bench(days: int = 400):
    if yf is None:
        return None, pd.DataFrame()
    end = dt.date.today() + dt.timedelta(days=1)
    start = end - dt.timedelta(days=days)
    for t in BENCH_TICKERS:
        try:
            df = yf.Ticker(t).history(start=start, end=end,
                                       interval="1d", auto_adjust=True)
            if df is not None and not df.empty:
                df = df[["Open", "High", "Low", "Close"]].copy()
                df.index = pd.to_datetime(df.index).tz_localize(None)
                return t, df.dropna()
        except Exception:
            continue
    return None, pd.DataFrame()


def _regime_from_bench(bench_df: pd.DataFrame) -> str:
    if bench_df.empty or len(bench_df) < 210:
        return "UNKNOWN"
    c = bench_df["Close"]
    s200 = float(c.rolling(200).mean().iloc[-1])
    last = float(c.iloc[-1])
    above = last > s200
    roc10 = (c.iloc[-1] / c.iloc[-11] - 1) * 100 if len(c) > 11 else 0.0
    if above and roc10 > -1.0: return "RISK-ON"
    if above or roc10 > -3.0:  return "NEUTRAL"
    return "RISK-OFF"


# ======================================================================================
#  POSITIONS CSV LOADER
# ======================================================================================
# What's TRULY required vs OPTIONAL after v2:
#   REQUIRED : ticker, buy_date, buy_price, quantity
#   OPTIONAL : stop_loss (auto-derived from 2xATR if blank),
#              target     (advisory only — if blank, we still work),
#              signal_date (defaults to buy_date - 1),
#              sector     (auto-filled from universe loader),
#              notes      (free text)
REQUIRED_COLS = ("ticker", "buy_date", "buy_price", "quantity")
OPTIONAL_COLS = ("stop_loss", "target", "signal_date", "sector", "notes")

import re as _re
_TICKER_ALLOWED = _re.compile(r"[^A-Z0-9&\-]")


def _clean_ticker(raw: str) -> str:
    """Strip Unicode artefacts / stray whitespace from a ticker.
    NSE symbols use A-Z, 0-9, '&', '-'. Everything else gets stripped.
    e.g. 'SAREGAMA�' -> 'SAREGAMA'; 'M&M' -> 'M&M' unchanged."""
    if not isinstance(raw, str):
        return ""
    s = raw.strip().upper()
    s = _TICKER_ALLOWED.sub("", s)
    return s


def _parse_flex_date(v):
    """Try DD-MM-YYYY first (user's format), then fall back to pandas default.
    Returns a `date` or None."""
    if pd.isna(v) or str(v).strip() in ("", "nan", "None"):
        return None
    s = str(v).strip()
    # Try DD-MM-YYYY explicit
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Last-resort pandas parser (dayfirst=True to prefer 03-08-2026 = 3 Aug not 8 Mar)
    try:
        return pd.to_datetime(s, dayfirst=True, errors="coerce").date()
    except Exception:
        return None


def load_positions(path: str = POSITIONS_CSV) -> tuple:
    """Return (df, errors). Positions with missing OPTIONAL fields still load
    — those fields get auto-derived downstream. Only rows missing REQUIRED
    fields (ticker, buy_date, buy_price, quantity) are dropped."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=list(REQUIRED_COLS) + list(OPTIONAL_COLS)), \
               [f"File not found: {path}"]
    # Read with encoding fallback — user files sometimes contain non-UTF8
    # bytes (Windows-1252 quotes/dashes, Unicode replacement chars from
    # copy/paste). Try encodings in order; last resort uses error replacement.
    df = None
    read_err = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            df = pd.read_csv(path, comment="#", skip_blank_lines=True, encoding=enc)
            break
        except Exception as e:
            read_err = e
            continue
    if df is None:
        # Absolute fallback: read as bytes, drop non-decodable characters
        try:
            with open(path, "rb") as f:
                raw_bytes = f.read()
            text = raw_bytes.decode("utf-8", errors="replace")
            df = pd.read_csv(io.StringIO(text), comment="#", skip_blank_lines=True)
        except Exception as e:
            return pd.DataFrame(), [f"Read error: {read_err} / {e}"]
    df.columns = [c.strip().lower() for c in df.columns]

    errors = []
    for c in REQUIRED_COLS:
        if c not in df.columns:
            errors.append(f"Missing required column: {c}")
    if errors:
        return pd.DataFrame(), errors

    # Fill any missing optional columns as empty
    for c in OPTIONAL_COLS:
        if c not in df.columns:
            df[c] = np.nan

    # SANITIZE tickers (strip Unicode replacement chars, whitespace, non-symbol chars)
    original_tickers = df["ticker"].astype(str).copy()
    df["ticker"] = original_tickers.apply(_clean_ticker)
    cleaned_map = {orig: new for orig, new in zip(original_tickers, df["ticker"])
                   if orig.strip() != new and new}
    if cleaned_map:
        errors.append("Cleaned corrupted ticker(s): "
                      + ", ".join(f"'{o.strip()}' -> '{n}'" for o, n in cleaned_map.items()))

    # Drop blank tickers and obvious example rows
    df = df[df["ticker"].str.len() > 0]
    df = df[~df["ticker"].str.contains("EXAMPLE", na=False)]
    if df.empty:
        return df, ["No real positions found. Edit positions.csv and re-run."]

    # Coerce numerics
    for c in ("buy_price", "quantity", "stop_loss", "target"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Flexible date parsing (DD-MM-YYYY, YYYY-MM-DD, both slashes and dashes)
    df["buy_date"]    = df["buy_date"].apply(_parse_flex_date)
    df["signal_date"] = df["signal_date"].apply(_parse_flex_date)

    # Fill signal_date default = buy_date - 1 (day before fill)
    def _sig_default(row):
        if row["signal_date"] is not None:
            return row["signal_date"]
        if row["buy_date"] is not None:
            return row["buy_date"] - dt.timedelta(days=1)
        return None
    df["signal_date"] = df.apply(_sig_default, axis=1)

    # Sector / notes: leave NaN → treated as blank downstream
    for c in ("sector", "notes"):
        df[c] = df[c].fillna("").astype(str)

    # ROW-LEVEL VALIDATION: only REQUIRED fields must be present
    bad_mask = (df["buy_price"].isna() | df["quantity"].isna() | df["buy_date"].isna()
                | (df["ticker"].str.len() == 0))
    bad = df[bad_mask]
    if not bad.empty:
        errors.append(f"{len(bad)} row(s) dropped for missing REQUIRED fields: "
                      f"{list(bad['ticker'])}")
    df = df[~bad_mask].reset_index(drop=True)

    # Flag rows that will need auto-derivation (informational, not an error)
    n_missing_stop   = int(df["stop_loss"].isna().sum())
    n_missing_sector = int((df["sector"].str.strip() == "").sum())
    n_missing_target = int(df["target"].isna().sum())
    if n_missing_stop:
        errors.append(f"ℹ️ {n_missing_stop} row(s) have no stop_loss "
                      f"— will be auto-derived from 2×ATR at load time.")
    if n_missing_sector:
        errors.append(f"ℹ️ {n_missing_sector} row(s) have no sector — will auto-fill from NSE map.")
    if n_missing_target:
        errors.append(f"ℹ️ {n_missing_target} row(s) have no target — advisory field, safe to omit.")

    return df, errors


# ======================================================================================
#  DECISION LOGIC
# ======================================================================================
# Ratchet ladder: (min_gain_pct, floor_pct_of_entry)
RATCHET_LADDER = [
    (5.0,    0.0),
    (10.0,   3.0),
    (20.0,  12.0),
    (30.0,  20.0),
    (40.0,  28.0),
    (50.0,  37.0),
    (75.0,  60.0),
    (100.0, 80.0),
]


def _ratchet_stop(entry_price: float, pnl_pct: float, current_stop: float) -> float:
    """Return the highest floor from the ladder that pnl_pct qualifies for,
    strictly greater than current_stop. Returns None if no raise applies."""
    best = None
    for peak, floor in RATCHET_LADDER:
        if pnl_pct >= peak:
            candidate = entry_price * (1 + floor / 100)
            if candidate > current_stop:
                best = candidate
    return round(best, 2) if best is not None else None


# ======================================================================================
#  ADAPTIVE RATCHET  (v2, Aug-2026) — replaces the fixed ladder
# ======================================================================================
# The v1 fixed ladder gave uneven give-back:
#   +5%  → floor +0%  (give-back 5pp)
#   +10% → floor +3%  (give-back 7pp)
#   +20% → floor +12% (give-back 8pp)
#   +30% → floor +20% (give-back 10pp)
# Problem: at +17%, applied the +10% rung → new floor +3% → **giving back 14pp**
# — user's exact complaint. Also fixed give-back ignores volatility: 5pp is
# fine for TCS (ATR 1.5%) but way too tight for ADANIENT (ATR 4%+).
#
# v2 adaptive give-back:
#   give_back = clamp(ATR% × 2, 3, 8)         # 3-8pp, scaled to volatility
#   new_floor = pnl_pct - give_back
# So +17% on a 2.5% ATR stock → give-back 5pp → new floor +12%
# And  +17% on a 4.5% ATR stock → give-back 8pp → new floor +9%
# — matches what the volatility actually justifies.
def _adaptive_ratchet(entry_price: float, pnl_pct: float,
                       current_stop: float, atr_pct: float,
                       min_gain_to_arm: float = 5.0) -> tuple:
    """Adaptive ratchet: give-back scaled by volatility.
    Returns (new_stop_price, give_back_pp) or (None, None) if no raise applies.

    Only ARMS when pnl_pct >= min_gain_to_arm (5% by default) — below that,
    let the original stop protect you; a 3-day trade at +2% shouldn't be
    micro-managed.
    """
    if pnl_pct < min_gain_to_arm:
        return None, None
    # Give-back range: 3pp minimum (never tighter for very calm stocks), 8pp max
    atr = float(atr_pct) if pd.notna(atr_pct) and atr_pct > 0 else 3.0
    give_back = max(3.0, min(atr * 2.0, 8.0))
    new_floor_pct = pnl_pct - give_back
    if new_floor_pct <= 0:
        return None, None                # not yet at break-even + give_back
    candidate = entry_price * (1 + new_floor_pct / 100)
    if candidate <= current_stop:
        return None, None                # ratchet only raises, never lowers
    return round(candidate, 2), round(give_back, 1)


def _detect_exhaustion(ta: dict, pnl_pct: float, days_held: int) -> tuple:
    """Detect exhaustion in a fast winner (+10-25% in ≤10 days).
    Returns (score 0-4, list of triggered signals).

    Signals (each worth 1 point):
      A. RSI > 75  — overbought
      B. BB %B > 95 — riding upper Bollinger band
      C. Vol ratio < 0.9 on new highs — momentum fading (volume divergence)
      D. Price > 8% above 20-DMA — extended, mean-reversion risk

    Trigger BOOK_PARTIAL when score >= 2 AND rapid gain (+10-25% in ≤10 days).
    """
    triggers = []
    def _f(k, default):
        v = ta.get(k, default)
        return float(v) if pd.notna(v) else default
    if _f("rsi14", 50)      > 75: triggers.append("RSI overbought (>75)")
    if _f("bb_pctB", 50)    > 95: triggers.append("riding upper Bollinger (%B>95)")
    if _f("vol_ratio", 1.0) < 0.9 and pnl_pct >= 10:
        triggers.append("volume fading on new highs")
    if _f("pct_vs_sma20", 0) > 8:
        triggers.append(f"price {ta['pct_vs_sma20']:+.1f}% above 20-DMA (extended)")
    return len(triggers), triggers


def _expected_range(entry_price: float, current_price: float,
                     atr_pct: float, days_ahead: int = 5) -> dict:
    """Statistical price-range projection for the next `days_ahead` sessions.
    Uses ATR-scaled random walk: expected 1-sigma range = ATR × sqrt(days).
    Returns {low, high, base, move_pct}."""
    if not pd.notna(atr_pct) or atr_pct <= 0:
        return {"low": None, "high": None, "base": current_price, "move_pct": None}
    daily_sigma = atr_pct / 100.0
    move = daily_sigma * (days_ahead ** 0.5)
    return {
        "low":  round(current_price * (1 - move), 2),
        "high": round(current_price * (1 + move), 2),
        "base": current_price,
        "move_pct": round(move * 100, 1),
    }


# ======================================================================================
#  TARGET-PROJECTION HELPERS (Aug-2026) — answer the "when + how far" question
# ======================================================================================
def _historical_target_stats(df_ind, target_pct: float = 15.0,
                              window_days: int = 30, lookback: int = 500) -> dict:
    """Backward-scan of price history: how OFTEN did this stock post a
    target_pct% gain within a window_days rolling window, and how long did
    it typically take? Uses only the last `lookback` bars (~2 years) so
    stale eras don't dominate.

    Returns {med_days, min_days, occurrences, hit_rate_%}.
    """
    if df_ind is None or df_ind.empty:
        return {"med_days": None, "min_days": None, "occurrences": 0, "hit_rate": None}
    close = df_ind["Close"].values
    n = min(len(close), lookback)
    close = close[-n:]
    if n < window_days + 5:
        return {"med_days": None, "min_days": None, "occurrences": 0, "hit_rate": None}
    tgt_mult = 1 + target_pct / 100.0
    days_taken = []
    starts = 0
    for i in range(0, n - window_days):
        starts += 1
        target = close[i] * tgt_mult
        max_j = min(i + window_days, n - 1)
        for j in range(i + 1, max_j + 1):
            if close[j] >= target:
                days_taken.append(j - i)
                break
    if not days_taken:
        return {"med_days": None, "min_days": None,
                "occurrences": 0, "hit_rate": 0.0}
    return {
        "med_days":    int(np.median(days_taken)),
        "min_days":    int(np.min(days_taken)),
        "occurrences": len(days_taken),
        "hit_rate":    round(100 * len(days_taken) / starts, 1),
    }


def _project_days_to_target(entry: float, current: float, target_price: float,
                              ta: dict, df_ind) -> dict:
    """Estimate how many trading days until price reaches target_price.

    Combines two methods:
      A. Historical velocity — median time a similar % gain took on THIS stock
      B. Current momentum   — extrapolate from recent 5-day price velocity
    Returns dict with base, low, high days estimates + momentum_state label.
    """
    if not (current and target_price and target_price > current):
        # Already at/above target — no more days needed
        return {"days_low": 0, "days_base": 0, "days_high": 0,
                "momentum_state": "at_target", "method": "already-there",
                "hist_stats": None, "target_pct_from_now": 0.0}
    pct_needed = (target_price / current - 1) * 100
    close = df_ind["Close"].values if df_ind is not None else None

    # A. Historical velocity — how long does a `pct_needed` gain typically take?
    hist_stats = _historical_target_stats(df_ind, target_pct=pct_needed,
                                            window_days=30, lookback=500)

    # B. Current momentum — 5-day velocity
    daily_vel = None
    if close is not None and len(close) > 5:
        ret_5d = (close[-1] / close[-6] - 1) * 100
        daily_vel = ret_5d / 5.0    # % per day
    # Trend context
    prev_5d = None
    if close is not None and len(close) > 10:
        prev_5d = (close[-6] / close[-11] - 1) * 100 / 5.0

    # Days estimate from velocity
    days_velocity = None
    if daily_vel and daily_vel > 0.1:      # meaningful upside momentum
        days_velocity = pct_needed / daily_vel

    # Blend the two — base = median of historical + velocity
    candidates = []
    if hist_stats["med_days"]:  candidates.append(float(hist_stats["med_days"]))
    if days_velocity:           candidates.append(float(days_velocity))
    if not candidates:
        return {"days_low": None, "days_base": None, "days_high": None,
                "momentum_state": "unknown", "method": "no data",
                "hist_stats": hist_stats, "target_pct_from_now": round(pct_needed, 2)}
    base = int(np.median(candidates))
    low  = int(max(1, min(candidates) * 0.7))
    high = int(max(base + 1, max(candidates) * 1.5))

    # Momentum-state label
    if daily_vel is None:
        state = "unknown"
    elif prev_5d is not None and daily_vel > prev_5d * 1.15:
        state = "accelerating ↑"
    elif prev_5d is not None and daily_vel < prev_5d * 0.85:
        state = "decelerating ↓"
    elif daily_vel > 0.2:
        state = "steady advance"
    elif daily_vel > 0:
        state = "flat / slow drift"
    else:
        state = "declining ↓"

    return {"days_low": low, "days_base": base, "days_high": high,
            "momentum_state": state,
            "method": "hist × velocity" if len(candidates) == 2 else
                       ("historical" if hist_stats["med_days"] else "velocity"),
            "hist_stats": hist_stats,
            "current_velocity_pct_per_day": round(daily_vel, 3) if daily_vel else None,
            "target_pct_from_now": round(pct_needed, 2)}


def _project_price_ceiling(entry: float, current: float, ta: dict, df_ind,
                            days_ahead: int = 30) -> dict:
    """Estimate the realistic price ceiling over the next `days_ahead` sessions.

    Layered analysis:
      1. Immediate resistance   — 20-day high
      2. Medium-term ceiling    — 52-week high
      3. Statistical maximum    — current × (1 + ATR% × sqrt(days) / 100 × 1.5)
                                  (1.5× ATR-drift = upper edge of bullish 1σ path)
      4. If already past 52-week high, use ATR-projection alone
    """
    result = {
        "immediate_resistance": None,
        "medium_ceiling":       None,
        "statistical_max":      None,
        "pnl_from_entry_at_ceiling": {},
        "notes": [],
    }
    if df_ind is None or df_ind.empty:
        return result
    high_series = df_ind["High"]
    close = df_ind["Close"]
    # 1. Immediate resistance = highest high in the last 20 sessions (excluding today)
    if len(high_series) >= 21:
        imm = float(high_series.iloc[-21:-1].max())
        if imm > current * 1.005:            # only useful if it's ABOVE now
            result["immediate_resistance"] = round(imm, 2)
            result["pnl_from_entry_at_ceiling"]["immediate"] = \
                round((imm / entry - 1) * 100, 1)

    # 2. Medium ceiling = 52-week high
    if len(high_series) >= 252:
        wk52_high = float(high_series.iloc[-252:].max())
    else:
        wk52_high = float(high_series.max())
    result["medium_ceiling"] = round(wk52_high, 2)
    result["pnl_from_entry_at_ceiling"]["52w_high"] = \
        round((wk52_high / entry - 1) * 100, 1)
    if current > wk52_high * 0.99:
        result["notes"].append(
            "already at/near 52-week high — no historical resistance overhead")

    # 3. Statistical max via ATR × sqrt(days) × 1.5 (bullish drift edge)
    atr_pct = ta.get("atr_pct", None)
    if pd.notna(atr_pct) and atr_pct > 0:
        max_move_pct = atr_pct * (days_ahead ** 0.5) * 1.5
        stat_max = current * (1 + max_move_pct / 100)
        result["statistical_max"] = round(stat_max, 2)
        result["pnl_from_entry_at_ceiling"]["stat_max_30d"] = \
            round((stat_max / entry - 1) * 100, 1)

    # 4. Momentum context — is this a genuinely strong trend?
    if ta.get("adx14", 0) >= 25 and ta.get("macd_hist", 0) > 0:
        result["notes"].append(
            f"strong trend (ADX {ta.get('adx14',0):.0f}, MACD+) — "
            "ceiling estimates on the higher side")
    elif ta.get("adx14", 100) < 18:
        result["notes"].append(
            "weak trend (ADX < 18) — ceiling estimates on the lower side")

    return result


def _target_hit_probability(pnl_pct: float, target_pct: float, ta: dict,
                              hist_hit_rate: float = None,
                              days_held: int = 0, max_hold: int = 30) -> int:
    """Rough estimate of the probability of hitting `target_pct` gain
    within the remaining hold window. Combines:
      - historical hit rate for this stock (from _historical_target_stats)
      - progress-so-far (already-halfway? much more likely)
      - momentum bonus (uptrend adds probability)
      - time remaining (less time = lower probability)
    Returns 0-100 integer.
    """
    days_left = max(1, max_hold - days_held)
    # If already at/above target, probability is very high
    if pnl_pct >= target_pct:
        return 95
    remaining_pct = target_pct - pnl_pct

    base = hist_hit_rate if (hist_hit_rate is not None and hist_hit_rate > 0) else 30.0
    # Progress bonus — halfway there is a strong signal
    progress = pnl_pct / target_pct if target_pct > 0 else 0
    base += max(0, progress * 30)      # +0 at 0%, +30 at 100%
    # Momentum tilt
    if ta.get("macd_hist", 0) > 0:  base += 5
    if ta.get("adx14", 0) >= 25:    base += 5
    if ta.get("rsi14", 50) > 70:    base -= 5    # overbought — less headroom
    # Time-remaining haircut
    time_ratio = days_left / max_hold
    if time_ratio < 0.3:
        base *= 0.7          # <30% time left — much harder
    elif time_ratio < 0.5:
        base *= 0.85

    return int(max(5, min(base, 95)))


def _compute_confidence(action: str, score: dict, ta: dict, news: dict,
                         events: dict, urgency: str = "normal") -> int:
    """Return a 0-100 confidence for the recommendation.
    Higher = stronger signal alignment; lower = borderline / conflicted.

    Base:
      URGENT EXIT → 90 (stop-loss / event / severe news don't leave much room)
      EXIT        → 65 + |score|*2 clamped [55, 85]
      REDUCE      → 55 + |score| clamped [50, 75]
      BOOK_PARTIAL→ 70
      HOLD        → 50 + score*2 clamped [45, 85]

    Adjustments:
      +5 if news direction matches action (positive news + HOLD, neg news + EXIT)
      -5 if news CONTRADICTS action (positive news + EXIT feels wrong)
      +5 if regime supports (RISK-ON + HOLD; RISK-OFF + EXIT)
    """
    tot = score.get("total", 0) if score else 0
    ns  = news.get("score", 0.0) if news else 0.0
    nn  = news.get("n_articles", 0) if news else 0

    if urgency == "URGENT":
        base = 90
    elif action == "EXIT":
        base = 65 + min(abs(tot) * 2, 20)
    elif action == "REDUCE":
        base = 55 + min(abs(tot), 20)
    elif action == "BOOK_PARTIAL":
        base = 70
    elif action == "HOLD":
        base = 50 + max(-10, min(tot * 2, 35))
    else:
        base = 50
    base = max(35, min(base, 95))

    # News alignment
    if nn >= 2:
        if action in ("HOLD",) and ns >= 0.2:      base += 5
        if action in ("EXIT",) and ns <= -0.2:     base += 5
        if action in ("HOLD",) and ns <= -0.2:     base -= 5
        if action in ("EXIT",) and ns >= 0.2:      base -= 5

    # Regime alignment (via score's regime component)
    reg = score.get("regime", 0) if score else 0
    if action == "HOLD" and reg > 0: base += 3
    if action == "EXIT" and reg < 0: base += 3

    return int(max(30, min(base, 95)))


def _derive_stop_loss(buy_price: float, ta_snapshot: dict,
                       max_pct: float = 10.0, atr_mult: float = 2.0) -> tuple:
    """When user leaves stop_loss blank, compute a sensible default matching
    the scanner's convention: entry - 2×ATR, capped at max_pct (10%) loss.

    Returns (stop_price, method_str) where method_str explains the derivation.
    Never returns None — always produces a stop (10% flat if ATR unavailable).
    """
    atr_pct = ta_snapshot.get("atr_pct", np.nan)
    if pd.notna(atr_pct) and atr_pct > 0:
        # ATR-based stop
        atr_abs = buy_price * atr_pct / 100.0
        stop = buy_price - atr_mult * atr_abs
        floor = buy_price * (1 - max_pct / 100.0)
        stop = max(stop, floor)
        method = (f"2×ATR ({atr_pct:.1f}% ATR → {atr_mult*atr_pct:.1f}% risk), "
                  f"capped at {max_pct:.0f}%")
        return round(stop, 2), method
    # Fallback: flat 10% stop
    return round(buy_price * (1 - max_pct / 100.0), 2), \
           f"{max_pct:.0f}% flat (ATR unavailable)"


def _ta_snapshot(df_ind: pd.DataFrame) -> dict:
    """Extract a compact TA snapshot at the last bar."""
    if df_ind is None or df_ind.empty:
        return {}
    last = df_ind.iloc[-1]
    prev = df_ind.iloc[-2] if len(df_ind) > 1 else last
    # 10-day RSI max for "momentum peaked then broke down" check
    rsi_max_10d = float(df_ind["rsi14"].tail(10).max()) if "rsi14" in df_ind else np.nan
    return {
        "close":         float(last["Close"]),
        "pct_vs_sma20":  float(last.get("pct_vs_sma20", np.nan)),
        "pct_vs_sma50":  float(last.get("pct_vs_sma50", np.nan)),
        "pct_vs_sma200": float(last.get("pct_vs_sma200", np.nan)),
        "rsi14":         float(last.get("rsi14", np.nan)),
        "rsi_max_10d":   rsi_max_10d,
        "macd_hist":     float(last.get("macd_hist", np.nan)),
        "macd_hist_prev":float(prev.get("macd_hist", np.nan)),
        "atr_pct":       float(last.get("atr_pct", np.nan)),
        "vol_ratio":     float(last.get("vol_ratio", np.nan)),
        "dist_52wH":     float(last.get("dist_52wH", np.nan)),
        "adx14":         float(last.get("adx14", np.nan)),
        "signal_today":  bool(last.get("signal", False)),
    }


def _mk_check(category: str, name: str, value, verdict: str, note: str = "") -> dict:
    """Uniform check record — used for the audit table in the UI."""
    return {"category": category, "name": name, "value": value,
            "verdict": verdict, "note": note}


def _finalize(base: dict, ta: dict, news: dict, events: dict,
               entry: float, price: float) -> dict:
    """Attach confidence % + expected_range to any decide() return dict.
    Runs after the base dict is built so all decision paths get the same
    quality of downstream info. Idempotent — safe if fields already exist."""
    if "confidence" not in base or base["confidence"] is None:
        base["confidence"] = _compute_confidence(
            base.get("action", "HOLD"),
            base.get("score", {}),
            ta, news, events,
            urgency=base.get("urgency", "normal"),
        )
    if "expected_range" not in base or base["expected_range"] is None:
        base["expected_range"] = _expected_range(
            entry, price, ta.get("atr_pct", 3.0), days_ahead=5)
    return base


def decide(position: pd.Series, ta: dict, news: dict, events: dict,
           regime: str) -> dict:
    """Central decision engine. Runs a full battery of TA + News + Event
    checks, records EVERY check with pass/warn/fail badge, then maps the
    verdicts to a final action following a strict priority tree.

    Returns
    -------
    dict with:
        action        : "EXIT" | "REDUCE" | "HOLD" | "NO_DATA"
        urgency       : "URGENT" | "normal"
        pnl_pct, pnl_abs, days_held
        new_stop      : ratchet stop suggestion (or None)
        add_qty       : + integer for ADD, - integer for partial-book,
                        0 for no size change
        reasons       : [str] — high-level bullet list (shown in summary)
        narrative     : [str] — full multi-line story (shown in drill-down)
        checks        : [{category, name, value, verdict, note}] — audit
        score         : {ta, news, event, regime, ratchet, total}
    """
    entry = float(position["buy_price"])
    qty   = float(position["quantity"])
    stop  = float(position["stop_loss"])
    price = ta.get("close", entry)
    pnl_pct = (price / entry - 1) * 100 if np.isfinite(price) else 0.0
    pnl_abs = (price - entry) * qty     if np.isfinite(price) else 0.0
    days_held = (dt.date.today() - position["buy_date"]).days if position["buy_date"] else 0

    checks   = []
    narrative = []
    ta_score = news_score = event_score = 0

    # ---------------- 1. STOP-LOSS CHECK ----------------
    stop_hit = np.isfinite(price) and price <= stop
    checks.append(_mk_check(
        "stop", "Price vs stop-loss",
        f"₹{price:.2f} vs ₹{stop:.2f}",
        "FAIL" if stop_hit else "PASS",
        "STOP TOUCHED — capital preservation trigger" if stop_hit else
            f"cushion = ₹{price-stop:.2f} ({100*(price-stop)/price:.1f}%)"
    ))

    # ---------------- 2. EVENT CHECK ----------------
    ev_type = events.get("type")
    ev_days = events.get("days_until")
    ev_urgent = events.get("blocked") and ev_days is not None and ev_days <= 2
    if ev_type:
        checks.append(_mk_check(
            "event", f"Upcoming {ev_type}",
            f"{ev_days}d away",
            "FAIL" if ev_urgent else ("WARN" if (ev_days or 99) <= 5 else "INFO"),
            (events.get("subject") or "")[:120]
        ))
        if ev_urgent:
            event_score -= 10
        elif (ev_days or 99) <= 5:
            event_score -= 2
    else:
        checks.append(_mk_check("event", "Upcoming event risk",
                                 "none in next 5 sessions", "PASS", ""))

    # ---------------- 3. NEWS CHECKS ----------------
    ns = float(news.get("score", 0.0))
    nn = int(news.get("n_articles", 0))
    if nn == 0:
        checks.append(_mk_check("news", "News sentiment (5d)",
                                 "no articles", "INFO",
                                 "no news coverage found in last 5 sessions"))
    else:
        # Categorize
        if ns <= -0.5 and nn >= 2:
            label, verdict = "SEVERE NEGATIVE", "FAIL"
            news_score -= 10
        elif ns <= -0.3 and nn >= 2:
            label, verdict = "moderate negative", "WARN"
            news_score -= 4
        elif ns <= -0.15:
            label, verdict = "mildly negative", "WARN"
            news_score -= 1
        elif ns >= 0.5 and nn >= 2:
            label, verdict = "STRONG POSITIVE", "PASS"
            news_score += 4
        elif ns >= 0.15:
            label, verdict = "mildly positive", "PASS"
            news_score += 2
        else:
            label, verdict = "neutral", "INFO"
        top = (news.get("top_headline") or "")[:120]
        checks.append(_mk_check(
            "news", "News sentiment (5d)",
            f"{ns:+.2f} ({nn} articles) — {label}",
            verdict,
            top and f'top: "{top}"' or ""
        ))

    # ---------------- 4. TA CHECKS (each individually recorded) ----------------
    def _has(k): return k in ta and np.isfinite(ta.get(k, np.nan))

    # RSI
    if _has("rsi14"):
        rsi = ta["rsi14"]
        if rsi > 70:
            v = "WARN"; ta_score -= 1
            note = "overbought — susceptible to pullback"
        elif rsi < 40 and _has("rsi_max_10d") and ta["rsi_max_10d"] > 60:
            v = "FAIL"; ta_score -= 3
            note = f"momentum broke — peaked at {ta['rsi_max_10d']:.0f}"
        elif rsi < 30:
            v = "WARN"; ta_score -= 1
            note = "oversold — could be exhaustion or capitulation"
        else:
            v = "PASS"; ta_score += 1
            note = "in healthy range"
        checks.append(_mk_check("ta", "RSI(14)", f"{rsi:.1f}", v, note))

    # MACD histogram — 2 consecutive negative
    if _has("macd_hist") and _has("macd_hist_prev"):
        m, mp = ta["macd_hist"], ta["macd_hist_prev"]
        if m < 0 and mp < 0:
            v = "FAIL"; ta_score -= 3
            note = "negative 2 sessions — trend momentum broken"
        elif m < 0:
            v = "WARN"; ta_score -= 1
            note = "just flipped negative — 1st bar"
        else:
            v = "PASS"; ta_score += 1
            note = "positive — momentum with the trend"
        checks.append(_mk_check("ta", "MACD histogram",
                                 f"{m:+.2f} (prev {mp:+.2f})", v, note))

    # Price vs 20-DMA on volume
    if _has("pct_vs_sma20") and _has("vol_ratio"):
        p20, vr = ta["pct_vs_sma20"], ta["vol_ratio"]
        if p20 < -1 and vr > 1.2:
            v = "FAIL"; ta_score -= 3
            note = f"broke 20-DMA on heavy {vr:.1f}× volume — real distribution"
        elif p20 < -1:
            v = "WARN"; ta_score -= 1
            note = "below 20-DMA but light volume — may recover"
        elif p20 > 0:
            v = "PASS"; ta_score += 1
            note = "above short trend — continuation intact"
        else:
            v = "WARN"; ta_score += 0
            note = "under 20-DMA but not yet decisive"
        checks.append(_mk_check("ta", "Price vs 20-DMA",
                                 f"{p20:+.2f}% (vol {vr:.2f}×)", v, note))

    # Price vs 50-DMA
    if _has("pct_vs_sma50"):
        p50 = ta["pct_vs_sma50"]
        if p50 < 0 and pnl_pct < 0:
            v = "FAIL"; ta_score -= 2
            note = "below 50-DMA AND in loss — trend breakdown confirmed"
        elif p50 < 0:
            v = "WARN"; ta_score -= 1
            note = "below 50-DMA but still net-up — trend weakening"
        else:
            v = "PASS"; ta_score += 1
            note = "above intermediate trend"
        checks.append(_mk_check("ta", "Price vs 50-DMA",
                                 f"{p50:+.2f}%", v, note))

    # Price vs 200-DMA (long-trend context)
    if _has("pct_vs_sma200"):
        p200 = ta["pct_vs_sma200"]
        if p200 < 0:
            v = "WARN"; ta_score -= 1
            note = "below 200-DMA — long-term trend is DOWN"
        elif p200 > 15:
            v = "WARN"
            note = "extended > 15% above 200-DMA — mean-reversion risk"
        else:
            v = "PASS"; ta_score += 1
            note = "in healthy uptrend zone"
        checks.append(_mk_check("ta", "Price vs 200-DMA",
                                 f"{p200:+.2f}%", v, note))

    # ADX (trend strength)
    if _has("adx14"):
        adx = ta["adx14"]
        if adx >= 25:
            v = "PASS"; ta_score += 1
            note = "strong directional trend"
        elif adx >= 20:
            v = "INFO"
            note = "moderate trend"
        else:
            v = "WARN"
            note = "weak/no trend (choppy)"
        checks.append(_mk_check("ta", "ADX(14)", f"{adx:.1f}", v, note))

    # ATR% (volatility state)
    if _has("atr_pct"):
        atrp = ta["atr_pct"]
        if atrp > 7:
            v = "WARN"
            note = "very volatile — expect wide swings"
        elif atrp < 1.5:
            v = "INFO"
            note = "low volatility — quiet regime"
        else:
            v = "PASS"
            note = "typical volatility"
        checks.append(_mk_check("ta", "ATR%", f"{atrp:.2f}%", v, note))

    # ---------------- 5. REGIME + SIGNAL-TODAY (context) ----------------
    reg_verdict = {"RISK-ON": "PASS", "NEUTRAL": "INFO",
                   "RISK-OFF": "WARN", "UNKNOWN": "INFO"}.get(regime, "INFO")
    reg_score = {"RISK-ON": +2, "NEUTRAL": 0, "RISK-OFF": -2, "UNKNOWN": 0}[regime]
    checks.append(_mk_check("regime", "Market regime (bench)",
                             regime, reg_verdict,
                             {"RISK-ON": "supportive backdrop for longs",
                              "NEUTRAL": "mixed — take only leaders",
                              "RISK-OFF": "unfriendly — avoid new adds",
                              "UNKNOWN": "no benchmark data"}[regime]))

    if ta.get("signal_today"):
        checks.append(_mk_check("signal", "Scanner signal today?",
                                 "YES", "PASS",
                                 "engine's PASS_combined rule fires on today's bar"))
    else:
        checks.append(_mk_check("signal", "Scanner signal today?",
                                 "no", "INFO", ""))

    # ---------------- COMPUTE BREAKDOWN COUNT (for tier logic) ----------------
    breakdowns = [c for c in checks if c["category"] == "ta" and c["verdict"] == "FAIL"]

    # ================ DECISION PRIORITY TREE ================
    # ---------- TIER 1 : URGENT EXIT ----------
    if stop_hit:
        action, urgency = "EXIT", "URGENT"
        narrative.append(
            f"🛑 STOP-LOSS TOUCHED. Price ₹{price:.2f} closed at or below "
            f"your stop at ₹{stop:.2f}. Capital-preservation discipline: "
            f"exit at the next open regardless of other signals. Loss on this "
            f"trade: {pnl_pct:+.1f}% (₹{pnl_abs:+.0f})."
        )
        _ret = dict(action=action, urgency=urgency, pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                    days_held=days_held, new_stop=None, add_qty=0,
                    reasons=[narrative[0]],
                    narrative=narrative, checks=checks,
                    score=dict(ta=ta_score, news=news_score,
                               event=event_score, regime=reg_score,
                               ratchet=0, total=ta_score+news_score+event_score+reg_score))
        return _finalize(_ret, ta, news, events, entry, price)

    if ev_urgent:
        action, urgency = "EXIT", "URGENT"
        narrative.append(
            f"⚠️ IMMINENT EVENT ({ev_type} in {ev_days}d). Corporate actions "
            f"like results/AGM/split routinely produce 5-20% overnight gaps. "
            f"Exit before the event and re-evaluate on the post-event tape."
        )
        _ret = dict(action=action, urgency=urgency, pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                    days_held=days_held, new_stop=None, add_qty=0,
                    reasons=[narrative[0]],
                    narrative=narrative, checks=checks,
                    score=dict(ta=ta_score, news=news_score,
                               event=event_score, regime=reg_score,
                               ratchet=0, total=ta_score+news_score+event_score+reg_score))
        return _finalize(_ret, ta, news, events, entry, price)

    if ns <= -0.5 and nn >= 2:
        action, urgency = "EXIT", "URGENT"
        top = (news.get("top_headline") or "")[:120]
        narrative.append(
            f"📰 SEVERE NEGATIVE NEWS. Sentiment score {ns:+.2f} across "
            f"{nn} articles. Headlines of this severity (SEBI probe / auditor "
            f"resignation / large default / fraud allegation) historically "
            f"deliver -15 to -40% moves. Exit even if technicals still look OK."
        )
        if top: narrative.append(f'Top headline: "{top}"')
        _ret = dict(action=action, urgency=urgency, pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                    days_held=days_held, new_stop=None, add_qty=0,
                    reasons=[narrative[0]],
                    narrative=narrative, checks=checks,
                    score=dict(ta=ta_score, news=news_score,
                               event=event_score, regime=reg_score,
                               ratchet=0, total=ta_score+news_score+event_score+reg_score))
        return _finalize(_ret, ta, news, events, entry, price)

    # ---------- TIER 2 : EXIT (≥ 2 TA breakdowns) ----------
    if len(breakdowns) >= 2:
        action, urgency = "EXIT", "normal"
        detail = "; ".join(f"{c['name']} — {c['note']}" for c in breakdowns)
        narrative.append(
            f"🔻 MULTIPLE TA BREAKDOWNS ({len(breakdowns)}). The trend that "
            f"justified this position is broken. Exit at open."
        )
        narrative.append(f"Broken checks → {detail}")
        _ret = dict(action=action, urgency=urgency, pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                    days_held=days_held, new_stop=None, add_qty=0,
                    reasons=[narrative[0]],
                    narrative=narrative, checks=checks,
                    score=dict(ta=ta_score, news=news_score,
                               event=event_score, regime=reg_score,
                               ratchet=0, total=ta_score+news_score+event_score+reg_score))
        return _finalize(_ret, ta, news, events, entry, price)

    # ---------- TIER 3 : REDUCE (book half) ----------
    if -0.3 >= ns > -0.5 and nn >= 2:
        top = (news.get("top_headline") or "")[:120]
        narrative.append(
            f"📰 MODERATE NEGATIVE NEWS (score {ns:+.2f}, {nn} articles). "
            f"Not severe enough to force exit, but material enough to "
            f"reduce exposure. Book roughly half; reassess in 2-3 sessions."
        )
        if top: narrative.append(f'Top: "{top}"')
        _ret = dict(action="REDUCE", urgency="normal", pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                    days_held=days_held, new_stop=None,
                    add_qty=-int(qty // 2),
                    reasons=[narrative[0]],
                    narrative=narrative, checks=checks,
                    score=dict(ta=ta_score, news=news_score,
                               event=event_score, regime=reg_score,
                               ratchet=0, total=ta_score+news_score+event_score+reg_score))
        return _finalize(_ret, ta, news, events, entry, price)

    if len(breakdowns) == 1 and pnl_pct < 0:
        bd = breakdowns[0]
        narrative.append(
            f"⚠️ WARNING SIGNAL WHILE IN LOSS ({pnl_pct:+.1f}%). "
            f"{bd['name']} — {bd['note']}. One broken check plus red ink is "
            f"enough to trim exposure; book half and let the rest ride."
        )
        _ret = dict(action="REDUCE", urgency="normal", pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                    days_held=days_held, new_stop=None,
                    add_qty=-int(qty // 2),
                    reasons=[narrative[0]],
                    narrative=narrative, checks=checks,
                    score=dict(ta=ta_score, news=news_score,
                               event=event_score, regime=reg_score,
                               ratchet=0, total=ta_score+news_score+event_score+reg_score))
        return _finalize(_ret, ta, news, events, entry, price)

    # ---------- TIER 3.5 : BOOK_PARTIAL — fast winner showing exhaustion ----------
    # Trigger conditions ALL must hold:
    #   - Rapid gain: +10% to +25% in <=10 days (the "fast-mover" profile)
    #   - >= 2 exhaustion signals firing on today's bar
    #   - Not already in profit-take zone (>25% would be HOLD with adaptive ratchet)
    if 10 <= pnl_pct <= 25 and days_held <= 10:
        exh_score, exh_triggers = _detect_exhaustion(ta, pnl_pct, days_held)
        if exh_score >= 2:
            book_frac = 0.5 if exh_score >= 3 else 0.3    # 50% or 30% off
            book_qty = max(1, int(qty * book_frac))
            atr_pct_now = ta.get("atr_pct", 3.0)
            new_stop_partial, give_back = _adaptive_ratchet(entry, pnl_pct, stop, atr_pct_now)
            narrative.append(
                f"🎯 BOOK PARTIAL — you're up {pnl_pct:+.1f}% in {days_held} days "
                f"(annualised >{365*pnl_pct/max(days_held,1):.0f}%) and "
                f"{exh_score} exhaustion signals are firing: "
                f"{'; '.join(exh_triggers)}. Book {int(book_frac*100)}% "
                f"({book_qty} shares) to lock in the fast profit; let "
                f"{int(qty - book_qty)} shares run with a tighter stop."
            )
            if new_stop_partial:
                narrative.append(
                    f"🔒 Raise stop on the remaining {int(qty - book_qty)} shares "
                    f"to ₹{new_stop_partial:.2f} (give-back {give_back}pp)."
                )
            score_dict = dict(ta=ta_score, news=news_score, event=event_score,
                              regime=reg_score, ratchet=0, total=ta_score+news_score+event_score+reg_score)
            conf = _compute_confidence("BOOK_PARTIAL", score_dict, ta, news, events)
            expected = _expected_range(entry, price, ta.get("atr_pct", 3.0), days_ahead=5)
            return dict(action="BOOK_PARTIAL", urgency="normal",
                        pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                        days_held=days_held, new_stop=new_stop_partial,
                        add_qty=-book_qty,
                        confidence=conf, expected_range=expected,
                        reasons=[narrative[0]],
                        narrative=narrative, checks=checks,
                        score=score_dict)

    # ---------- TIER 4 : HOLD (with adaptive ratchet + optional ADD) ----------
    reasons = []
    add_qty = 0

    # v2: adaptive ratchet — give-back scaled by volatility, capped [3, 8]pp
    atr_pct_now = ta.get("atr_pct", 3.0)
    new_stop, give_back = _adaptive_ratchet(entry, pnl_pct, stop, atr_pct_now)
    ratchet_score = 0
    if new_stop is not None:
        floor_pct = (new_stop / entry - 1) * 100
        reasons.append(f"🔒 Raise stop-loss to ₹{new_stop:.2f} "
                       f"(was ₹{stop:.2f}) — protects {floor_pct:+.1f}% floor "
                       f"(give-back {give_back}pp)")
        narrative.append(
            f"🔒 ADAPTIVE RATCHET: with {pnl_pct:+.1f}% gain and "
            f"{atr_pct_now:.1f}% ATR, give-back sized to {give_back}pp "
            f"(range 3-8pp, scaled to volatility). New stop ₹{new_stop:.2f} "
            f"locks in +{floor_pct:.1f}% floor (₹{(new_stop-entry)*qty:+.0f} of "
            f"open profit). If price pulls back to that stop you keep the floor; "
            f"if it continues up, the stop trails again on next scan."
        )
        ratchet_score = 2

    # Add signal — profit + fresh signal + friendly regime + no negative news
    add_ok = (pnl_pct >= 5 and ta.get("signal_today")
              and regime in ("RISK-ON", "NEUTRAL")
              and ns >= -0.1)
    if add_ok:
        add_qty = max(1, int(qty * 0.5))
        reasons.append(f"➕ Fresh signal on a winner (+{pnl_pct:.1f}%) — "
                       f"consider adding {add_qty} shares (~50% of {int(qty)})")
        narrative.append(
            f"➕ SCALE-IN OPPORTUNITY: position is up {pnl_pct:+.1f}% AND the "
            f"scanner's PASS_combined rule is firing on today's bar AND market "
            f"regime is {regime}. Consider adding ~50% ({add_qty} shares) of "
            f"your original size. This is scale-in, not averaging down — "
            f"never fires on losing positions."
        )

    # Positive news support (informational, positive tilt)
    if ns >= 0.3 and nn >= 2:
        top = (news.get("top_headline") or "")[:120]
        reasons.append(f"📰 Positive news support (score {ns:+.2f}, {nn} articles)")
        narrative.append(
            f"📰 POSITIVE NEWS BACKS THE THESIS: {nn} articles with net "
            f"sentiment {ns:+.2f}. Reinforces the HOLD."
        )
        if top: narrative.append(f'Top: "{top}"')

    # 1 breakdown while in profit — WATCH
    if len(breakdowns) == 1 and pnl_pct >= 0:
        bd = breakdowns[0]
        reasons.append(f"⚠️ Watch: {bd['name']} — {bd['note']}")
        narrative.append(
            f"⚠️ ONE BROKEN TA CHECK ({bd['name']}). Not enough for exit on "
            f"its own since you're still in profit, but if a second check "
            f"joins it, action will escalate to EXIT next run."
        )

    # Default reasoning when everything is clean
    if not reasons:
        rsi = ta.get("rsi14", np.nan)
        p200 = ta.get("pct_vs_sma200", np.nan)
        rsi_txt = f"RSI {rsi:.0f}" if np.isfinite(rsi) else "TA neutral"
        p200_txt = f"{p200:+.1f}% vs 200-DMA" if np.isfinite(p200) else ""
        reasons.append(f"📈 Trend intact ({rsi_txt}, {p200_txt}, {pnl_pct:+.1f}% P&L) "
                       f"— continue holding")
        narrative.append(
            f"📈 ALL CLEAR — no breakdown signals, no material negative news, "
            f"no imminent events. Continue holding. Current: {pnl_pct:+.1f}% "
            f"P&L over {days_held} days."
        )

    total_score = ta_score + news_score + event_score + reg_score + ratchet_score
    score_dict = dict(ta=ta_score, news=news_score, event=event_score,
                      regime=reg_score, ratchet=ratchet_score, total=total_score)
    conf_hold = _compute_confidence("HOLD", score_dict, ta, news, events)
    expected = _expected_range(entry, price, ta.get("atr_pct", 3.0), days_ahead=5)

    return dict(action="HOLD", urgency="normal", pnl_pct=pnl_pct, pnl_abs=pnl_abs,
                days_held=days_held, new_stop=new_stop, add_qty=add_qty,
                confidence=conf_hold, expected_range=expected,
                reasons=reasons,
                narrative=narrative, checks=checks,
                score=score_dict)


# ======================================================================================
#  ANALYSIS DRIVER (per position)
# ======================================================================================
def analyze_position(position: pd.Series, bench_close: pd.Series,
                      regime: str, use_news: bool, use_events: bool,
                      sector_map: dict) -> dict:
    """Full analysis pipeline for one position."""
    ticker_bare = str(position["ticker"]).upper()
    ty = _to_yahoo(ticker_bare)

    # Auto-fill sector if blank (from NSE map)
    user_sector = str(position.get("sector") or "").strip()
    if user_sector:
        sector = user_sector
        sector_source = "user"
    else:
        sector = sector_map.get(ticker_bare, "-") or "-"
        sector_source = "auto (NSE map)" if sector != "-" else "unknown"

    raw = _fetch_stock(ty)
    result = {
        "ticker":    ticker_bare,
        "yahoo":     ty,
        "buy_date":  position["buy_date"],
        "buy_price": position["buy_price"],
        "quantity":  position["quantity"],
        "stop_loss": position.get("stop_loss"),          # may be NaN — derived below
        "target":    position.get("target"),
        "sector":    sector,
        "sector_source": sector_source,
        "notes":     position.get("notes", ""),
    }
    if raw.empty or len(raw) < 220:
        result.update({"action": "NO_DATA", "urgency": "normal",
                       "reasons": [f"insufficient data ({len(raw)} bars) — "
                                    f"ticker may be delisted or Yahoo-unavailable"],
                       "current_price": np.nan, "pnl_pct": np.nan, "pnl_abs": np.nan,
                       "new_stop": None, "add_qty": 0, "days_held": None,
                       "ta": {}, "news": {}, "events": {},
                       "checks": [], "narrative": [],
                       "stop_source": "n/a"})
        return result

    # Compute indicators + signal (uses SAME engine as scanner).
    # Historical data uses auto_adjust=True (necessary for indicator math).
    df_ind = engine.compute_indicators(raw)
    df_ind = engine.generate_signals(df_ind, "PASS_combined",
                                      {"regime": 8.0, "atr": 3.5, "roc": 3.0,
                                       "volr": 1.2, "rsi_os": 30.0},
                                      bench_close=bench_close,
                                      require_confirmation=True,
                                      block_risk_off=False)
    ta = _ta_snapshot(df_ind)

    # LIVE PRICE — separate fetch that returns UNADJUSTED price (matches
    # your broker screen). If successful, replace the adjusted close in `ta`
    # so downstream P&L / stop-comparison math uses the correct number.
    live = _fetch_live_price(ty)
    if live.get("price") is not None:
        ta["close"] = live["price"]
    result["price_asof"]  = live.get("as_of")
    result["price_source"] = live.get("source", "n/a")

    # --- AUTO-DERIVE stop_loss if user left it blank ---
    user_stop = position.get("stop_loss")
    if pd.isna(user_stop) or user_stop in (None, 0):
        derived_stop, stop_method = _derive_stop_loss(float(position["buy_price"]), ta)
        result["stop_loss"] = derived_stop
        result["stop_source"] = f"auto: {stop_method}"
        # Rewrite the position series so decide() sees the derived stop
        position = position.copy()
        position["stop_loss"] = derived_stop
    else:
        result["stop_source"] = "user"

    # News
    news = {"score": 0.0, "n_articles": 0, "top_headline": None,
            "matched_terms": [], "all_headlines": []}
    if use_news and HAVE_NEWS:
        try:
            news = _news_score(ty)
        except Exception:
            pass

    # Events
    events = {"blocked": False, "type": None, "days_until": None,
              "subject": None, "all_upcoming": []}
    if use_events and HAVE_EVENTS:
        try:
            events = _event_risk(ticker_bare, next_sessions=5)
        except Exception:
            pass

    decision = decide(position, ta, news, events, regime)
    result.update(decision)
    result["current_price"] = ta.get("close", np.nan)
    result["ta"] = ta
    result["news"] = news
    result["events"] = events

    # ---- TARGET PROJECTION (Aug-2026) ----
    # Compute "when will it hit +15%" + realistic ceiling + hit probability
    # These are advisory — they help you decide whether to book at 15% or hold further.
    entry_v = float(position["buy_price"])
    current_v = float(ta.get("close", entry_v))
    # Use scanner's default 15% target if the position has no target set
    target_v = position.get("target")
    if not pd.notna(target_v) or target_v <= 0:
        target_v = entry_v * 1.15
    target_pct = (target_v / entry_v - 1) * 100
    result["target_projection"] = {
        "target_price": round(float(target_v), 2),
        "target_pct":   round(target_pct, 2),
        "timing":       _project_days_to_target(entry_v, current_v, float(target_v),
                                                  ta, df_ind),
        "ceiling":      _project_price_ceiling(entry_v, current_v, ta, df_ind,
                                                 days_ahead=30),
    }
    # Hit probability uses the historical rate we just computed inside timing
    hist_stats = result["target_projection"]["timing"].get("hist_stats") or {}
    result["target_projection"]["hit_probability"] = _target_hit_probability(
        pnl_pct=decision.get("pnl_pct", 0),
        target_pct=target_pct,
        ta=ta,
        hist_hit_rate=hist_stats.get("hit_rate"),
        days_held=decision.get("days_held", 0),
        max_hold=30,
    )
    return result


# ======================================================================================
#  RENDER
# ======================================================================================
ACTION_STYLE = {
    "EXIT":         ("🔴", "#dc2626"),
    "REDUCE":       ("🟠", "#f97316"),
    "BOOK_PARTIAL": ("🎯", "#8b5cf6"),
    "HOLD":         ("🟢", "#16a34a"),
    "NO_DATA":      ("⚪", "#64748b"),
}


def _style_action(a: str) -> str:
    emo, _ = ACTION_STYLE.get(a, ("•", "#374151"))
    return f"{emo} {a}"


def main():
    """Standalone entry-point — sets page config, then renders body()."""
    st.set_page_config(page_title="Position Monitor", layout="wide")
    body()


def body():
    """All render logic, no set_page_config (safe to call inside a larger app).
    v3 (Aug-2026) — redesigned UI: hero + KPI dashboard + filters + tabbed drill-down.
    Zero changes to decide()/analyze_position()/projection helpers.
    """
    _V_ICON = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "INFO": "ℹ️"}

    # ================================================================
    # SIDEBAR
    # ================================================================
    with st.sidebar:
        st.markdown("## 📊 Position Monitor")
        st.caption("Daily hold / exit / reduce / add decisions")

        st.divider()
        st.markdown("**⚙️ Data sources**")
        use_news = st.checkbox(
            "📰 News sentiment", value=HAVE_NEWS, disabled=not HAVE_NEWS,
            help="yfinance + Google News. Adds Tier-1 severe / Tier-3 moderate negative-news exits.")
        use_events = st.checkbox(
            "📅 NSE upcoming events", value=HAVE_EVENTS, disabled=not HAVE_EVENTS,
            help="Force-exit within 2 sessions of results/AGM/split/dividend.")

        st.divider()
        st.markdown("**📁 Positions file**")
        with st.expander("File path", expanded=False):
            st.code(POSITIONS_CSV, language="text")
        st.caption("Edit → save → click Refresh below.")

        if st.button("🔄 Refresh (re-fetch prices & news)",
                     type="primary", use_container_width=True):
            _fetch_stock.clear()
            _fetch_live_price.clear()
            _fetch_bench.clear()
            st.rerun()

        st.divider()
        with st.expander("📖 Ratchet ladder reference"):
            for peak, floor in RATCHET_LADDER:
                st.markdown(f"- **+{peak:.0f}%** gain → stop floor +{floor:.0f}%")
            st.caption("(v2 adaptive: actual give-back scales to ATR volatility)")

    # ================================================================
    # LOAD POSITIONS
    # ================================================================
    positions, errors = load_positions(POSITIONS_CSV)
    st.title("📊 Position Monitor")

    if positions.empty:
        for e in errors: st.warning(e)
        st.info("No open positions. Edit **positions.csv** and click Refresh.")
        with st.expander("Show positions.csv template"):
            try:
                with open(POSITIONS_CSV, "r", encoding="utf-8") as f:
                    st.code(f.read(), language="csv")
            except Exception as ex:
                st.error(f"Can't read template: {ex}")
        return

    for e in errors:
        if e.startswith("ℹ️"):
            st.caption(e)
        else:
            st.warning(e)

    # ================================================================
    # ANALYZE
    # ================================================================
    sector_map = {}
    if HAVE_UNIVERSE:
        try: sector_map = _ul_load().get("sector_map", {})
        except Exception: sector_map = {}

    with st.spinner("📡 Fetching benchmark index..."):
        bench_name, bench_df = _fetch_bench()
    regime = _regime_from_bench(bench_df)
    bench_close = bench_df["Close"] if not bench_df.empty else None

    results = []
    prog_container = st.container()
    with prog_container:
        prog = st.progress(0.0); status = st.empty()
        for k, (_, pos) in enumerate(positions.iterrows(), 1):
            status.markdown(f"🔎 Analyzing **{pos['ticker']}** ({k}/{len(positions)})…")
            r = analyze_position(pos, bench_close, regime, use_news, use_events, sector_map)
            results.append(r)
            prog.progress(k / len(positions))
            time.sleep(0.05)
        status.empty(); prog.empty()

    # ================================================================
    # HERO META RIBBON
    # ================================================================
    regime_emoji = {"RISK-ON": "🟢", "NEUTRAL": "🟡", "RISK-OFF": "🔴", "UNKNOWN": "⚪"}
    reg_ico = regime_emoji.get(regime, "⚪")

    asof_stamps = [r.get("price_asof") for r in results if r.get("price_asof")]
    latest = max((a for a in asof_stamps if a is not None),
                 default=None, key=lambda x: pd.Timestamp(str(x)))
    latest_str = (latest.strftime("%d %b %Y, %H:%M") if hasattr(latest, "strftime")
                  else "unknown")

    live_srcs = [r.get("price_source", "-") for r in results if r.get("price_source")]
    n_live  = sum(1 for s in live_srcs if s.startswith("live"))
    n_intra = sum(1 for s in live_srcs if s.startswith("1-min"))
    n_eod   = sum(1 for s in live_srcs if s.startswith("daily"))

    ribbon = st.container()
    with ribbon:
        rc1, rc2, rc3 = st.columns([2, 2, 3])
        rc1.markdown(f"### 📦 **{len(results)}** positions")
        rc2.markdown(f"### {reg_ico} Regime: **{regime}**")
        rc3.markdown(f"### ⏱️ Prices as of **{latest_str}**")
        rc3.caption(f"Freshness → live: {n_live} · intraday: {n_intra} · EoD: {n_eod}")

    st.divider()

    # ================================================================
    # KPI DASHBOARD
    # ================================================================
    total_pnl = sum(r.get("pnl_abs", 0) or 0 for r in results
                    if pd.notna(r.get("pnl_abs", np.nan)))
    total_cap = sum(r["buy_price"] * r["quantity"] for r in results)
    total_now = sum((r.get("current_price", r["buy_price"]) or r["buy_price"])
                    * r["quantity"] for r in results)
    port_pct  = 100 * total_pnl / total_cap if total_cap > 0 else 0

    ok_results = [r for r in results
                  if r.get("current_price") and pd.notna(r.get("pnl_pct", np.nan))]
    best = max(ok_results, key=lambda r: r.get("pnl_pct", 0), default=None)
    worst = min(ok_results, key=lambda r: r.get("pnl_pct", 0), default=None)

    st.markdown("### 💼 Portfolio Snapshot")
    kpi = st.columns(5)
    kpi[0].metric("💰 Portfolio P&L", f"₹{total_pnl:+,.0f}",
                  f"{port_pct:+.2f}%",
                  delta_color=("normal" if port_pct != 0 else "off"))
    kpi[1].metric("💵 Invested", f"₹{total_cap:,.0f}")
    kpi[2].metric("📊 Current value", f"₹{total_now:,.0f}",
                  f"{100*(total_now-total_cap)/total_cap:+.1f}%" if total_cap else "-")
    if best:
        kpi[3].metric("🚀 Best", best["ticker"],
                      f"{best.get('pnl_pct', 0):+.1f}%")
    else:
        kpi[3].metric("🚀 Best", "—")
    if worst:
        kpi[4].metric("🔻 Worst", worst["ticker"],
                      f"{worst.get('pnl_pct', 0):+.1f}%",
                      delta_color="inverse")
    else:
        kpi[4].metric("🔻 Worst", "—")

    # ---- Action distribution ----
    n_urgent   = sum(1 for r in results if r.get("urgency") == "URGENT")
    n_exit_all = sum(1 for r in results if r["action"] == "EXIT")
    n_exit     = n_exit_all - n_urgent
    n_reduce   = sum(1 for r in results if r["action"] == "REDUCE")
    n_book     = sum(1 for r in results if r["action"] == "BOOK_PARTIAL")
    n_hold     = sum(1 for r in results if r["action"] == "HOLD")
    n_hold_add = sum(1 for r in results if r["action"] == "HOLD" and r.get("add_qty", 0) > 0)

    st.markdown("### 🎯 Recommended Actions")
    ac = st.columns(6)
    def _acard(col, ico, count, label):
        col.metric(f"{ico} {label}", count)
    _acard(ac[0], "🚨", n_urgent, "URGENT")
    _acard(ac[1], "🔴", n_exit,   "Exit")
    _acard(ac[2], "🟠", n_reduce, "Reduce")
    _acard(ac[3], "🎯", n_book,   "Book partial")
    _acard(ac[4], "🟢", n_hold,   "Hold")
    _acard(ac[5], "➕", n_hold_add, "Add-signal")

    st.divider()

    # ================================================================
    # INTERACTIVE FILTER + MAIN TABLE
    # ================================================================
    st.markdown("### 📋 Action list  ·  interactive filter + sort")

    fc1, fc2, fc3 = st.columns([3, 2, 3])
    with fc1:
        action_filter = st.multiselect(
            "Show only actions",
            ["EXIT", "REDUCE", "BOOK_PARTIAL", "HOLD"],
            default=[],
            placeholder="all actions",
            label_visibility="collapsed",
        )
    with fc2:
        sort_key = st.selectbox("Sort by",
                                ["Urgency", "P&L %", "Confidence", "Days held",
                                 "Hit prob %", "Alphabetical"],
                                label_visibility="collapsed")
    with fc3:
        search = st.text_input("🔍 Search stock", placeholder="filter by ticker (e.g. IRFC)",
                                label_visibility="collapsed")

    def _days_to_tgt(r):
        p = r.get("target_projection") or {}
        t = p.get("timing") or {}
        return t.get("days_base")
    def _ceiling_of(r):
        p = r.get("target_projection") or {}
        c = p.get("ceiling") or {}
        return c.get("statistical_max")
    def _hit_prob(r):
        p = r.get("target_projection") or {}
        return p.get("hit_probability", 0) or 0

    tbl_rows = []
    for r in results:
        act_ico = ACTION_STYLE.get(r["action"], ("•", "#374151"))[0]
        pnl_pct = r.get("pnl_pct", 0) or 0
        tbl_rows.append({
            "Stock":       r["ticker"],
            "Sector":      r.get("sector", "-") or "-",
            "Action":      f"{act_ico} {r['action']}",
            "_Action":     r["action"],   # for filter
            "Urgency":     r.get("urgency", "normal"),
            "Conf%":       int(r.get("confidence", 0) or 0),
            "Days":        r.get("days_held", 0) or 0,
            "Buy ₹":       float(r["buy_price"]),
            "Now ₹":       float(r.get("current_price") or r["buy_price"]),
            "P&L %":       pnl_pct,
            "P&L ₹":       r.get("pnl_abs", 0) or 0,
            "Days→+15%":   _days_to_tgt(r),
            "Hit%":        _hit_prob(r),
            "Ceiling ₹":   _ceiling_of(r),
            "Stop ₹":      float(r["stop_loss"]),
            "New stop ₹":  r.get("new_stop"),
            "Reason":      (r["reasons"][0] if r.get("reasons") else "")[:140],
        })
    tbl_df = pd.DataFrame(tbl_rows)

    # Apply filters
    if action_filter:
        tbl_df = tbl_df[tbl_df["_Action"].isin(action_filter)]
    if search:
        tbl_df = tbl_df[tbl_df["Stock"].str.contains(search.upper(), na=False)]

    action_order = {"EXIT": 0, "REDUCE": 1, "BOOK_PARTIAL": 2, "HOLD": 3, "NO_DATA": 4}
    urgency_order = {"URGENT": 0, "normal": 1}
    if sort_key == "Urgency":
        tbl_df["_a"] = tbl_df["_Action"].map(action_order).fillna(9)
        tbl_df["_u"] = tbl_df["Urgency"].map(urgency_order).fillna(9)
        tbl_df = tbl_df.sort_values(["_u", "_a", "Stock"]).drop(columns=["_a", "_u"])
    elif sort_key == "P&L %":
        tbl_df = tbl_df.sort_values("P&L %", ascending=False)
    elif sort_key == "Confidence":
        tbl_df = tbl_df.sort_values("Conf%", ascending=False)
    elif sort_key == "Days held":
        tbl_df = tbl_df.sort_values("Days", ascending=False)
    elif sort_key == "Hit prob %":
        tbl_df = tbl_df.sort_values("Hit%", ascending=False)
    elif sort_key == "Alphabetical":
        tbl_df = tbl_df.sort_values("Stock")
    tbl_df = tbl_df.reset_index(drop=True).drop(columns=["_Action"])

    if tbl_df.empty:
        st.info("No positions match your filter.")
    else:
        st.dataframe(
            tbl_df, use_container_width=True, hide_index=True,
            height=min(60 + 35*len(tbl_df), 550),
            column_config={
                "Stock": st.column_config.TextColumn("Stock", width="small"),
                "Sector": st.column_config.TextColumn("Sector", width="medium"),
                "Action": st.column_config.TextColumn("Action", width="small"),
                "Urgency": st.column_config.TextColumn("Urg", width="small"),
                "Conf%": st.column_config.ProgressColumn(
                    "Conf%", format="%d%%", min_value=0, max_value=100, width="small"),
                "Days": st.column_config.NumberColumn("Days", width="small"),
                "Buy ₹": st.column_config.NumberColumn("Buy ₹", format="₹%.2f", width="small"),
                "Now ₹": st.column_config.NumberColumn("Now ₹", format="₹%.2f", width="small"),
                "P&L %": st.column_config.NumberColumn("P&L %", format="%+.1f%%", width="small"),
                "P&L ₹": st.column_config.NumberColumn("P&L ₹", format="₹%+,.0f", width="small"),
                "Days→+15%": st.column_config.NumberColumn("D→+15%", format="~%dd", width="small"),
                "Hit%": st.column_config.ProgressColumn(
                    "Hit%", format="%d%%", min_value=0, max_value=100, width="small"),
                "Ceiling ₹": st.column_config.NumberColumn("Ceiling", format="₹%.0f", width="small"),
                "Stop ₹": st.column_config.NumberColumn("Stop", format="₹%.2f", width="small"),
                "New stop ₹": st.column_config.NumberColumn("New stop", format="₹%.2f", width="small"),
                "Reason": st.column_config.TextColumn("Reason (short)", width="large"),
            },
        )

        st.download_button("⬇️ Download action list",
                            tbl_df.to_csv(index=False).encode(),
                            file_name=f"monitor_actions_{dt.date.today()}.csv",
                            mime="text/csv")

    st.divider()

    # ================================================================
    # PER-STOCK DEEP-DIVE — tabbed cards
    # ================================================================
    st.markdown("### 🔎 Per-stock deep-dive")
    st.caption("Click any position to open a tabbed detail card: "
               "Overview · Target & Ceiling · Technical · News & Events · Scenarios.")

    for r in results:
        _render_stock_card(r, _V_ICON)


def _render_stock_card(r, _V_ICON):
    """Full per-stock analysis inside a single expander, organised in tabs."""
    emo, _ = ACTION_STYLE.get(r["action"], ("•", "#374151"))
    pnl = r.get("pnl_pct", 0) or 0
    conf = r.get("confidence")
    conf_ico = ("🟢" if (conf and conf >= 75) else
                "🟡" if (conf and conf >= 55) else "🔴")

    header = (f"{emo} **{r['ticker']}** · {r.get('sector','-') or '-'} · "
              f"**{r['action']}** ({conf_ico} {conf or 0}% conf) · "
              f"P&L {pnl:+.1f}% · {r.get('days_held','-')}d held")

    with st.expander(header):
        # Provenance strip
        src_bits = []
        if r.get("price_source"):
            asof = r.get("price_asof")
            asof_str = (asof.strftime("%Y-%m-%d %H:%M") if hasattr(asof, "strftime")
                        else str(asof) if asof else "n/a")
            src_bits.append(f"💰 {r['price_source']} ({asof_str})")
        if r.get("stop_source"):   src_bits.append(f"🛑 {r['stop_source']}")
        if r.get("sector_source"): src_bits.append(f"🏭 {r['sector_source']}")
        if src_bits:
            st.caption("Data → " + "  ·  ".join(src_bits))

        tab_ov, tab_tgt, tab_tech, tab_ne, tab_scen = st.tabs([
            "📊 Overview",
            "🎯 Target & Ceiling",
            "📈 Technical",
            "📰 News & Events",
            "📐 Scenarios",
        ])

        # ---------- TAB: OVERVIEW ----------
        with tab_ov:
            cA, cB, cC, cD = st.columns(4)
            cA.metric("Buy", f"₹{r['buy_price']:.2f}",
                      f"{r.get('days_held','-')}d ago")
            cur = r.get("current_price") or r["buy_price"]
            pnl_abs = r.get("pnl_abs", 0) or 0
            cB.metric("Now", f"₹{cur:.2f}",
                      f"{pnl:+.1f}%  (₹{pnl_abs:+,.0f})")
            new_stop = r.get("new_stop")
            cC.metric("Stop", f"₹{r['stop_loss']:.2f}",
                      f"↗ ₹{new_stop:.2f}" if new_stop else "unchanged")
            tgt = r.get("target")
            cD.metric("Target", f"₹{tgt:.2f}" if (tgt and pd.notna(tgt)) else "—")

            st.markdown("")   # small spacer

            # Confidence progress
            if conf is not None:
                st.markdown(f"**Recommendation confidence — {conf_ico} {conf}%**")
                st.progress(min(1.0, max(0.0, conf/100.0)))
                conf_note = ("Multiple signals aligned strongly — good conviction."
                             if conf >= 75 else
                             "Signals mixed or moderate — advisory, not high-conviction."
                             if conf >= 55 else
                             "Weak / borderline setup — use your own judgement or wait.")
                st.caption(conf_note)

            # Progress-to-target bar
            proj = r.get("target_projection") or {}
            tgt_price = proj.get("target_price")
            if tgt_price and cur and tgt_price > r["buy_price"]:
                progress = min(1.0, max(0.0,
                    (cur - r["buy_price"]) / (tgt_price - r["buy_price"])))
                st.markdown(f"**Progress toward target** "
                            f"(₹{r['buy_price']:.0f} → ₹{tgt_price:.2f}): "
                            f"**{progress*100:.0f}%**")
                st.progress(progress)

            # Reasoning
            st.markdown("**💡 Recommendation reasoning**")
            for reason in r.get("reasons", []):
                st.markdown(f"- {reason}")

            narrative = r.get("narrative") or []
            if narrative:
                with st.expander("📝 Full multi-line narrative"):
                    for line in narrative:
                        st.markdown(f"> {line}")

            if r.get("notes"):
                st.info(f"📝 Your notes: {r['notes']}")

        # ---------- TAB: TARGET & CEILING ----------
        with tab_tgt:
            proj = r.get("target_projection") or {}
            if not proj:
                st.info("Target projection not available.")
            else:
                tgt_price = proj["target_price"]
                tgt_pct   = proj["target_pct"]
                timing    = proj.get("timing") or {}
                ceiling   = proj.get("ceiling") or {}
                hit_prob  = proj.get("hit_probability", 0) or 0
                cur = r.get("current_price") or r["buy_price"]

                st.markdown(f"### 🎯 Target: ₹{tgt_price:.2f} (+{tgt_pct:.1f}% from entry)")

                colT1, colT2, colT3 = st.columns(3)
                if timing.get("days_base") == 0:
                    colT1.metric("Days to target", "already hit ✓",
                                  f"currently {pnl:+.1f}%")
                elif timing.get("days_base") is not None:
                    colT1.metric("Days to target",
                                  f"~{timing['days_base']}d",
                                  f"range {timing['days_low']}–{timing['days_high']}d")
                else:
                    colT1.metric("Days to target", "unknown")
                colT2.metric("Hit probability (30d)", f"{hit_prob}%",
                              timing.get("momentum_state", ""))
                vel = timing.get("current_velocity_pct_per_day")
                colT3.metric("Current velocity",
                              f"{vel:+.2f}%/day" if vel is not None else "—",
                              timing.get("method", ""))

                # Progress bar for hit probability
                st.progress(min(1.0, max(0.0, hit_prob/100.0)))

                # Historical base rate
                hs = timing.get("hist_stats") or {}
                if hs.get("occurrences"):
                    st.caption(f"📊 **Historical base rate:** {hs['occurrences']} similar "
                                f"moves in last ~2 yr · hit rate **{hs['hit_rate']}%** · "
                                f"typical **{hs['med_days']}d** (fastest {hs['min_days']}d).")
                else:
                    st.caption("📊 No comparable historical moves — projection uses "
                                "current-momentum extrapolation only.")

                st.markdown("**📈 Realistic ceiling analysis**")
                ceil_rows = []
                if ceiling.get("immediate_resistance"):
                    ceil_rows.append({
                        "Ceiling": "🔵 Immediate resistance (20d high)",
                        "Price":  ceiling["immediate_resistance"],
                        "From now %": 100*(ceiling["immediate_resistance"]/(cur or 1) - 1),
                        "From entry %": ceiling["pnl_from_entry_at_ceiling"].get("immediate", 0),
                    })
                if ceiling.get("medium_ceiling"):
                    ceil_rows.append({
                        "Ceiling": "🟡 52-week high (medium)",
                        "Price":  ceiling["medium_ceiling"],
                        "From now %": 100*(ceiling["medium_ceiling"]/(cur or 1) - 1),
                        "From entry %": ceiling["pnl_from_entry_at_ceiling"].get("52w_high", 0),
                    })
                if ceiling.get("statistical_max"):
                    ceil_rows.append({
                        "Ceiling": "🟢 Statistical max (30d, 1.5σ ATR)",
                        "Price":  ceiling["statistical_max"],
                        "From now %": 100*(ceiling["statistical_max"]/(cur or 1) - 1),
                        "From entry %": ceiling["pnl_from_entry_at_ceiling"].get("stat_max_30d", 0),
                    })
                if ceil_rows:
                    st.dataframe(pd.DataFrame(ceil_rows), hide_index=True,
                                  use_container_width=True,
                                  column_config={
                                      "Price":       st.column_config.NumberColumn("Price ₹",  format="₹%.2f"),
                                      "From now %":  st.column_config.NumberColumn("From now",  format="%+.1f%%"),
                                      "From entry %": st.column_config.NumberColumn("From entry", format="%+.1f%%"),
                                  })
                for note in ceiling.get("notes", []):
                    st.caption(f"ℹ️ {note}")

                # Interpretation
                if timing.get("days_base") == 0 and ceiling.get("statistical_max"):
                    upside_beyond = ((ceiling["statistical_max"] / cur - 1) * 100) if cur else 0
                    if upside_beyond > 8:
                        st.success(f"💡 **Target already hit** — but ceiling ₹{ceiling['statistical_max']:.2f} "
                                    f"is {upside_beyond:+.1f}% more upside. Adaptive ratchet trails.")
                    else:
                        st.warning(f"💡 **Target already hit** — limited upside ({upside_beyond:+.1f}%). "
                                    f"Consider booking at target or on weakness.")
                elif timing.get("days_base") and hit_prob >= 60:
                    st.success(f"💡 **High-probability setup ({hit_prob}%)** — expect target hit "
                                f"in ~{timing['days_base']}d. Hold with adaptive ratchet stop.")
                elif timing.get("days_base") and hit_prob < 40:
                    st.warning(f"⚠️ **Low hit probability ({hit_prob}%)** — target may not be "
                                f"reached in 30d. Consider tighter target / early exit.")

        # ---------- TAB: TECHNICAL ----------
        with tab_tech:
            score = r.get("score") or {}
            if score:
                total = score.get("total", 0)
                st.markdown(f"### 🧮 Composite score: **{total:+d}**")
                sc = st.columns(5)
                sc[0].metric("TA",      f"{score.get('ta',0):+d}")
                sc[1].metric("News",    f"{score.get('news',0):+d}")
                sc[2].metric("Events",  f"{score.get('event',0):+d}")
                sc[3].metric("Regime",  f"{score.get('regime',0):+d}")
                sc[4].metric("Ratchet", f"{score.get('ratchet',0):+d}")

            checks = r.get("checks") or []
            if checks:
                st.markdown("**📋 Every check that ran**")
                check_rows = [{
                    "": _V_ICON.get(c["verdict"], "•"),
                    "Category": c["category"].upper(),
                    "Check": c["name"],
                    "Value": str(c["value"]),
                    "Verdict": c["verdict"],
                    "Note": c["note"],
                } for c in checks]
                st.dataframe(pd.DataFrame(check_rows), hide_index=True,
                              use_container_width=True,
                              height=min(50 + 32*len(check_rows), 400))

            if r.get("new_stop"):
                st.markdown("**🔒 Ratchet ladder — highlighted rung**")
                lad_rows = []
                for peak, floor in RATCHET_LADDER:
                    fires = pnl >= peak
                    lad_rows.append({
                        "":       "🔥" if fires else "",
                        "Gain ≥": peak,
                        "Stop floor": floor,
                        "Absolute ₹": r["buy_price"] * (1 + floor/100),
                    })
                st.dataframe(pd.DataFrame(lad_rows), hide_index=True,
                              use_container_width=True,
                              column_config={
                                  "Gain ≥":     st.column_config.NumberColumn("Gain ≥",     format="+%d%%"),
                                  "Stop floor": st.column_config.NumberColumn("Stop floor", format="+%d%% of entry"),
                                  "Absolute ₹": st.column_config.NumberColumn("Absolute ₹", format="₹%.2f"),
                              })
                st.info(f"💡 Update `stop_loss` in positions.csv to **₹{r['new_stop']:.2f}** "
                        f"to lock in the current rung.")

        # ---------- TAB: NEWS & EVENTS ----------
        with tab_ne:
            news = r.get("news") or {}
            all_h = news.get("all_headlines") or []
            n_art = news.get("n_articles", 0)

            st.markdown("#### 📰 News sentiment (last 5 sessions)")
            if all_h:
                score_val = news.get("score", 0)
                score_ico = "🟢" if score_val > 0.2 else "🔴" if score_val < -0.2 else "🟡"
                nc1, nc2 = st.columns(2)
                nc1.metric(f"{score_ico} Sentiment", f"{score_val:+.2f}",
                            "positive" if score_val > 0.2 else
                            "negative" if score_val < -0.2 else "neutral")
                nc2.metric("Articles", n_art)
                st.markdown("**Headlines analysed:**")
                head_rows = []
                for h in all_h[:15]:
                    d = h.get("date")
                    d_str = d.strftime("%Y-%m-%d") if d and hasattr(d, "strftime") else "-"
                    head_rows.append({
                        "Date":   d_str,
                        "Score":  h.get("score", 0),
                        "Source": h.get("source", "-"),
                        "Headline": (h.get("title") or "")[:200],
                    })
                st.dataframe(pd.DataFrame(head_rows), hide_index=True,
                              use_container_width=True,
                              column_config={
                                  "Score": st.column_config.NumberColumn("Score", format="%+.2f"),
                              })
            elif n_art > 0:
                st.markdown(f"Score **{news.get('score', 0):+.2f}** ({n_art} articles)")
                if news.get("top_headline"):
                    st.caption(f"Top: \"{news['top_headline']}\"")
            else:
                st.info("📰 No news articles found in the last 5 sessions.")

            st.divider()

            st.markdown("#### 📅 Upcoming corporate events")
            events = r.get("events") or {}
            all_ev = events.get("all_upcoming") or []
            if all_ev:
                ev_rows = [{
                    "Date": str(e.get("date", "-")),
                    "Type": e.get("type", "-"),
                    "Subject": (e.get("subject") or "")[:200],
                } for e in all_ev]
                st.dataframe(pd.DataFrame(ev_rows), hide_index=True,
                              use_container_width=True,
                              height=min(50 + 32*len(ev_rows), 300))
            elif events.get("type"):
                st.warning(f"**{events['type']}** in {events.get('days_until','?')}d "
                            f"— {(events.get('subject') or '')[:200]}")
            else:
                st.success("✅ No corporate events scheduled in the next 5 sessions.")

        # ---------- TAB: SCENARIOS ----------
        with tab_scen:
            price_now = r.get("current_price")
            buy = r.get("buy_price")
            stop = r.get("stop_loss")
            new_stop = r.get("new_stop") or stop
            qty = r.get("quantity", 0)
            expected = r.get("expected_range") or {}

            if not (price_now and buy and stop):
                st.info("Insufficient data to project scenarios.")
            else:
                st.markdown("**📐 What happens if… (each scenario\'s P&L math)**")
                stop_pct = (new_stop / buy - 1) * 100
                stop_pnl = (new_stop - buy) * qty
                move_to_stop = (new_stop / price_now - 1) * 100
                base_upside = expected.get("high")
                base_downside = expected.get("low")

                scen_rows = [{
                    "Scenario": f"🛑 Stop-loss hits (₹{new_stop:.2f})",
                    "Move from here": move_to_stop,
                    "P&L on trade": stop_pct,
                    "P&L ₹": stop_pnl,
                    "Note": "Capital protected at floor",
                }]
                if base_downside:
                    scen_rows.append({
                        "Scenario": "📉 Downside 1σ (5d, ATR)",
                        "Move from here": (base_downside/price_now - 1)*100,
                        "P&L on trade": (base_downside/buy - 1)*100,
                        "P&L ₹": (base_downside - buy)*qty,
                        "Note": f"~68% stays above ₹{base_downside:.2f}",
                    })
                if base_upside:
                    scen_rows.append({
                        "Scenario": "📈 Upside 1σ (5d, ATR)",
                        "Move from here": (base_upside/price_now - 1)*100,
                        "P&L on trade": (base_upside/buy - 1)*100,
                        "P&L ₹": (base_upside - buy)*qty,
                        "Note": f"~68% stays below ₹{base_upside:.2f}",
                    })
                tgt = r.get("target")
                if tgt and pd.notna(tgt) and tgt > price_now:
                    scen_rows.append({
                        "Scenario": f"🎯 Original target (₹{tgt:.2f})",
                        "Move from here": (tgt/price_now - 1)*100,
                        "P&L on trade": (tgt/buy - 1)*100,
                        "P&L ₹": (tgt - buy)*qty,
                        "Note": "Advisory only",
                    })
                proj = r.get("target_projection") or {}
                ceiling = proj.get("ceiling") or {}
                if ceiling.get("statistical_max"):
                    smax = ceiling["statistical_max"]
                    scen_rows.append({
                        "Scenario": f"🚀 Statistical ceiling (₹{smax:.2f})",
                        "Move from here": (smax/price_now - 1)*100,
                        "P&L on trade": (smax/buy - 1)*100,
                        "P&L ₹": (smax - buy)*qty,
                        "Note": "30d, 1.5σ ATR — realistic best-case",
                    })

                st.dataframe(pd.DataFrame(scen_rows), hide_index=True,
                              use_container_width=True,
                              column_config={
                                  "Move from here": st.column_config.NumberColumn("Move from here", format="%+.1f%%"),
                                  "P&L on trade":  st.column_config.NumberColumn("P&L on trade",  format="%+.1f%%"),
                                  "P&L ₹":         st.column_config.NumberColumn("P&L ₹",         format="₹%+,.0f"),
                              })
                st.caption("ATR-scaled random-walk projection (1σ over 5 sessions). "
                            "Real markets have fatter tails — treat as central expectation, "
                            "not a hard bound.")


if __name__ == "__main__":
    main()
