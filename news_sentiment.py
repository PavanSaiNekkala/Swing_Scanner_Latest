"""
news_sentiment.py
=================
Free news + keyword-based sentiment scorer for the swing scanner.

Sources (both free, no auth):
  1. yfinance Ticker.news       — Reuters/Bloomberg wire, ~10 recent items
  2. Google News RSS            — very broad, pulls from 100+ Indian outlets

Sentiment engine: hand-curated Indian-market keyword lexicon. Higher precision
than off-the-shelf financial sentiment models on Indian news specifically
(picks up things like "SEBI probe", "auditor resigns", "wins order" which are
strong signals for INR-swing outcomes but poorly weighted by generic models).

Score returned in [-1, +1]:
   > +0.3  strong positive news (upgrade, buyback, big order, expansion)
   -0.3 to +0.3  neutral / mixed / no news
   < -0.3  strong negative news (downgrade, probe, resignation, penalty)

Cached 60 min — news moves fast but our scanner runs after market close, so
60min lets us re-scan within the same session without re-fetching everything.

Public API:
    fetch_news_score(ticker_yahoo) -> dict
"""

import re
import time
import datetime as dt
import urllib.parse
import urllib.request

try:
    import streamlit as st
except Exception:
    st = None

try:
    import yfinance as yf
except Exception:
    yf = None


# ======================================================================================
#  KEYWORD LEXICON — Indian-market tuned
# ======================================================================================
# Each keyword weighted by its typical price impact when it appears in a headline.
# Weights sum to ±5 for the strongest signals so a single big-impact word can
# drive the whole score.
_POSITIVE = {
    # Broker actions
    r"\bupgrade[sd]?\b": 3, r"\btarget (raised?|hiked?|increased?)\b": 3,
    r"\b(buy call|buy rating)\b": 2, r"\boutperform\b": 2, r"\boverweight\b": 2,
    r"\b(motilal|clsa|hsbc|jefferies|morgan|goldman|nomura|bernstein|bofa|kotak|"
    r"axis|elara) (upgrade|initiate|buy|outperform|target)\b": 3,
    r"\bbrokerage (upgrade|buy)\b": 2,
    r"\binitiate coverage\b": 2,
    # Results / operations
    r"\bbeats? (estimates?|expectations?|forecasts?|view|street|analysts?)\b": 4,
    r"\btops? (estimates?|expectations?|forecasts?|view|street)\b": 3,
    r"\b(strong|solid|robust) (quarter|q[1-4]|results|earnings|show|performance)\b": 3,
    r"\bprofit (surge|jump|rise|growth|rises?|jumps?|climbs?)\b": 3,
    r"\brecord (high|profit|revenue|quarter)\b": 3,
    r"\b(revenue|profit) (up|jumps?|rises?|surges?) \d+\s*%\b": 3,
    r"\bearnings? beat\b": 4,
    # Indian-market phrasings (Aug-2026 addition — catches headlines like
    # "M&M's July sales rose 24%" that the older lexicon missed)
    r"\b(sales|revenue|volumes?|deliveries?|dispatches?|shipments?|production) "
    r"(rose|grew|jumped|surged|climbed|increased|expanded) (by )?\d+"
    r"(\.\d+)?\s*%": 3,
    r"\b(sales|revenue|volumes?|profit) (rise|jump|surge|climb|growth|increase)\s+"
    r"\d+(\.\d+)?\s*%": 3,
    r"\bmarket share (leads?|gains?|rises?|expands?)\b": 2,
    r"\bmarket leader\b": 1,
    r"\bindex (inclusion|entry|addition)\b": 3,
    r"\breplace[sd]? \w+ in nifty\b": 3,
    r"\bnifty (inclusion|entry)\b": 3,
    r"\bindependent director\b": 0,       # neutral admin
    # Deals / orders
    r"\bwins? (order|contract|deal|tender)\b": 4,
    r"\bbags? (order|contract)\b": 4,
    r"\bawarded (contract|order)\b": 4,
    r"\b(joint venture|strategic partnership|acquisition)\b": 2,
    r"\bMoU\b": 1, r"\btie.?up\b": 1,
    # Capital returns
    r"\bbuyback\b": 3, r"\bbonus (issue|share)\b": 2,
    r"\bdividend (hike|increased?|higher|announced?)\b": 2,
    r"\brights (issue|offering)\b": 1,
    r"\bstock split\b": 2,
    # Expansion / momentum
    r"\bexpansion\b": 1, r"\bnew (plant|facility|capacity|hub)\b": 2,
    r"\blaunch(es|ed)?\b": 1,
    # v4 (Aug-2026 EVIDENCE-DRIVEN): "hits X-high" / "surges" / "rallies" are
    # RETROSPECTIVE — the move ALREADY happened before the headline was written.
    # Weekly Nifty-500 test showed PVRINOX at news_score 0.599 (dominated by
    # "rallies … hits 52-week high") delivered −2.73%. Weighting these as
    # BULLISH LEADING was wrong. Now they carry a small NEGATIVE weight
    # (priced-in tax) unless paired with genuinely forward-looking language.
    r"\b(all.?time|52.?week|record|life.?time)\s+high\b": -1,
    r"\bshares?\s+(soar|soars|surge|surges|jump|jumps|rally|rallies)\s+\d+": -2,
    r"\bstock\s+(soars|surges|jumps|rallies|rockets)\b": -1,
    r"\brallies?\s+\d+\s*%": -1,
    r"\bup\s+\d+\s*%\s+(today|this\s+week|ytd|so\s+far)\b": -1,
    r"\bhits? upper circuit\b": 3,   # KEEP positive — imminent momentum lock-up, not retrospective
    r"\bsurge[sd]?\b": 0,            # neutralised (was +2) — needs pairing with a specific reason
    r"\bralli(es|ed)\b": 0,          # neutralised (was +1) — same reason
    r"\bmulti[- ]?bagger\b": 1,      # softened (was +2) — usually said AFTER the move
    # Legal wins
    r"\b(court|judge) (clears?|dismisses?|drops?|acquits?)\b": 3,
    r"\bcharges? (dismissed?|dropped?|cleared?)\b": 4,
}

