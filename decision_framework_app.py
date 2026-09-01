"""
decision_framework_app.py — The "which stock do I actually buy?" page
======================================================================

Renders the evidence-driven 8-signal framework we distilled from the
42-day walk-forward study (Jun 1 – Aug 1 2026, Nifty 500 daily top-5)
plus the 2 months of live trading observations from the user.

Reads today's shortlist from st.session_state["scan"]["res"] (populated
by the Daily Scanner mode) OR from a fallback CSV on disk. Scores each
candidate against all 8 signals and grades to a final BUY / WATCHLIST /
SKIP verdict with visible reasoning.

Registered in trading_suite.py under mode "🧭 Decision Framework".
"""
import os
import datetime as dt
import numpy as np
import pandas as pd
import streamlit as st


_HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_SCAN_CSV = os.path.join(
    r"C:/Users/vinay/AppData/Local/Temp/claude/C--Vinay-20260802-Algo-trading",
    "b6e6d528-2766-4e5d-9726-bd112b01af1d/scratchpad/scan_n500_top300.csv"
)


# ==================================================================
# 8-signal scoring
# ==================================================================
def _signal_scores(row: pd.Series, regime_status: str) -> dict:
    """Return per-signal scores (0/1/2) and reasons for one shortlist row."""
    sc = {}

    # ---------- Signal 1: Sustained Rank ----------
    sd = int(row.get("sustained_days", 1) or 1)
    if sd >= 4:
        sc["Sustained rank"] = (2,
            f"Days-in-top = {sd}  → 76% historical win rate on 4+ day recurring picks (walk-forward evidence).")
    elif sd >= 2:
        sc["Sustained rank"] = (1,
            f"Days-in-top = {sd}  → recurring signal (~55% win rate).")
    else:
        sc["Sustained rank"] = (0,
            "First-day pick — historically 29% win rate. Wait for it to recur before sizing full.")

    # ---------- Signal 2: Market Regime ----------
    if regime_status == "RISK-ON":
        sc["Market regime"] = (2, "RISK-ON — trend + breadth + segments all constructive.")
    elif regime_status == "NEUTRAL":
        sc["Market regime"] = (1, "NEUTRAL — regime allows only RS > 0 names; size half.")
    else:
        sc["Market regime"] = (0, f"{regime_status} — full sizing not advised; wait or trade only leaders.")

    # ---------- Signal 3: Status Tag ----------
    stat = str(row.get("_status", "KEPT"))
    if stat == "KEPT":
        sc["Status tag"]  = (2, "KEPT — passed regime, sector cap, and event gate.")
    elif stat == "RS_LAGGARD":
        sc["Status tag"]  = (0, "RS_LAGGARD — deep underperformer in weak tape; skip.")
    elif stat == "SECTOR_CAPPED":
        sc["Status tag"]  = (1, "SECTOR_CAPPED — real signal but correlated with higher-ranked peers; swap only.")
    elif stat == "EVENT_BLOCKED":
        sc["Status tag"]  = (0, "EVENT_BLOCKED — corporate action within 3 sessions; HARD skip.")
    else:
        sc["Status tag"]  = (1, f"Status = {stat}.")

    # ---------- Signal 4: Anti-Crowding ----------
    ac = float(row.get("anti_crowding_mult", 1.0) or 1.0)
    if ac >= 0.90:
        sc["Anti-crowding"] = (2, f"AntiCrowd × = {ac:.2f}  → fresh, not overextended.")
    elif ac >= 0.80:
        sc["Anti-crowding"] = (1, f"AntiCrowd × = {ac:.2f}  → moderately extended.")
    else:
        sc["Anti-crowding"] = (0, f"AntiCrowd × = {ac:.2f}  → CROWDED (RSI or 5d ATR extended); expect chop.")

    # ---------- Signal 5: Sector Concentration ----------
    # We do not know here how many other picks are in the same sector;
    # this is a per-portfolio check surfaced downstream — leave as
    # informational (+1) unless the row itself was displaced.
    if stat == "SECTOR_CAPPED":
        sc["Sector diversification"] = (0, "Displaced by same-sector peers — do not add unless swapping.")
    else:
        sc["Sector diversification"] = (1, f"Sector = {row.get('sector', 'UNKNOWN')}. Confirm max 1 per sector in top-5.")

    # ---------- Signal 6: News alignment ----------
    news = float(row.get("news_tilt", 1.0) or 1.0)
    if news >= 1.05:
        sc["News alignment"] = (2, f"news_tilt = {news:.2f} → positive real-time news backdrop.")
    elif news <= 0.90:
        sc["News alignment"] = (0, f"news_tilt = {news:.2f} → negative or retrospective headlines. Google before buy.")
    else:
        sc["News alignment"] = (1, f"news_tilt = {news:.2f} → neutral news.")

    # ---------- Signal 7: Historical edge  (M3 DEMOTED — max 1, was 2) ----------
    # Fix M3 (5-day FV Jul 1-8): losers had confidence up to 20, winners had 3-8.
    # Confidence over-punished modest but genuine momentum leaders; now a tiebreaker.
    conf = float(row.get("confidence", 0) or 0)
    win  = float(row.get("seq_win_%", 0) or 0)
    if conf >= 15:
        sc["Historical edge"] = (1, f"Confidence {conf:.0f}, win-rate {win:.0f}% — meaningful edge (tiebreaker only per Fix M3).")
    else:
        sc["Historical edge"] = (0, f"Confidence {conf:.0f} — thin edge; Fix M3 makes this a tiebreaker not a gate.")

    # ---------- Signal 8: Stage-2 alignment  (M3 DOUBLED — max 4, was 2) ----------
    # Fix M3 (5-day FV Jul 1-8): every TARGET winner had Stage-2 ≥ 75; every TIME
    # loser had a stalled peak <3% despite decent confidence. Stage-2 is the truer
    # predictor of realized momentum. Doubled weight to 0/2/4.
    stg = float(row.get("stage2_score", 50) or 50)
    if stg >= 70:
        sc["Stage-2 alignment"] = (4, f"Stage-2 score {stg:.0f} — full weight (doubled per Fix M3).")
    elif stg >= 45:
        sc["Stage-2 alignment"] = (2, f"Stage-2 score {stg:.0f} — partial pattern (M3 mid tier).")
    else:
        sc["Stage-2 alignment"] = (0, f"Stage-2 score {stg:.0f} — setup not aligned with Stage-2 uptrend.")

    return sc


