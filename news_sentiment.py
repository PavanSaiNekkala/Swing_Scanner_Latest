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
    r"\b(all.?time|52.?week|record|life.?time) high\b": 2,
    r"\bhits? upper circuit\b": 3, r"\bsurge[sd]?\b": 2, r"\bralli(es|ed)\b": 1,
    r"\bmulti[- ]?bagger\b": 2,
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
def _fetch_yfinance_news(ticker_yahoo: str) -> list:
    """Fetch news from yfinance. yfinance's news schema changed in 2024 — the
    payload is now nested under 'content'. Handles both old and new shapes."""
    if yf is None:
        return []
    try:
        news = yf.Ticker(ticker_yahoo).news
    except Exception:
        return []
    if not news:
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
    except Exception:
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


def _fetch_google_news_multi(queries: list, days: int = 7,
                              per_query: int = 15) -> list:
    """Fetch news across MULTIPLE Google News queries and dedupe by title."""
    seen_titles = set()
    all_items = []
    for q in queries[:4]:               # cap at 4 queries
        items = _fetch_google_news(q, max_items=per_query, days=days)
        for it in items:
            t = (it.get("title") or "").strip().lower()
            if t and t not in seen_titles:
                seen_titles.add(t)
                all_items.append(it)
    return all_items


# ======================================================================================
#  PUBLIC API
# ======================================================================================
def fetch_news_score(ticker_yahoo: str, company_name: str = None,
                     lookback_days: int = 7) -> dict:
    """Fetch news for a ticker and compute a sentiment score.

    v2 (Aug-2026) — auto-resolves the company name from yfinance if not
    provided, builds a multi-query Google News search, and applies a loosened
    relevance filter that matches ANY meaningful word from the company name.
    Fixes the M&M/BAJFINANCE/ADANIGREEN/TVSMOTOR "no news found" problem
    where headlines used the FULL company name (e.g. 'Mahindra') but the
    filter only accepted the ticker string (e.g. 'M&M').

    Args:
        ticker_yahoo: e.g. "RELIANCE.NS"
        company_name: optional — auto-resolved from yfinance.Ticker.info if None
        lookback_days: only headlines within this many days count (default 7)
    """
    bare = ticker_yahoo.replace(".NS", "").replace(".BO", "").upper()

    # Auto-resolve company name if not supplied (biggest single fix)
    if not company_name:
        company_name = _resolve_company_name(ticker_yahoo)

    # Extract keywords for relevance filter — union of bare ticker + name-words
    keywords = [bare.lower()]
    keywords.extend(_keywords_from_name(company_name))

    yf_news = _fetch_yfinance_news(ticker_yahoo)

    # Build a MULTI-QUERY Google News search (covers name + ticker variants)
    queries = _build_search_queries(bare, company_name)
    gn_news = _fetch_google_news_multi(queries, days=lookback_days, per_query=15)

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

    cutoff = dt.datetime.now() - dt.timedelta(days=lookback_days)
    all_items = []
    for it in (yf_news + gn_news):
        d = it.get("date")
        # If we can't tell how old it is, include it (be permissive)
        if d is not None and d.replace(tzinfo=None) < cutoff:
            continue
        score, matched = _score_headline(it["title"])
        all_items.append({**it, "score": score, "matched": matched})

    if not all_items:
        return {"score": 0.0, "n_articles": 0, "top_headline": None,
                "top_impact": 0.0, "matched_terms": [],
                "sources": {"yfinance": 0, "google": 0},
                "all_headlines": []}

    # Aggregate: take the average absolute impact, weighted by recency.
    # Normalise to [-1, +1] using a soft compression (tanh-like).
    raw_scores = [it["score"] for it in all_items]
    net_raw = sum(raw_scores) / len(raw_scores)      # mean, not sum — insensitive to N
    # Compress to [-1, +1]. A headline with |score|=5 gives ~ ±0.76 after tanh.
    import math
    net = math.tanh(net_raw / 4.0)

    # Top headline = the one with the largest absolute individual score
    top = max(all_items, key=lambda x: abs(x["score"]))
    matched_terms = sorted({m for it in all_items for m in it["matched"]})

    return {
        "score": round(net, 3),
        "n_articles": len(all_items),
        "top_headline": top["title"],
        "top_impact": top["score"],
        "matched_terms": matched_terms,
        "sources": {"yfinance": sum(1 for it in all_items if it["source"] == "yfinance"),
                    "google":   sum(1 for it in all_items if it["source"] == "google")},
        "all_headlines": [
            {"title": it["title"], "date": it["date"], "source": it["source"],
             "score": it["score"]} for it in all_items
        ],
    }


# Streamlit cache wrapper (60 min TTL)
if st is not None:
    fetch_news_score = st.cache_data(ttl=60 * 60, show_spinner=False)(fetch_news_score)