_NEGATIVE = {
    # Broker actions
    r"\bdowngrade[sd]?\b": -3, r"\btarget (cut|lowered?|reduced?)\b": -3,
    r"\b(sell call|sell rating)\b": -2, r"\bunderperform\b": -2,
    r"\bcautious\b": -1,
    # Regulatory / legal (BIG signals — most predictive of crash)
    r"\bSEBI (probe|order|penalty|action|investigation)\b": -5,
    r"\b(income tax|IT department) (raid|search|notice)\b": -5,
    r"\b(ED|CBI|SFIO|CCI) (probe|raid|search|investigation)\b": -5,
    r"\bpenalty\b": -2, r"\bfined?\b": -2,
    r"\bshow.?cause notice\b": -3,
    # Management issues
    r"\b(resigns?|resignation)\b": -3, r"\b(quit[st]?|steps? down|exit[ed]?)\b": -2,
    r"\barrest(ed)?\b": -5, r"\bhospitali[sz]ed\b": -3,
    r"\bauditor (resigns?|qualifies?|adverse|disclaimer)\b": -5,
    # Financial distress
    r"\bloss (widens?|deepens?)\b": -3,
    r"\bmisses? (estimates?|expectations?|forecasts?)\b": -3,
    r"\b(weak|disappointing) (quarter|q[1-4]|results)\b": -3,
    r"\b(profit|earnings) (falls?|declines?|drops?|plunges?)\b": -3,
    r"\bdefault(s|ed)?\b": -4, r"\binsolvency\b": -4, r"\bbankruptcy\b": -5,
    r"\b(NPA|non.?performing)\b": -2, r"\brestructure[dr]?\b": -2,
    # Indian-market phrasings (negative)
    r"\b(sales|revenue|volumes?|deliveries?|dispatches?|shipments?|production) "
    r"(fell|declined|dropped|slumped|plunged) (by )?\d+"
    r"(\.\d+)?\s*%": -3,
    r"\bindex (exclusion|removal|deletion)\b": -3,
    r"\bremoved from nifty\b": -3,
    # Sentiment
    r"\btumble[sd]?\b": -2, r"\bplunge[sd]?\b": -2, r"\bslump[sd]?\b": -2,
    r"\bhits? lower circuit\b": -3, r"\bcrash(es|ed)?\b": -3,
    r"\b(52.?week|record) low\b": -3,
    r"\boutflows?\b": -1,
    r"\bstake sale\b": -1,
    r"\bdivest(ment|iture)?\b": -1,
    # Deal breakdowns
    r"\b(deal|merger|acquisition) (fails?|falls? through|terminated?)\b": -3,
    r"\bfraud\b": -5, r"\bscandal\b": -4,
    # Legal escalations
    r"\b(indictment|charged|lawsuit|litigation)\b": -3,
    r"\b(criminal|bribery|corruption) (charges?|case|probe)\b": -4,
}