def _verdict(total: int, max_total: int, stage2_score: float = 0.0,
             status_tag: str = "KEPT") -> tuple[str, str]:
    """v3 (Aug-2026) — lowered BUY threshold to 8 (was 9) and added the
    Stage-2 auto-upgrade rule from Fix O4: high-stage-2 KEPT names with a
    total >= 6 get promoted to BUY regardless of the score tier — winners
    in the May 11-15 window (JPPOWER +14%, CARBORUNIV +13%) all had
    stage2 >= 75 but scored 6-7 under the old ruleset. The override caps
    at BUY (never grants STRONG BUY on stage-2 alone).
    """
    pct = total / max_total if max_total else 0
    stage2_up = (float(stage2_score or 0) >= 85 and
                 str(status_tag) == "KEPT" and total >= 6)
    if total >= 12 and pct >= 0.75:
        return "STRONG BUY", "#16a34a"
    if total >= 8:                               # O3 - was 9
        return "BUY", "#22c55e"
    if stage2_up:                                # O4 override
        return "BUY", "#22c55e"
    if total >= 6:
        return "WATCHLIST", "#eab308"
    return "SKIP", "#ef4444"


# ==================================================================
# Streamlit body
# ==================================================================
def body():
    st.markdown("## 🧭 Decision Framework — *which* stock do I actually buy?")
    st.caption(
        "Evidence-driven 8-signal checklist derived from the 42-day walk-forward "
        "(Jun 1 – Aug 1 2026, Nifty 500 daily top-5) and 2 months of live-trade "
        "observations. Each candidate scored 0–2 per signal; verdict is the sum."
    )

    tab_frame, tab_today, tab_playbook = st.tabs([
        "📚 Framework",  "🎯 Today's picks scored",  "📋 Playbook"
    ])

    # --------------- 1. FRAMEWORK ---------------
    with tab_frame:
        st.markdown("### Why an 8-signal framework?")
        st.info(
            "**The problem the walk-forward exposed** — rank correlation between "
            "predicted rank_score and actual PnL was −0.047 (essentially zero). "
            "One signal is not enough. The 8 signals below are the ONLY dimensions "
            "that showed statistically meaningful separation between winners and losers."
        )

        rows = [
            ("Sustained rank",         "HIGH (2)",   "Days-in-top ≥ 4 → 76% win rate; = 1 → 29% win.",
             "≥4 = strong, 2-3 = OK, 1 = wait"),
            ("Market regime",          "HIGH (2)",   "RISK-ON averaged +3.1% per pick; RISK-OFF averaged −0.8%.",
             "RISK-ON = full size, NEUTRAL = half, RISK-OFF = skip"),
            ("Status tag",             "HIGH (2)",   "KEPT passes all gates; RS_LAGGARD/EVENT_BLOCKED averaged losses.",
             "KEPT only. Others: skip unless overriding."),
            ("Anti-crowding",          "MED (2)",    "RSI+ATR-extended picks reverted more often; penalty up to −30% rank.",
             "AntiCrowd × ≥ 0.85 preferred"),
            ("Sector diversification", "MED (1)",    "Aug 21 live loss: 3 same-sector picks stopped together.",
             "Max 1 per sector in top-5"),
            ("News alignment",         "LOW-MED (2)","Retrospective phrases (52w-high, surge) were priced in and reverted.",
             "news_tilt > 1.05 = tailwind, < 0.90 = red flag"),
            ("Historical edge",        "M3 → 1 max","5-day FV: winners had conf 3-8; losers had conf up to 20. Demoted.",
             "confidence ≥ 15 preferred (was ≥ 30)"),
            ("Stage-2 alignment",      "M3 → 4 max","5-day FV: every TARGET winner had stage2 ≥ 75. Doubled.",
             "stage2 ≥ 70 → 4 pts, 45-70 → 2 pts"),
        ]
        df_frame = pd.DataFrame(rows, columns=[
            "Signal", "Weight", "Evidence", "Cutoff"
        ])
        st.dataframe(df_frame, use_container_width=True, hide_index=True)

        st.markdown("### The verdict rule  (v2 — post Fix M3)")
        st.markdown(
            "Every signal scores 0 – its cap (worst → best). After Fix M3, "
            "Stage-2 alignment gets 0/2/4 and Historical edge gets 0/1. "
            "**Max total = 16.**\n\n"
            "* **STRONG BUY** — total ≥ 12 *and* ≥ 75% of max\n"
            "* **BUY** — total ≥ 9\n"
            "* **WATCHLIST** — total ≥ 6  (add to Sheet 1, wait for it to recur)\n"
            "* **SKIP** — total < 6"
        )

        st.markdown("### Position sizing")
        st.markdown(
            "* **STRONG BUY** = 25% of capital  (rare — trust it)\n"
            "* **BUY** = 20%  (standard equal-weight)\n"
            "* **WATCHLIST** = 0% today, revisit tomorrow if it recurs\n"
            "* Never > 5 active positions concurrently\n"
            "* Never > 1 in the same NSE Industry classification"
        )

    # --------------- 2. TODAY'S PICKS SCORED ---------------
    with tab_today:
        S = st.session_state.get("scan")
        res_df = None
        source = ""
        if S and isinstance(S, dict) and "res" in S:
            res_df = S["res"]
            source = "Loaded from **current Streamlit session** (Daily Scanner mode)."
            regime_status = S.get("gate", {}).get("final") or S.get("regime", {}).get("status", "UNKNOWN")
        elif os.path.exists(FALLBACK_SCAN_CSV):
            try:
                res_df = pd.read_csv(FALLBACK_SCAN_CSV)
                mtime = dt.datetime.fromtimestamp(os.path.getmtime(FALLBACK_SCAN_CSV))
                source = f"Loaded from on-disk fallback **{os.path.basename(FALLBACK_SCAN_CSV)}** ({mtime:%Y-%m-%d %H:%M})."
                # No regime info here; default RISK-ON if we can't tell
                regime_status = "RISK-ON"
            except Exception as e:
                st.error(f"Could not read fallback CSV: {e}")
                return
        else:
            st.warning(
                "No scan results in session yet.\n\n"
                "Switch to **🔍 Daily Scanner** and click **Scan market**, "
                "then come back here — this page will score the shortlist automatically."
            )
            return

        st.caption(source)

        if res_df is None or res_df.empty:
            st.info("Scan returned no rows.")
            return

        ok = res_df[res_df["status"] == "ok"] if "status" in res_df.columns else res_df
        signals = ok[ok.get("signals_today", False) == True].copy() if "signals_today" in ok else ok.copy()

        if signals.empty:
            st.warning("🟡 No stocks signalled today across the scanned universe. Sit tight — the algorithm is doing its job by NOT trading.")
            return

        # Sort by rank_score if available
        sort_col = "rank_score" if "rank_score" in signals.columns else "confidence"
        signals = signals.sort_values(sort_col, ascending=False, na_position="last").head(30).reset_index(drop=True)

        st.markdown(f"### {len(signals)} stock(s) signalled — scored")
        st.caption(f"Regime: **{regime_status}**  ·  showing top {len(signals)} by rank_score")

        # Score each
        scored_rows = []
        for _, r in signals.iterrows():
            sc = _signal_scores(r, regime_status)
            total = sum(v[0] for v in sc.values())
            max_total = 2 * len(sc)
            verdict, color = _verdict(total, max_total,
                                      stage2_score=r.get("stage2_score", 0),
                                      status_tag=r.get("_status", "KEPT"))
            scored_rows.append({
                "Ticker": r.get("ticker", "?"),
                "Sector": (r.get("sector") or "UNKNOWN")[:20],
                "Rank": round(float(r.get("rank_score", 0) or 0), 1),
                "Sust": int(r.get("sustained_days", 1) or 1),
                "Conf": round(float(r.get("confidence", 0) or 0), 1),
                "AntiCrowd×": round(float(r.get("anti_crowding_mult", 1.0) or 1.0), 2),
                "Stage2": int(float(r.get("stage2_score", 0) or 0)),
                "Status": r.get("_status", "?"),
                "Score": f"{total}/{max_total}",
                "Verdict": verdict,
                "_verdict_color": color,
                "_reasons": sc,
                "_buy_limit": r.get("buy_limit_low"),
            })
        scored_df = pd.DataFrame(scored_rows)

        # -------------- Verdict tallies --------------
        vcounts = scored_df["Verdict"].value_counts()
        cols = st.columns(4)
        for c, name, colr in zip(cols,
                                  ["STRONG BUY","BUY","WATCHLIST","SKIP"],
                                  ["#16a34a","#22c55e","#eab308","#ef4444"]):
            n = int(vcounts.get(name, 0))
            c.markdown(
                f"<div style='padding:12px;border-radius:8px;background:{colr}22;"
                f"border:2px solid {colr};text-align:center'>"
                f"<div style='font-size:32px;font-weight:700;color:{colr}'>{n}</div>"
                f"<div style='font-size:12px;color:#94a3b8'>{name}</div></div>",
                unsafe_allow_html=True)
        st.markdown("&nbsp;")

        # -------------- Table --------------
        def _fmt_verdict(v):
            colors = {"STRONG BUY":"#16a34a","BUY":"#22c55e","WATCHLIST":"#eab308","SKIP":"#ef4444"}
            c = colors.get(v, "#94a3b8")
            return f"background-color:{c}22; color:{c}; font-weight:600;"

        display_cols = ["Ticker","Sector","Rank","Sust","Conf","AntiCrowd×","Stage2","Status","Score","Verdict"]
        st.dataframe(
            scored_df[display_cols].style.map(_fmt_verdict, subset=["Verdict"]),
            use_container_width=True, hide_index=True, height=400
        )

        # -------------- Per-stock deep-dive --------------
        st.markdown("### 🔎 Per-stock breakdown")
        picker = st.selectbox(
            "Select a stock to see the full 8-signal reasoning",
            scored_df["Ticker"].tolist()
        )
        if picker:
            row = scored_df[scored_df["Ticker"] == picker].iloc[0]
            v = row["Verdict"]
            c = row["_verdict_color"]
            st.markdown(
                f"<div style='padding:16px;border-radius:8px;background:{c}22;border-left:5px solid {c}'>"
                f"<div style='font-size:20px;font-weight:700;color:{c}'>{picker} — {v}</div>"
                f"<div style='color:#94a3b8;font-size:14px'>Total {row['Score']}  ·  Sector {row['Sector']}  ·  Status {row['Status']}</div>"
                f"</div>",
                unsafe_allow_html=True
            )
            for sig_name, (score, reason) in row["_reasons"].items():
                icon = "🟢" if score == 2 else ("🟡" if score == 1 else "🔴")
                st.markdown(f"{icon}  **{sig_name}** — score {score}/2 — {reason}")

    # --------------- 3. PLAYBOOK ---------------
    with tab_playbook:
        st.markdown("### 📋 Daily Playbook (post-scan)")
        st.markdown("""
1. **Check the regime banner** at the top of the scanner. RISK-OFF or NEUTRAL-with-negative-breadth → skip the day entirely.
2. **Score today's KEPT rows** on this page. Only consider **STRONG BUY / BUY**.
3. **Sector-diversify**: choose at most 1 per NSE Industry from your BUY list.
4. **Position sizing** — equal weight OR the tiered rule (STRONG 25%, BUY 20%).
5. **Set adaptive entry limit** at the buy_limit_low the scanner suggests. Cap chase at +1.5% above signal close.
6. **Enter the wishlist tracker** (Sheet 1) — it will monitor whether your limit filled and start the executability audit.
7. **Track daily**: if a stock recurs 4+ days in top-5, allocate up-front (sustained rank is the strongest signal).

### 🛑 Do NOT
- Buy 3 stocks from one sector "because they all ranked well" — that's ONE bet with 3 legs.
- Buy on the FIRST day a name appears in top-5 (29% win vs 76% at 4+ days).
- Chase a gap-up open more than 1.5% above the signal close.
- Override RS_LAGGARD in a RISK-OFF tape.
- Trade a stock with a scheduled corporate event within 3 sessions (EVENT_BLOCKED).

### 📊 Portfolio hygiene
- **Max 5 active** positions.
- **v5.1 ratchet lock** ON by default — will trim ~10% of your peak on winners, but rescues ~40% of what would have been STOP → TRAIL profits (net: median +2.3% vs +0.6%, win rate 58.6% vs 52.5%).
- **Anti-crowding** demotes stocks that got ahead of themselves — trust the ranker.

### 📚 Evidence log
* Walk-forward Jun 1 – Aug 1 2026, Nifty 500, daily top-5 → 220 picks, 76 unique tickers
* Rank-correlation with actual PnL: −0.047 → single-metric ranking is noise
* Sustained rank strongest signal: 4+ day recur = 76% win, 1 day = 29%
* Peak-vs-net gap: 43% of stops peaked > +5% before reversing → v5.1 ratchet
* 2 months live: 6 wishlist audits → all-loss except gold ETF, mostly BLOCKED_LIMIT_NOT_HIT — motivated adaptive entry + executability audit
""")


if __name__ == "__main__":
    st.set_page_config(page_title="Decision Framework", layout="wide")
    body()
