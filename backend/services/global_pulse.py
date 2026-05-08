"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.

Global Pulse Service — World-Sense Intelligence + Economic Intelligence Hub
============================================================================
Real-time aggregation of:
  - Global news via RSS feeds (no API key needed)
  - Bank of Canada Valet API (free, no key) — CAD/USD, BoC policy rate
  - Alpha Vantage free tier (25 calls/day) — S&P 500, VIX, global markets
  - Geo-aware context (Canada/India/USA detection)
  - Recursive Brain: daily delta tracking (no predictions)
  - Zero-Loss persistence via global_pulse_shadow cache

COMPLIANCE: Economic data for business context only. Not investment advice.
All language uses "context", "indicator", "data" — never "prediction", "forecast", "signal".
"""
import logging
import asyncio
import aiohttp
try:
    import feedparser
except ImportError:
    feedparser = None
import re
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_db = None
_pulse_cache = {}  # In-memory shadow cache for <100ms reads
_boc_cache = {}    # Bank of Canada data cache
_ticker_cache = {} # Ticker rotation cache

ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_KEY", "")

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

INDUSTRY_KEYWORDS = [
    "biotech", "aesthetics", "medspa", "skincare", "dermatology", "pdrn",
    "ai", "artificial intelligence", "saas", "machine learning",
    "startup", "venture capital", "ipo", "acquisition",
    "dental", "wellness", "fitness", "health tech", "telehealth",
    "ecommerce", "shopify", "woocommerce", "stripe",
    "crypto", "bitcoin", "blockchain", "defi",
    "real estate", "mortgage", "interest rate",
    "recession", "inflation", "tariff", "trade war",
    "fda", "regulation", "compliance",
]

NEWS_RSS_FEEDS = [
    {"name": "Google News - Business", "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtVnVHZ0pWVXlnQVAB"},
    {"name": "Google News - Technology", "url": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB"},
    {"name": "Google News - Health", "url": "https://news.google.com/rss/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtVnVLQUFQAQ"},
    {"name": "Reuters - Business", "url": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
]

MARKET_FEEDS = [
    {"name": "Yahoo Finance - Market", "url": "https://finance.yahoo.com/news/rssindex"},
]

VIX_FALLBACK = 18.5

# Bank of Canada Valet API series
BOC_SERIES = {
    "cad_usd": "FXUSDCAD",          # USD/CAD exchange rate
    "policy_rate": "V39079",          # BoC overnight rate target
    "bank_rate": "V122530",           # Bank rate (policy rate + 0.25%)
}
BOC_VALET_BASE = "https://www.bankofcanada.ca/valet/observations"

# Upcoming BoC interest rate decision dates (2026)
BOC_DECISION_DATES = [
    "2026-01-29", "2026-03-12", "2026-04-16", "2026-06-04",
    "2026-07-15", "2026-09-03", "2026-10-22", "2026-12-10",
]


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# BANK OF CANADA VALET API (Free, No Key)
# ═══════════════════════════════════════════════════════════════

async def fetch_boc_data() -> dict:
    """Fetch Bank of Canada data: CAD/USD exchange, policy rate, prime rate."""
    result = {
        "cad_usd_rate": None,
        "cad_usd_change_pct": None,
        "policy_rate": None,
        "bank_rate": None,
        "next_boc_decision": _next_boc_decision(),
        "source": "Bank of Canada Valet API",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_cached": False,
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Fetch CAD/USD (FXUSDCAD) — last 5 observations for change calc
            try:
                url = f"{BOC_VALET_BASE}/{BOC_SERIES['cad_usd']}/json?recent=5"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        obs = data.get("observations", [])
                        if obs:
                            latest = obs[-1]
                            rate_val = latest.get(BOC_SERIES["cad_usd"], {}).get("v")
                            if rate_val:
                                result["cad_usd_rate"] = round(float(rate_val), 4)
                            # Calculate daily change
                            if len(obs) >= 2:
                                prev_val = obs[-2].get(BOC_SERIES["cad_usd"], {}).get("v")
                                if prev_val and rate_val:
                                    prev = float(prev_val)
                                    curr = float(rate_val)
                                    if prev > 0:
                                        result["cad_usd_change_pct"] = round(((curr - prev) / prev) * 100, 3)
            except Exception as e:
                logger.debug(f"[GlobalPulse] BoC CAD/USD fetch error: {e}")

            # Fetch Policy Rate
            try:
                url = f"{BOC_VALET_BASE}/{BOC_SERIES['policy_rate']}/json?recent=1"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        obs = data.get("observations", [])
                        if obs:
                            val = obs[-1].get(BOC_SERIES["policy_rate"], {}).get("v")
                            if val:
                                result["policy_rate"] = float(val)
            except Exception as e:
                logger.debug(f"[GlobalPulse] BoC policy rate fetch error: {e}")

            # Fetch Bank Rate
            try:
                url = f"{BOC_VALET_BASE}/{BOC_SERIES['bank_rate']}/json?recent=1"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        obs = data.get("observations", [])
                        if obs:
                            val = obs[-1].get(BOC_SERIES["bank_rate"], {}).get("v")
                            if val:
                                result["bank_rate"] = float(val)
            except Exception as e:
                logger.debug(f"[GlobalPulse] BoC bank rate fetch error: {e}")

    except Exception as e:
        logger.warning(f"[GlobalPulse] BoC API error: {e}")

    # Cache to memory
    _boc_cache["latest"] = result
    _boc_cache["cached_at"] = datetime.now(timezone.utc)

    # Persist to DB shadow
    db = _get_db()
    if db is not None:
        try:
            await db.global_pulse_shadow.update_one(
                {"key": "boc_latest"},
                {"$set": {"data": result, "updated_at": datetime.now(timezone.utc).isoformat()},
                 "$setOnInsert": {"key": "boc_latest", "created_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception:
            pass

    return result


async def get_boc_cached() -> dict:
    """Get BoC data from cache, fallback to DB shadow if API unavailable."""
    # 1. Memory cache (< 30 min)
    if "latest" in _boc_cache:
        cached_at = _boc_cache.get("cached_at")
        if cached_at and (datetime.now(timezone.utc) - cached_at).total_seconds() < 1800:
            return _boc_cache["latest"]

    # 2. DB shadow cache
    db = _get_db()
    if db is not None:
        shadow = await db.global_pulse_shadow.find_one({"key": "boc_latest"}, {"_id": 0})
        if shadow and shadow.get("data"):
            cached_data = shadow["data"]
            cached_data["is_cached"] = True
            _boc_cache["latest"] = cached_data
            _boc_cache["cached_at"] = datetime.now(timezone.utc)
            return cached_data

    # 3. Fresh fetch
    return await fetch_boc_data()


def _next_boc_decision() -> str:
    """Get the next Bank of Canada interest rate decision date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for d in BOC_DECISION_DATES:
        if d >= today:
            return d
    return "TBD"