def _score_headline(text: str) -> tuple:
    """Return (raw_score, matched_terms_list) for a single headline."""
    if not text:
        return 0.0, []
    matched = []
    score = 0.0
    for pat, w in _POSITIVE.items():
        if re.search(pat, text, re.IGNORECASE):
            score += w
            matched.append(re.search(pat, text, re.IGNORECASE).group(0).lower())
    for pat, w in _NEGATIVE.items():
        if re.search(pat, text, re.IGNORECASE):
            score += w
            matched.append(re.search(pat, text, re.IGNORECASE).group(0).lower())
    return score, matched


# ======================================================================================
#  NEWS FETCHERS
# ======================================================================================
_LAST_FETCH_ERRORS = {}     # {ticker: (source, error_str)} — last-run diagnostics

def _fetch_yfinance_news(ticker_yahoo: str) -> list:
    """Fetch news from yfinance. yfinance's news schema changed in 2024 — the
    payload is now nested under 'content'. Handles both old and new shapes.

    v3.2 (Aug-2026): capture the exception into _LAST_FETCH_ERRORS so the UI
    can surface WHY a fetch failed instead of silently returning []."""
    if yf is None:
        _LAST_FETCH_ERRORS[ticker_yahoo] = ("yfinance", "yfinance not installed")
        return []
    try:
        news = yf.Ticker(ticker_yahoo).news
    except Exception as e:
        _LAST_FETCH_ERRORS[ticker_yahoo] = ("yfinance", f"{type(e).__name__}: {str(e)[:80]}")
        return []
    if not news:
        _LAST_FETCH_ERRORS.setdefault(ticker_yahoo, ("yfinance", "returned empty list"))
        return []
    out = []
    for a in news:
        c = a.get("content", a)               # new schema wraps under 'content'
        title = c.get("title") or a.get("title") or ""
        # timestamp: content.pubDate (ISO string) or old providerPublishTime (epoch)
        ts_raw = c.get("pubDate") or a.get("providerPublishTime") or ""
        pub_dt = None
        if isinstance(ts_raw, str) and ts_raw:
            try:
                pub_dt = dt.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except Exception:
                pass
        elif isinstance(ts_raw, (int, float)):
            try:
                pub_dt = dt.datetime.fromtimestamp(float(ts_raw))
            except Exception:
                pass
        if title:
            out.append({"title": title.strip(), "date": pub_dt, "source": "yfinance"})
    return out


def _fetch_google_news(query: str, max_items: int = 10, days: int = 3) -> list:
    """Fetch Google News RSS for a query. No dependencies — parses XML with regex.

    IMPORTANT (Aug-2026 freshness fix): Google News RSS defaults to sorting by
    RELEVANCE, which surfaces stale-but-topical articles (median age 44 days
    in a 10-stock audit). We force date-restriction using Google's advanced
    search operators:
      * `when:Nd`  → only results from the last N days (Google's RSS-native)
      * `+news`    → prioritise news over aggregator noise

    Note: Google may still return items older than `days` (its filter is
    approximate); the caller re-applies a hard cutoff for safety.
    """
    q_with_time = f"{query} when:{int(days)}d"
    q = urllib.parse.quote(q_with_time)
    url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        req = urllib.request.Request(url, headers={"User-Agent":
            "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36"})
        raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", errors="replace")
    except Exception as e:
        # v3.2: capture the actual error so callers can surface it. Use the
        # query as the key — one entry per query, gets overwritten by later
        # queries but at least we have visibility into what failed and why.
        _LAST_FETCH_ERRORS[f"__google:{query[:40]}"] = (
            "google", f"{type(e).__name__}: {str(e)[:80]}")
        return []
    # Extract each <item> block, then title + pubDate within
    items = re.findall(r"<item>(.*?)</item>", raw, re.DOTALL)
    out = []
    for block in items[:max_items]:
        tm = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.DOTALL)
        pm = re.search(r"<pubDate>(.*?)</pubDate>", block)
        if not tm:
            continue
        title = tm.group(1).strip()
        pub_dt = None
        if pm:
            try:
                pub_dt = dt.datetime.strptime(pm.group(1)[:25], "%a, %d %b %Y %H:%M:%S")
            except Exception:
                pass
        out.append({"title": title, "date": pub_dt, "source": "google"})
    return out


# ======================================================================================
#  COMPANY NAME RESOLUTION (Aug-2026)
# ======================================================================================
# Without the actual company name, Google searches for "M&M stock NSE" return
# M&M's candy or unrelated content. Fetching yfinance.Ticker.info["longName"]
# gives us "Mahindra & Mahindra Limited" — dramatically better search results
# AND a wider relevance filter.
_NAME_CACHE = {}   # in-process cache (ticker -> longName)

def _resolve_company_name(ticker_yahoo: str) -> str:
    """Return the stock's full company name (e.g. 'Mahindra & Mahindra Limited').
    Cached per process; falls back to '' if yfinance is unavailable."""
    if ticker_yahoo in _NAME_CACHE:
        return _NAME_CACHE[ticker_yahoo]
    name = ""
    if yf is not None:
        try:
            info = yf.Ticker(ticker_yahoo).info or {}
            name = (info.get("longName") or info.get("shortName") or "").strip()
        except Exception:
            name = ""
    _NAME_CACHE[ticker_yahoo] = name
    return name


_NAME_STOP = {"ltd", "ltd.", "limited", "company", "co.", "co", "corp",
              "corporation", "the", "and", "of", "in", "&", "india",
              "indian", "group", "grp", "inc", "pvt", "private", "public"}

# ------------------------------------------------------------------
# CONFUSABLES — same brand family, different listed company.
# When we search for one ticker's news, exclude articles about its
# similarly-named siblings so the sentiment score isn't polluted.
# ------------------------------------------------------------------
_CONFUSABLES = {
    # Mahindra & Mahindra (M&M) vs everything else in the Mahindra group
    "M&M":         ["tech mahindra", "mahindra financial", "mahindra holidays",
                    "mahindra lifespace", "mahindra cie", "mahindra epc",
                    "mahindra logistics"],
    # Bajaj family — Finance vs Auto vs Finserv vs Holdings
    "BAJFINANCE":  ["bajaj auto", "bajaj holdings", "bajaj finserv",
                    "bajaj hindusthan", "bajaj electricals"],
    "BAJAJFINSV":  ["bajaj auto", "bajaj holdings", "bajaj finance",
                    "bajaj hindusthan", "bajaj electricals"],
    "BAJAJ-AUTO":  ["bajaj finance", "bajaj finserv", "bajaj holdings"],
    # Adani group — many listed entities
    "ADANIGREEN":  ["adani ports", "adani total", "adani wilmar", "adani power",
                    "adani transmission", "adani energy solutions"],
    "ADANIENT":    ["adani green", "adani ports", "adani total", "adani wilmar",
                    "adani power", "adani transmission", "adani energy"],
    "ADANIPORTS":  ["adani green", "adani total", "adani wilmar", "adani power",
                    "adani transmission", "adani enterprises"],
    "ADANIPOWER":  ["adani green", "adani ports", "adani total", "adani wilmar",
                    "adani transmission", "adani enterprises"],
    # Tata family
    "TATAMOTORS":  ["tata power", "tata steel", "tata consultancy", "tata chemicals",
                    "tata elxsi", "tata communications", "tata investment",
                    "tata coffee", "tata consumer", "tcs", "tata technologies",
                    "titan"],
    "TATASTEEL":   ["tata power", "tata motors", "tata consultancy", "tata chemicals",
                    "tcs", "tata technologies"],
    "TATAPOWER":   ["tata steel", "tata motors", "tata consultancy",
                    "tcs", "tata chemicals"],
    "TCS":         ["tata power", "tata motors", "tata steel", "tata chemicals",
                    "tata elxsi"],
    "TATATECH":    ["tata power", "tata motors", "tata steel", "tata consultancy",
                    "tcs", "tata chemicals"],
    "TATACONSUM":  ["tata power", "tata motors", "tata steel", "tata consultancy",
                    "tcs", "tata chemicals"],
    # TVS family
    "TVSMOTOR":    ["tvs supply chain", "tvs srichakra", "tvs electronics",
                    "tvs holdings"],
    # Reliance family
    "RELIANCE":    ["reliance power", "reliance infra", "reliance capital",
                    "reliance nippon", "reliance communications"],
    # Godrej family
    "GODREJCP":    ["godrej properties", "godrej industries", "godrej agrovet"],
    "GODREJPROP":  ["godrej consumer", "godrej industries", "godrej agrovet"],
    # HDFC family
    "HDFCBANK":    ["hdfc life", "hdfc amc", "hdfc securities"],
    "HDFCLIFE":    ["hdfc bank", "hdfc amc"],
    "HDFCAMC":     ["hdfc bank", "hdfc life"],
    # Aditya Birla family
    "ULTRACEMCO":  ["aditya birla capital", "aditya birla fashion", "grasim"],
    "GRASIM":      ["aditya birla capital", "aditya birla fashion", "ultratech"],
    "ABCAPITAL":   ["aditya birla fashion", "ultratech", "grasim"],
}