# ═══════════════════════════════════════════════════════════════
# ALPHA VANTAGE (Free Tier — 25 calls/day)
# ═══════════════════════════════════════════════════════════════

async def fetch_alpha_vantage_data() -> dict:
    """Fetch global market indicators via Alpha Vantage free tier."""
    av_data = {
        "sp500": None,
        "sensex": None,
        "vix": None,
        "source": "Alpha Vantage",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "is_cached": False,
    }

    key = ALPHA_VANTAGE_KEY
    if not key:
        # Fallback to cached data
        return await _get_av_cache()

    try:
        async with aiohttp.ClientSession() as session:
            # S&P 500 (SPY as proxy)
            try:
                url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={key}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quote = data.get("Global Quote", {})
                        if quote.get("05. price"):
                            av_data["sp500"] = round(float(quote["05. price"]), 2)
            except Exception as e:
                logger.debug(f"[GlobalPulse] Alpha Vantage SPY error: {e}")

            # VIX
            try:
                url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=VIX&apikey={key}"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        quote = data.get("Global Quote", {})
                        if quote.get("05. price"):
                            av_data["vix"] = round(float(quote["05. price"]), 2)
            except Exception as e:
                logger.debug(f"[GlobalPulse] Alpha Vantage VIX error: {e}")

    except Exception as e:
        logger.warning(f"[GlobalPulse] Alpha Vantage error: {e}")

    # Cache
    db = _get_db()
    if db is not None:
        try:
            await db.global_pulse_shadow.update_one(
                {"key": "alpha_vantage_latest"},
                {"$set": {"data": av_data, "updated_at": datetime.now(timezone.utc).isoformat()},
                 "$setOnInsert": {"key": "alpha_vantage_latest", "created_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception:
            pass

    return av_data


async def _get_av_cache() -> dict:
    """Get Alpha Vantage data from DB shadow cache."""
    db = _get_db()
    if db is not None:
        shadow = await db.global_pulse_shadow.find_one({"key": "alpha_vantage_latest"}, {"_id": 0})
        if shadow and shadow.get("data"):
            cached = shadow["data"]
            cached["is_cached"] = True
            return cached
    return {"sp500": None, "sensex": None, "vix": None, "source": "Alpha Vantage", "is_cached": True,
            "fetched_at": None}


# ═══════════════════════════════════════════════════════════════
# GEO-AWARE CONTEXT
# ═══════════════════════════════════════════════════════════════

async def get_geo_context(tenant_id: str = None) -> str:
    """Detect tenant location and return region code (ca, in, us)."""
    db = _get_db()
    if db is not None and tenant_id:
        try:
            tenant = await db.users.find_one({"id": tenant_id}, {"_id": 0, "country": 1, "location": 1, "timezone": 1})
            if tenant:
                country = (tenant.get("country") or "").lower()
                location = (tenant.get("location") or "").lower()
                tz = (tenant.get("timezone") or "").lower()
                if "canada" in country or "ca" == country or "toronto" in location or "america/toronto" in tz:
                    return "ca"
                if "india" in country or "in" == country or "mumbai" in location or "kolkata" in tz:
                    return "in"
                if "us" in country or "united states" in country or "america" in tz:
                    return "us"
        except Exception:
            pass
    return "ca"  # Default to Canada


# ═══════════════════════════════════════════════════════════════
# RSS FEED PARSER
# ═══════════════════════════════════════════════════════════════

def _matches_industry(text: str) -> list:
    text_lower = text.lower()
    return [kw for kw in INDUSTRY_KEYWORDS if kw in text_lower]


async def _fetch_feed(session: aiohttp.ClientSession, feed: dict) -> list:
    items = []
    try:
        async with session.get(feed["url"], timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                text = await resp.text()
                if feedparser is None:
                    return items
                parsed = feedparser.parse(text)
                for entry in parsed.entries[:15]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", entry.get("description", ""))
                    link = entry.get("link", "")
                    published = entry.get("published", "")
                    clean_summary = re.sub(r'<[^>]+>', '', summary)[:300]
                    matched = _matches_industry(f"{title} {clean_summary}")
                    if matched:
                        items.append({
                            "source": feed["name"],
                            "title": title,
                            "summary": clean_summary,
                            "link": link,
                            "published": published,
                            "keywords": matched,
                            "fetched_at": datetime.now(timezone.utc).isoformat(),
                        })
    except Exception as e:
        logger.debug(f"[GlobalPulse] Feed fetch error ({feed['name']}): {e}")
    return items


async def fetch_global_news() -> list:
    all_items = []
    try:
        async with aiohttp.ClientSession() as session:
            tasks = [_fetch_feed(session, f) for f in NEWS_RSS_FEEDS + MARKET_FEEDS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_items.extend(result)
    except Exception as e:
        logger.warning(f"[GlobalPulse] News fetch error: {e}")

    seen = set()
    unique = []
    for item in all_items:
        key = item["title"][:50]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# ═══════════════════════════════════════════════════════════════
# FINANCIAL MARKET DATA (combined BoC + Alpha Vantage + fallback)
# ═══════════════════════════════════════════════════════════════

async def fetch_market_data() -> dict:
    """Fetch combined market data: BoC + Alpha Vantage + VIX estimate."""
    boc, av = await asyncio.gather(
        fetch_boc_data(),
        fetch_alpha_vantage_data(),
    )

    vix_val = av.get("vix") or VIX_FALLBACK
    sentiment = "neutral"
    vix_alert = False
    if vix_val > 25:
        vix_alert = True
        sentiment = "elevated_risk"
    elif vix_val > 20:
        sentiment = "cautious"
    elif vix_val < 15:
        sentiment = "stable"

    market = {
        "cad_usd": boc.get("cad_usd_rate"),
        "cad_usd_change_pct": boc.get("cad_usd_change_pct"),
        "policy_rate": boc.get("policy_rate"),
        "bank_rate": boc.get("bank_rate"),
        "next_boc_decision": boc.get("next_boc_decision"),
        "sp500": av.get("sp500"),
        "sensex": av.get("sensex"),
        "vix_estimate": vix_val,
        "vix_alert": vix_alert,
        "market_sentiment": sentiment,
        "boc_is_cached": boc.get("is_cached", False),
        "av_is_cached": av.get("is_cached", False),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    return market


# ═══════════════════════════════════════════════════════════════
# TICKER DATA (for frontend EconomicTicker rotation)
# ═══════════════════════════════════════════════════════════════

async def get_ticker_items(tenant_id: str = None) -> list:
    """Build ticker rotation items: CAD/USD, BoC rate, next econ date."""
    boc = await get_boc_cached()
    items = []

    # 1. CAD/USD rate + daily change
    rate = boc.get("cad_usd_rate")
    change = boc.get("cad_usd_change_pct")
    if rate:
        change_str = f" ({change:+.2f}%)" if change is not None else ""
        stale = f" (As of {boc.get('fetched_at', 'N/A')[:10]})" if boc.get("is_cached") else ""
        items.append({
            "id": "cad_usd",
            "label": f"CAD/USD {rate}{change_str}{stale}",
            "value": rate,
            "change_pct": change,
            "type": "exchange",
        })
    else:
        items.append({"id": "cad_usd", "label": "CAD/USD — unavailable", "value": None, "type": "exchange"})

    # 2. BoC policy rate
    policy = boc.get("policy_rate")
    if policy is not None:
        items.append({
            "id": "boc_rate",
            "label": f"BoC Rate {policy}%",
            "value": policy,
            "type": "rate",
        })
    else:
        items.append({"id": "boc_rate", "label": "BoC Rate — unavailable", "value": None, "type": "rate"})

    # 3. Next major economic date
    next_date = boc.get("next_boc_decision", _next_boc_decision())
    items.append({
        "id": "next_econ_date",
        "label": f"Next BoC Decision: {next_date}",
        "value": next_date,
        "type": "date",
    })

    return items


# ═══════════════════════════════════════════════════════════════
# ECONOMIC CONTEXT FOR MORNING BRIEF
# ═══════════════════════════════════════════════════════════════

async def build_economic_brief_line() -> str:
    """Build a max-2-line economic context string for the Morning Brief.
    Format: 'Economic context: CAD/USD {rate} ({change}% vs yesterday). Next BoC decision: {date}.'
    No numbers older than 24h. No predictions."""
    boc = await get_boc_cached()

    rate = boc.get("cad_usd_rate")
    change = boc.get("cad_usd_change_pct")
    next_decision = boc.get("next_boc_decision", _next_boc_decision())

    # Check freshness — no numbers older than 24h
    fetched = boc.get("fetched_at")
    if fetched:
        try:
            fetched_dt = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - fetched_dt).total_seconds() > 86400:
                return ""
        except Exception:
            pass

    if rate is None:
        return ""

    change_str = f"({change:+.2f}% vs yesterday)" if change is not None else "(change unavailable)"
    return f"Economic context: CAD/USD {rate} {change_str}. Next BoC decision: {next_decision}."


# ═══════════════════════════════════════════════════════════════
# GLOBAL PULSE AGGREGATION + PERSISTENCE
# ═══════════════════════════════════════════════════════════════

async def run_global_pulse() -> dict:
    """Run a full Global Pulse scan: news + markets. Store + cache."""
    news, market = await asyncio.gather(
        fetch_global_news(),
        fetch_market_data(),
    )

    pulse = {
        "news_items": news,
        "news_count": len(news),
        "market": market,
        "top_keywords": _top_keywords(news),
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "compliance_notice": "Economic data for business context only. Not investment advice.",
    }

    db = _get_db()
    if db is not None:
        try:
            await db.global_pulse.insert_one({**pulse})
            await db.global_pulse_shadow.update_one(
                {"key": "latest"},
                {"$set": {"data": pulse, "updated_at": datetime.now(timezone.utc).isoformat()},
                 "$setOnInsert": {"key": "latest", "created_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"[GlobalPulse] DB persist error: {e}")

    _pulse_cache["latest"] = pulse
    _pulse_cache["cached_at"] = datetime.now(timezone.utc)

    logger.info(f"[GlobalPulse] Scan complete: {len(news)} news, VIX={market.get('vix_estimate')}, CAD/USD={market.get('cad_usd')}")
    return pulse


def _top_keywords(news: list) -> list:
    counts = {}
    for item in news:
        for kw in item.get("keywords", []):
            counts[kw] = counts.get(kw, 0) + 1
    sorted_kw = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [{"keyword": k, "count": v} for k, v in sorted_kw[:10]]


async def get_latest_pulse() -> dict:
    """Get the latest Global Pulse from cache (< 100ms)."""
    if "latest" in _pulse_cache:
        cached_at = _pulse_cache.get("cached_at")
        if cached_at and (datetime.now(timezone.utc) - cached_at).total_seconds() < 600:
            return _pulse_cache["latest"]

    db = _get_db()
    if db is not None:
        shadow = await db.global_pulse_shadow.find_one({"key": "latest"}, {"_id": 0})
        if shadow and shadow.get("data"):
            _pulse_cache["latest"] = shadow["data"]
            _pulse_cache["cached_at"] = datetime.now(timezone.utc)
            return shadow["data"]

    return await run_global_pulse()


# ═══════════════════════════════════════════════════════════════
# RECURSIVE BRAIN: Self-Learning Deltas (Delta Tracking Only)
# ═══════════════════════════════════════════════════════════════

async def compute_learning_delta() -> dict:
    """Compare yesterday's context data vs actual outcomes.
    Called at 00:00 UTC by background scheduler.
    Delta tracking only — no predictions."""
    db = _get_db()
    if db is None:
        return {"delta_computed": False}

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    # Get yesterday's context snapshot
    prediction = await db.forecast_shadow_cache.find_one(
        {"tenant_id": {"$exists": True}}, {"_id": 0}
    )

    actual_pulse = await db.global_pulse.find_one(
        {"scanned_at": {"$regex": f"^{yesterday}"}},
        {"_id": 0},
        sort=[("scanned_at", -1)],
    )

    if not prediction or not actual_pulse:
        return {"delta_computed": False, "reason": "insufficient data"}

    predicted_confidence = prediction.get("data", {}).get("summary", {}).get("confidence", "low")
    actual_keywords = [kw["keyword"] for kw in actual_pulse.get("top_keywords", [])]
    actual_vix = actual_pulse.get("market", {}).get("vix_estimate", VIX_FALLBACK)
    actual_sentiment = actual_pulse.get("market", {}).get("market_sentiment", "neutral")

    confidence_map = {"high": 0.8, "medium": 0.5, "low": 0.2}
    context_score = confidence_map.get(predicted_confidence, 0.3)

    if actual_sentiment in ("elevated_risk", "cautious") and context_score > 0.5:
        accuracy_delta = -0.15
    elif actual_sentiment == "stable" and context_score < 0.5:
        accuracy_delta = 0.1
    else:
        accuracy_delta = 0.0

    delta = {
        "date": yesterday,
        "context_confidence": predicted_confidence,
        "context_score": context_score,
        "actual_vix": actual_vix,
        "actual_sentiment": actual_sentiment,
        "actual_top_keywords": actual_keywords[:5],
        "accuracy_delta": accuracy_delta,
        "new_weight": round(max(0.1, min(0.95, context_score + accuracy_delta)), 4),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.learning_deltas.insert_one({**delta})

    # Write to learning_vault (internal calibration data, never exposed in UI)
    actual_cad = actual_pulse.get("market", {}).get("cad_usd")
    if actual_cad:
        vault_entry = {
            "tenant_id": "system",
            "date": yesterday,
            "indicator_type": "FXUSDCAD",
            "context_value_at_time": context_score,
            "actual_value_next_day": float(actual_cad) if actual_cad else None,
            "delta": accuracy_delta,
            "correlation_score": delta["new_weight"],
            "data_source": "Bank of Canada",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await db.learning_vault.insert_one(vault_entry)

    await db.oracle_weights.update_one(
        {"key": "context_confidence_weight"},
        {
            "$set": {
                "weight": delta["new_weight"],
                "last_delta": accuracy_delta,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            "$setOnInsert": {"key": "context_confidence_weight", "created_at": datetime.now(timezone.utc).isoformat()},
        },
        upsert=True,
    )

    logger.info(f"[RecursiveBrain] Delta computed: {accuracy_delta:+.2f} -> new weight: {delta['new_weight']}")
    return {"delta_computed": True, **delta}


# ═══════════════════════════════════════════════════════════════
# ORA LIVE REPORTER: Morning brief from Global Pulse
# ═══════════════════════════════════════════════════════════════

async def build_live_reporter_brief(tenant_id: str) -> str:
    """Build ORA's morning 'Live Reporter' brief combining global pulse + economic context."""
    pulse = await get_latest_pulse()
    market = pulse.get("market", {})
    news = pulse.get("news_items", [])
    top_kw = pulse.get("top_keywords", [])

    parts = ["Good morning. Here's your intelligence briefing:"]

    # Market overview (compliance-safe language)
    vix = market.get("vix_estimate", VIX_FALLBACK)
    sentiment = market.get("market_sentiment", "neutral")

    if sentiment == "elevated_risk":
        parts.append(f"Market Indicator: VIX at {vix} (elevated). Cautionary context noted for your 90-day outlook.")
    elif sentiment == "cautious":
        parts.append(f"Market Indicator: VIX at {vix} (slightly elevated). Markets are cautious today.")
    elif sentiment == "stable":
        parts.append(f"Market Indicator: VIX at {vix} (low volatility). Stable conditions for outreach.")
    else:
        parts.append(f"Market Indicator: VIX at {vix}. Markets are within normal range.")

    # Economic context injection (BoC data)
    econ_line = await build_economic_brief_line()
    if econ_line:
        parts.append(econ_line)

    # Top trending
    if top_kw:
        trending = ", ".join([f"{kw['keyword']} ({kw['count']})" for kw in top_kw[:3]])
        parts.append(f"Trending Industry Topics: {trending}")

    if news:
        for n in news[:2]:
            parts.append(f"- {n['title']}")

    # Oracle auto-actions
    try:
        from services.oracle_proactive import build_oracle_response
        oracle = await build_oracle_response(tenant_id)
        if oracle.get("auto_scout_triggered"):
            parts.append("Overnight data review: queued a new Proximity Blast to capture emerging interest.")
        if oracle.get("risk_alert"):
            parts.append(f"Risk Indicator: {oracle['risk_pct']}% of revenue shows risk. Consider defensive outreach.")
    except Exception:
        pass

    parts.append("\nEconomic data for business context only. Not investment advice.")

    return "\n\n".join(parts)