def _keywords_from_name(name: str) -> list:
    """Extract meaningful search terms from a company name.
    E.g. 'Mahindra & Mahindra Limited' -> ['mahindra']
         'Bajaj Finance Limited'       -> ['bajaj', 'finance']
         'Adani Green Energy Ltd'      -> ['adani', 'green', 'energy']
    """
    if not name: return []
    out = []
    for w in name.split():
        wl = w.lower().strip(",.()'-\"")
        if wl and len(wl) >= 3 and wl not in _NAME_STOP and wl not in out:
            out.append(wl)
    return out


def _build_search_queries(bare_ticker: str, company_name: str) -> list:
    """Build a small set of complementary Google News queries. Fewer than 4
    to keep rate-limit pressure manageable."""
    queries = []
    if company_name:
        # Strip trailing 'Limited/Ltd' — usually noise in queries
        clean = company_name
        for suf in (" Limited", " Ltd.", " Ltd", " Corporation", " Corp"):
            if clean.endswith(suf):
                clean = clean[:-len(suf)]
        clean = clean.strip()
        queries.append(clean)                               # e.g. "Mahindra & Mahindra"
        queries.append(f"{clean} share price")              # results/earnings coverage
        queries.append(f"{clean} nse")                      # NSE-specific
    # Fall back to ticker-based query too, especially for stocks with unusual names
    if bare_ticker:
        queries.append(f"{bare_ticker} stock nse")
    # De-dupe while preserving order
    seen, out = set(), []
    for q in queries:
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


# v3.4 (Aug-2026): Google News RSS rate-limit protection.
# --------------------------------------------------------------
# Google returns EMPTY responses (not HTTP 429) when rate-limited, so we
# can't detect the block from HTTP status alone. Instead:
#   1. Sleep ~0.35s between queries to stay under Google's per-IP threshold
#      (empirically: <3 queries/sec sustained keeps us un-blocked).
#   2. If a query returns 0 items AND the previous query returned 0,
#      pause for `_BACKOFF_S` seconds — Google is very likely blocking us.
#   3. Track a session-level "blocked" flag that fast-fails remaining queries
#      once we're confident we're blocked. Prevents wasting 5s per query
#      × 100 stocks × 4 queries = 33 min of wall-clock waiting for empties.
import time as _time

_INTER_QUERY_SLEEP_S = 0.35     # empirical — see comment above
_BACKOFF_S           = 5.0
_BLOCK_STREAK_LIMIT  = 5        # 5 consecutive 0-item queries → assume blocked
_session_block       = {"blocked": False, "zero_streak": 0}


def reset_google_block_flag():
    """Call at the start of a fresh scan run to reset the session-level
    rate-limit flag. Otherwise the flag persists across scans and legitimate
    fetches get skipped."""
    _session_block["blocked"]     = False
    _session_block["zero_streak"] = 0


def _fetch_google_news_multi(queries: list, days: int = 7,
                              per_query: int = 15) -> list:
    """Fetch news across MULTIPLE Google News queries and dedupe by title.
    v3.4: rate-limit aware — sleeps between queries, backs off on empties,
    fast-fails once we're confident we're blocked for this session."""
    seen_titles = set()
    all_items = []
    for qi, q in enumerate(queries[:4]):
        if _session_block["blocked"]:
            break                          # skip remaining queries this call
        if qi > 0:
            _time.sleep(_INTER_QUERY_SLEEP_S)
        items = _fetch_google_news(q, max_items=per_query, days=days)
        if items:
            _session_block["zero_streak"] = 0
            for it in items:
                t = (it.get("title") or "").strip().lower()
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    all_items.append(it)
        else:
            _session_block["zero_streak"] += 1
            if _session_block["zero_streak"] >= _BLOCK_STREAK_LIMIT:
                _session_block["blocked"] = True
                _LAST_FETCH_ERRORS["__RATE_LIMIT__"] = (
                    "google",
                    f"5 consecutive empty responses — Google RSS is rate-"
                    f"limiting this IP. Fast-failing rest of the run to save "
                    f"time. Wait 5-15 min and rerun with cache-clear.")
                break
            # Small back-off on any empty response to give Google breathing room
            _time.sleep(_BACKOFF_S / 5)
    return all_items


# ======================================================================================
#  PUBLIC API
# ======================================================================================
def fetch_news_score(ticker_yahoo: str, company_name: str = None,
                     lookback_days: int = 7,
                     as_of_date=None) -> dict:
    """Fetch news for a ticker and compute a sentiment score.

    v2 (Aug-2026) — auto-resolves the company name from yfinance if not
    provided, builds a multi-query Google News search, and applies a loosened
    relevance filter that matches ANY meaningful word from the company name.
    Fixes the M&M/BAJFINANCE/ADANIGREEN/TVSMOTOR "no news found" problem
    where headlines used the FULL company name (e.g. 'Mahindra') but the
    filter only accepted the ticker string (e.g. 'M&M').

    v3 (Aug-2026) — NO-LOOK-AHEAD support via `as_of_date`.
        For live scanner use (`as_of_date=None`): behaves exactly as v2 —
        returns headlines from the last `lookback_days` calendar days.
        For forward validation (`as_of_date=<cutoff>`): filters headlines to
        the window [as_of_date - lookback_days, as_of_date]. Any headline
        published AFTER as_of_date is dropped (look-ahead contamination).
        The Google News query is widened so items published between
        as_of_date and today aren't the ONLY ones returned — otherwise
        the post-filter would leave the bucket empty for old cutoffs.

    Args:
        ticker_yahoo: e.g. "RELIANCE.NS"
        company_name: optional — auto-resolved from yfinance.Ticker.info if None
        lookback_days: length of the news window in calendar days (default 7)
        as_of_date:   `date` or `datetime`. When provided, the window is
                      [as_of_date - lookback_days, as_of_date] and any headline
                      after as_of_date is EXCLUDED (no-look-ahead). None = "now".
    """
    bare = ticker_yahoo.replace(".NS", "").replace(".BO", "").upper()

    # Auto-resolve company name if not supplied (biggest single fix)
    if not company_name:
        company_name = _resolve_company_name(ticker_yahoo)

    # Extract keywords for relevance filter — union of bare ticker + name-words
    keywords = [bare.lower()]
    keywords.extend(_keywords_from_name(company_name))

    # -------- v3: figure out the reference datetime for the lookback window --------
    if as_of_date is not None:
        # Accept either date or datetime; treat date as end-of-day so a headline
        # timestamped 2026-08-08 15:37 still qualifies when as_of_date=2026-08-08.
        if isinstance(as_of_date, dt.datetime):
            ref_dt = as_of_date
        else:
            ref_dt = dt.datetime.combine(as_of_date, dt.time.max)
    else:
        ref_dt = dt.datetime.now()

    # If cutoff is in the past, widen Google's `when:` query so items from
    # BEFORE the cutoff are actually returned. Google's when:Nd is relative
    # to NOW (the moment Google runs the query), NOT to our ref_dt.
    #
    # v3.1 FIX (Aug-2026): the previous "lookback + days_since_ref" widening
    # wasn't enough because Google News RSS is heavily recency-biased — even
    # with when:14d, most returned items are dated in the last 3-4 days. For
    # a cutoff 8 days ago that meant every returned item post-dated the
    # cutoff and got dropped by the post-filter → 0 kept articles.
    # Fix: when as_of_date is provided, use Google's practical MAX (30 days)
    # AND double per_query, so we cover the full window and get enough items
    # dated on-or-before the cutoff to survive the filter.
    days_from_now_to_ref = max(0, (dt.datetime.now() - ref_dt).days)
    if as_of_date is not None:
        google_days = 30                         # Google's practical ceiling
        per_query = 40                           # 2.6× the live-mode default
    else:
        google_days = int(lookback_days)
        per_query = 15

    yf_news = _fetch_yfinance_news(ticker_yahoo)

    # Build a MULTI-QUERY Google News search (covers name + ticker variants)
    queries = _build_search_queries(bare, company_name)
    gn_news = _fetch_google_news_multi(queries, days=google_days, per_query=per_query)

    # LOOSENED relevance filter — matches ANY meaningful company-name word
    # OR the bare ticker. AND checks the CONFUSABLES exclusion list so we
    # don't grab "Tech Mahindra" articles when searching for M&M.
    confusable_phrases = _CONFUSABLES.get(bare, [])
    def _is_relevant(title: str) -> bool:
        if not title: return False
        tl = title.lower()
        # Reject if title matches a known confusable (sibling company)
        for cp in confusable_phrases:
            if cp in tl:
                return False
        # Accept if any keyword matches
        return any(k in tl for k in keywords)
    gn_news = [it for it in gn_news if _is_relevant(it["title"])]

    # -------- Window filter: [ref_dt - lookback_days, ref_dt] --------
    # Any headline dated AFTER ref_dt is a look-ahead violation (excluded).
    # Any headline dated BEFORE ref_dt - lookback_days is out of window.
    # Undated headlines pass (be permissive — yfinance items sometimes lack dates).
    earliest = ref_dt - dt.timedelta(days=lookback_days)
    all_items = []
    # ---- Diagnostics for the UI: how many RAW items did we fetch, and what
    # was their date range? Helps the user diagnose "0 kept" — was it 0 raw
    # fetched (Google rate-limited / blocked), or 30 raw items all dated
    # after the cutoff (fetch worked but nothing pre-cutoff)?
    raw_items_all = yf_news + gn_news
    raw_fetched = len(raw_items_all)
    # v3.3: strip tzinfo defensively so min/max never sees mixed aware/naive.
    _raw_dates = []
    for it in raw_items_all:
        d = it.get("date")
        if d is None:
            continue
        if hasattr(d, "tzinfo") and d.tzinfo is not None:
            d = d.replace(tzinfo=None)
        _raw_dates.append(d)
    raw_oldest = min(_raw_dates) if _raw_dates else None
    raw_newest = max(_raw_dates) if _raw_dates else None
    dropped_look_ahead = 0
    dropped_too_old    = 0
    for it in raw_items_all:
        d = it.get("date")
        # v3.3 BUG FIX (Aug-2026): normalise timezone HERE, then store the
        # naive version back on the item. Previously the filter used a naive
        # copy `d_cmp` for comparison but appended the ORIGINAL tz-aware
        # date to all_items — downstream `max(all_items, key=x["date"])`
        # then crashed with "can't compare offset-naive and offset-aware
        # datetimes" whenever the list mixed yfinance (ISO/tz-aware) and
        # Google News (RFC-2822/tz-naive) items. That killed ~10% of runs
        # (5 out of 50 SmallCap tickers in the reproduction).
        if d is not None:
            if hasattr(d, "tzinfo") and d.tzinfo is not None:
                d = d.replace(tzinfo=None)
            if d > ref_dt:
                dropped_look_ahead += 1
                continue                # look-ahead — drop
            if d < earliest:
                dropped_too_old += 1
                continue                # too old — drop
        score, matched = _score_headline(it["title"])
        all_items.append({**it, "date": d, "score": score, "matched": matched})

    if not all_items:
        return {"score": 0.0, "n_articles": 0,
                "top_headline": None, "top_date": None, "top_impact": 0.0,
                "latest_headline": None, "latest_date": None,
                "latest_impact": 0.0, "latest_source": None,
                "matched_terms": [],
                "sources": {"yfinance": 0, "google": 0},
                "all_headlines": [],
                "window_from": earliest.date() if hasattr(earliest, "date") else None,
                "window_to":   ref_dt.date()  if hasattr(ref_dt, "date")   else None,
                "as_of_used":  (as_of_date if as_of_date is not None else None),
                # Diagnostics: why did we return 0 items?
                "raw_fetched":        raw_fetched,
                "raw_oldest":         raw_oldest.date() if raw_oldest else None,
                "raw_newest":         raw_newest.date() if raw_newest else None,
                "dropped_look_ahead": dropped_look_ahead,
                "dropped_too_old":    dropped_too_old,
                "google_days_used":   google_days}

    # Aggregate: take the average absolute impact, weighted by recency.
    # Normalise to [-1, +1] using a soft compression (tanh-like).
    raw_scores = [it["score"] for it in all_items]
    net_raw = sum(raw_scores) / len(raw_scores)      # mean, not sum — insensitive to N
    # Compress to [-1, +1]. A headline with |score|=5 gives ~ ±0.76 after tanh.
    import math
    net = math.tanh(net_raw / 4.0)

    # Top headline = the one with the largest absolute individual score
    #                (biggest single-item impact — dominates the average).
    top = max(all_items, key=lambda x: abs(x["score"]))

    # Latest headline = the most-recent article by publication date.
    # Different concept from `top`: e.g. a +4 "beats estimates" beat 4 days ago
    # will be the `top` slot, while a −3 "resigns" story from yesterday will be
    # the `latest`. Users want to see both — recency AND impact — because a
    # small-|score| news item can still be the most decision-relevant piece of
    # information (management change, regulatory notice, etc.).
    #
    # Fall back to `top` when no article carries a parseable date (e.g. all
    # yfinance items with missing pubDate) so the caller never sees None.
    items_with_date = [it for it in all_items if it.get("date") is not None]
    if items_with_date:
        latest = max(items_with_date, key=lambda x: x["date"])
    else:
        latest = top
    matched_terms = sorted({m for it in all_items for m in it["matched"]})

    return {
        "score": round(net, 3),
        "n_articles": len(all_items),
        "top_headline": top["title"],
        "top_date":     top.get("date"),        # NEW — pairs with latest_date
        "top_impact":   top["score"],
        "latest_headline": latest["title"],
        "latest_date":     latest.get("date"),
        "latest_impact":   float(latest["score"]),
        "latest_source":   latest.get("source"),
        "matched_terms": matched_terms,
        "sources": {"yfinance": sum(1 for it in all_items if it["source"] == "yfinance"),
                    "google":   sum(1 for it in all_items if it["source"] == "google")},
        "all_headlines": [
            {"title": it["title"], "date": it["date"], "source": it["source"],
             "score": it["score"]} for it in all_items
        ],
        # v3: the actual window applied (useful for the UI to prove no look-ahead)
        "window_from": earliest.date() if hasattr(earliest, "date") else None,
        "window_to":   ref_dt.date()   if hasattr(ref_dt, "date")   else None,
        "as_of_used":  (as_of_date if as_of_date is not None else None),
        # v3.1: diagnostics — makes "why did I get so few items?" answerable
        "raw_fetched":        raw_fetched,
        "raw_oldest":         raw_oldest.date() if raw_oldest else None,
        "raw_newest":         raw_newest.date() if raw_newest else None,
        "dropped_look_ahead": dropped_look_ahead,
        "dropped_too_old":    dropped_too_old,
        "google_days_used":   google_days,
    }


# Streamlit cache wrapper (60 min TTL)
if st is not None:
    fetch_news_score = st.cache_data(ttl=60 * 60, show_spinner=False)(fetch_news_score)


# ======================================================================================
#  DIAGNOSTIC HELPERS (v3.2 — Aug-2026)
# ======================================================================================
def clear_news_cache() -> None:
    """Wipe the Streamlit in-memory news cache. Call this when the user hits
    the sidebar 'Force refresh news' button — necessary because stale
    zero-item results from an earlier module version otherwise persist for
    60 min per Streamlit session. Also resets the rate-limit tracker."""
    global _LAST_FETCH_ERRORS
    _LAST_FETCH_ERRORS = {}
    _session_block["blocked"]     = False
    _session_block["zero_streak"] = 0
    try:
        fetch_news_score.clear()
    except Exception:
        pass


def is_rate_limited() -> bool:
    """True if this session has hit the empty-response streak threshold and
    is fast-failing subsequent queries. UI can surface this so the user
    doesn't wonder why later stocks show 0 news."""
    return bool(_session_block["blocked"])


def get_last_fetch_errors() -> dict:
    """Return the last-run per-source fetch errors (yfinance / google).
    UI can render this in a debug expander when raw_fetched == 0 to explain
    what actually failed instead of hand-waving 'probably rate-limited'."""
    return dict(_LAST_FETCH_ERRORS)


def reset_fetch_errors() -> None:
    """Clear the error log before a new run — otherwise stale errors from
    a previous run leak into the current diagnostic."""
    global _LAST_FETCH_ERRORS
    _LAST_FETCH_ERRORS = {}
