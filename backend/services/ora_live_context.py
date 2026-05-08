"""
ORA Live Context Service
========================
Single async function: get_live_context(tenant_id)
- asyncio.gather for ALL fetches — parallel only
- Redis cache: weather (10 min), session context (60s)
- Max 400 tokens total context (600 for text chat)
- Per-field freshness timestamps ("leads_as_of: 2 min ago")
- 80ms hard timeout — proceed without context if slow
- Never crash the whole context build on any single fetch failure
"""

import os
import asyncio
import logging
import time
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# REDIS CACHE
# ═══════════════════════════════════════

_redis = None


def _get_redis():
    """Return the shared sync Redis client from the global pool."""
    try:
        from utils.redis_pool import get_sync_redis
        return get_sync_redis()
    except Exception:
        return None


def _redis_get(key: str) -> Optional[str]:
    try:
        r = _get_redis()
        if r:
            return r.get(key)
    except Exception:
        pass
    return None


def _redis_set(key: str, value: str, ttl: int):
    try:
        r = _get_redis()
        if r:
            r.setex(key, ttl, value)
    except Exception:
        pass


def _redis_delete_pattern(pattern: str):
    try:
        r = _get_redis()
        if r:
            for k in r.scan_iter(match=pattern):
                r.delete(k)
    except Exception:
        pass


def invalidate_tenant_cache(tenant_id: str):
    """Call when new lead/invoice/activity happens for a tenant."""
    _redis_delete_pattern(f"ctx:{tenant_id}*")


def invalidate_session_cache(session_id: str):
    _redis_delete_pattern(f"session:{session_id}")


# ═══════════════════════════════════════
# WEATHER — Redis "weather:mississauga" TTL 600s
# ═══════════════════════════════════════

OPENWEATHERMAP_KEY = ""
DEFAULT_CITY = "Mississauga,CA"
WEATHER_TTL = 600  # 10 minutes


def _get_weather_key():
    """Read weather key dynamically — handles late .env loading."""
    global OPENWEATHERMAP_KEY
    if not OPENWEATHERMAP_KEY:
        OPENWEATHERMAP_KEY = os.environ.get("OPENWEATHERMAP_API_KEY", "")
        # Also try loading from dotenv directly
        if not OPENWEATHERMAP_KEY:
            try:
                with open(os.path.join(os.path.dirname(__file__), "..", ".env")) as f:
                    for line in f:
                        if line.startswith("OPENWEATHERMAP_API_KEY="):
                            OPENWEATHERMAP_KEY = line.strip().split("=", 1)[1].strip('"').strip("'")
                            break
            except Exception:
                pass
    return OPENWEATHERMAP_KEY


async def _fetch_weather(city: str = DEFAULT_CITY) -> Dict[str, Any]:
    """Fetch weather, return dict with data + timestamp."""
    cache_key = f"weather:{city.split(',')[0].lower()}"
    cached = _redis_get(cache_key)
    if cached:
        try:
            data = json.loads(cached)
            return data
        except Exception:
            pass

    key = _get_weather_key()
    if not key:
        # Fallback: Open-Meteo (free, no key needed)
        try:
            from services.free_api_arsenal import get_weather as free_weather
            w = await free_weather(43.59, -79.65, city.split(",")[0])
            if w.get("temp_c") is not None:
                result = {
                    "text": f"Weather ({w['city']}): {w['temp_c']}°C, {w.get('condition','')}, Humidity: {w.get('humidity','')}%, Wind: {w.get('wind_kph','')} km/h",
                    "as_of": datetime.now(timezone.utc).isoformat(),
                    "fetched_at": time.time(),
                    "source": "open-meteo (free)",
                }
                _redis_set(cache_key, json.dumps(result), WEATHER_TTL)
                return result
        except Exception:
            pass
        return {"text": "Weather data: unavailable", "as_of": "N/A"}

    # Open-Meteo is primary even when OWM key exists
    try:
        from services.free_api_arsenal import get_weather as free_weather
        w = await free_weather(43.59, -79.65, city.split(",")[0])
        if w.get("temp_c") is not None:
            result = {
                "text": f"Weather ({w['city']}): {w['temp_c']}°C, {w.get('condition','')}, Humidity: {w.get('humidity','')}%, Wind: {w.get('wind_kph','')} km/h",
                "as_of": datetime.now(timezone.utc).isoformat(),
                "fetched_at": time.time(),
                "source": "open-meteo (free)",
            }
            _redis_set(cache_key, json.dumps(result), WEATHER_TTL)
            return result
    except Exception as e:
        logger.warning(f"[LiveContext] Weather fetch error: {e}")

    return {"text": "Weather: temporarily unavailable", "as_of": "N/A"}


# ═══════════════════════════════════════
# BUSINESS DATA FROM MONGODB
# ═══════════════════════════════════════

async def _fetch_leads(db, tenant_id: str) -> Dict[str, Any]:
    """Active leads count + top lead."""
    try:
        if db is None:
            return {"count": 0, "today": 0, "top_name": None, "top_score": None, "as_of": "N/A"}

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        count = await db.ora_leads.count_documents({})
        today_count = await db.ora_leads.count_documents({"created_at": {"$gte": today_start.isoformat()}})

        top_lead = None
        cursor = db.ora_leads.find({}, {"_id": 0, "full_name": 1, "email": 1, "lead_score": 1}).sort("lead_score", -1).limit(1)
        async for doc in cursor:
            top_lead = doc

        return {
            "count": count,
            "today": today_count,
            "top_name": top_lead.get("full_name", top_lead.get("email", "Unknown")) if top_lead else None,
            "top_score": top_lead.get("lead_score") if top_lead else None,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.warning(f"[LiveContext] Leads fetch error: {e}")
        return {"count": 0, "today": 0, "top_name": None, "top_score": None, "as_of": "N/A"}


async def _fetch_revenue(db, tenant_id: str) -> Dict[str, Any]:
    """Revenue snapshot."""
    try:
        if db is None:
            return {"mrr": 0, "pipeline": 0, "as_of": "N/A"}

        biz = await db.business_metrics.find_one({}, {"_id": 0, "mrr": 1, "pipeline_value": 1, "revenue_this_month": 1})
        if biz:
            return {
                "mrr": biz.get("mrr", biz.get("revenue_this_month", 0)),
                "pipeline": biz.get("pipeline_value", 0),
                "as_of": datetime.now(timezone.utc).isoformat(),
            }
        return {"mrr": 0, "pipeline": 0, "as_of": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.warning(f"[LiveContext] Revenue fetch error: {e}")
        return {"mrr": 0, "pipeline": 0, "as_of": "N/A"}


async def _fetch_last_interaction(db, tenant_id: str) -> Dict[str, Any]:
    """Last customer interaction."""
    try:
        if db is None:
            return {"text": "No recent activity", "as_of": "N/A"}

        last = await db.aurem_voice_calls.find_one(
            {"status": {"$in": ["ended", "connected"]}},
            {"_id": 0, "created_at": 1, "status": 1},
        )
        if last and last.get("created_at"):
            ts = last["created_at"]
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            return {"text": f"Last interaction: {ts_str}", "as_of": datetime.now(timezone.utc).isoformat()}
        return {"text": "No recent customer interactions", "as_of": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        logger.warning(f"[LiveContext] Last interaction error: {e}")
        return {"text": "No recent activity", "as_of": "N/A"}


async def _fetch_knowledge_sync(db) -> Dict[str, Any]:
    """Knowledge sync status."""
    try:
        if db is None:
            return {"synced_at": "never", "docs_count": 0}

        sync_doc = await db.ora_knowledge_sync.find_one(
            {}, {"_id": 0, "synced_at": 1, "docs_count": 1},
        )
        if sync_doc:
            return {
                "synced_at": sync_doc.get("synced_at", "unknown"),
                "docs_count": sync_doc.get("docs_count", 0),
            }
        return {"synced_at": "never", "docs_count": 0}
    except Exception:
        return {"synced_at": "unknown", "docs_count": 0}


# ═══════════════════════════════════════
# WEB SEARCH TOOL (SmartSearch)
# ═══════════════════════════════════════

SEARCH_TRIGGER_KEYWORDS = [
    "latest", "today", "current", "right now",
    "trending", "news", "price", "rate", "update",
    "instagram", "tiktok", "competitor", "market",
    "happened", "recently", "this week", "2026",
]


def needs_web_search(user_text: str) -> bool:
    lower = user_text.lower()
    return any(kw in lower for kw in SEARCH_TRIGGER_KEYWORDS)


async def _web_search(db, query: str) -> str:
    """Execute web search using existing SmartSearch service. Max 1500 chars."""
    try:
        from services.smart_search import get_smart_search, set_smart_search_db
        if db is not None:
            set_smart_search_db(db)
        searcher = get_smart_search()
        result = await searcher.search(query=query, limit=5)
        if result and result.get("results"):
            lines = []
            for r in result["results"][:5]:
                title = r.get("title", "")
                snippet = r.get("snippet", r.get("description", ""))
                if title and snippet:
                    lines.append(f"- {title}: {snippet}")
                elif title:
                    lines.append(f"- {title}")
            if lines:
                return "[WEB SEARCH RESULTS]\n" + "\n".join(lines)[:1500]
        return ""
    except Exception as e:
        logger.warning(f"[LiveContext] Web search error: {e}")
        return ""


# ═══════════════════════════════════════
# FRESHNESS HELPERS
# ═══════════════════════════════════════

def _ago_string(iso_str: str) -> str:
    """Convert ISO timestamp to '2 min ago' style string."""
    if not iso_str or iso_str == "N/A":
        return "unavailable"
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - ts
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        elif secs < 3600:
            return f"{secs // 60} min ago"
        elif secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return "recently"


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


# ═══════════════════════════════════════
# MASTER CONTEXT BUILDER
# ═══════════════════════════════════════

async def get_live_context(
    db,
    tenant_id: str = "aurem_platform",
    user_message: str = "",
    tz_offset: int = 0,
    max_tokens: int = 400,
) -> Dict[str, Any]:
    """
    Single function — gathers ALL live data via asyncio.gather.
    Returns dict with 'context_string' and 'metadata'.

    - Redis session cache: 60s per tenant
    - 80ms hard timeout — proceed without on slow fetch
    - Max 400 tokens (voice) / 600 tokens (text chat)
    - Per-field freshness timestamps
    """
    utc_now = datetime.now(timezone.utc)
    local_now = utc_now - timedelta(minutes=int(tz_offset))
    date_str = local_now.strftime("%A, %B %d, %Y")
    time_str = local_now.strftime("%-I:%M %p")
    iso_str = utc_now.isoformat()

    do_search = needs_web_search(user_message)

    # Check Redis session cache (skip web search queries — those are per-message)
    if not do_search:
        cache_key = f"ctx:{tenant_id}"
        cached = _redis_get(cache_key)
        if cached:
            try:
                ctx = json.loads(cached)
                # Update datetime (zero cost)
                ctx["datetime"] = {"date": date_str, "time": time_str, "iso": iso_str}
                ctx["context_string"] = _build_context_string(ctx, date_str, time_str, max_tokens)
                ctx["from_cache"] = True
                return ctx
            except Exception:
                pass

    # Parallel fetch with 80ms hard timeout
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                _fetch_weather(),
                _fetch_leads(db, tenant_id),
                _fetch_revenue(db, tenant_id),
                _fetch_last_interaction(db, tenant_id),
                _fetch_knowledge_sync(db),
                return_exceptions=True,
            ),
            timeout=0.08,  # 80ms hard limit
        )
    except asyncio.TimeoutError:
        logger.warning("[LiveContext] Context fetch exceeded 80ms — proceeding with minimal context")
        # Schedule async fetch for next message
        asyncio.create_task(_warm_cache(db, tenant_id))
        results = [
            {"text": "Weather: loading...", "as_of": "N/A"},
            {"count": 0, "today": 0, "top_name": None, "top_score": None, "as_of": "N/A"},
            {"mrr": 0, "pipeline": 0, "as_of": "N/A"},
            {"text": "Activity: loading...", "as_of": "N/A"},
            {"synced_at": "unknown", "docs_count": 0},
        ]

    # Safe unpack — each result could be an Exception
    weather = results[0] if not isinstance(results[0], Exception) else {"text": "Weather: error", "as_of": "N/A"}
    leads = results[1] if not isinstance(results[1], Exception) else {"count": 0, "today": 0, "top_name": None, "top_score": None, "as_of": "N/A"}
    revenue = results[2] if not isinstance(results[2], Exception) else {"mrr": 0, "pipeline": 0, "as_of": "N/A"}
    activity = results[3] if not isinstance(results[3], Exception) else {"text": "No recent activity", "as_of": "N/A"}
    knowledge = results[4] if not isinstance(results[4], Exception) else {"synced_at": "unknown", "docs_count": 0}

    # Web search (only if triggered — runs outside the 80ms gate)
    web_search_text = ""
    if do_search:
        try:
            web_search_text = await asyncio.wait_for(_web_search(db, user_message), timeout=3.0)
        except asyncio.TimeoutError:
            web_search_text = "[WEB SEARCH] Timed out"

    # Build sources list
    sources = []
    if weather.get("as_of") != "N/A":
        sources.append("live_weather")
    if leads.get("count", 0) > 0:
        sources.append("mongodb_leads")
    if revenue.get("mrr", 0) > 0 or revenue.get("pipeline", 0) > 0:
        sources.append("mongodb_revenue")
    if web_search_text:
        sources.append("web_search")

    ctx = {
        "weather": weather,
        "leads": leads,
        "revenue": revenue,
        "activity": activity,
        "knowledge": knowledge,
        "web_search": web_search_text,
        "datetime": {"date": date_str, "time": time_str, "iso": iso_str},
        "sources": sources,
        "from_cache": False,
    }

    ctx["context_string"] = _build_context_string(ctx, date_str, time_str, max_tokens)

    # Cache in Redis (60s, excluding per-query web search)
    try:
        cache_copy = {k: v for k, v in ctx.items() if k not in ("web_search", "context_string", "from_cache")}
        _redis_set(f"ctx:{tenant_id}", json.dumps(cache_copy, default=str), 60)
    except Exception:
        pass

    return ctx


async def _warm_cache(db, tenant_id: str):
    """Background task to warm the cache after a timeout miss."""
    try:
        results = await asyncio.gather(
            _fetch_weather(),
            _fetch_leads(db, tenant_id),
            _fetch_revenue(db, tenant_id),
            _fetch_last_interaction(db, tenant_id),
            _fetch_knowledge_sync(db),
            return_exceptions=True,
        )
        cache_data = {
            "weather": results[0] if not isinstance(results[0], Exception) else {"text": "Weather: error", "as_of": "N/A"},
            "leads": results[1] if not isinstance(results[1], Exception) else {"count": 0, "today": 0, "top_name": None, "top_score": None, "as_of": "N/A"},
            "revenue": results[2] if not isinstance(results[2], Exception) else {"mrr": 0, "pipeline": 0, "as_of": "N/A"},
            "activity": results[3] if not isinstance(results[3], Exception) else {"text": "No recent activity", "as_of": "N/A"},
            "knowledge": results[4] if not isinstance(results[4], Exception) else {"synced_at": "unknown", "docs_count": 0},
            "sources": [],
        }
        _redis_set(f"ctx:{tenant_id}", json.dumps(cache_data, default=str), 60)
        logger.info(f"[LiveContext] Cache warmed for {tenant_id}")
    except Exception as e:
        logger.warning(f"[LiveContext] Cache warm failed: {e}")


def _build_context_string(ctx: Dict[str, Any], date_str: str, time_str: str, max_tokens: int = 400) -> str:
    """Build dense context string. Token-optimized format (Strategy 1)."""
    parts = [f"\n[CTX {time_str}]"]

    # Weather — dense format
    weather = ctx.get("weather", {})
    w_text = weather.get("text", "") if isinstance(weather, dict) else str(weather)
    if w_text and "not configured" not in w_text and "error" not in w_text:
        # Extract key data from verbose weather text
        parts.append(f"wx:{w_text[:60]}")

    # Leads — dense format
    leads = ctx.get("leads", {})
    if leads.get("count", 0) > 0:
        top = f",top:{leads['top_name']}/{leads.get('top_score','?')}" if leads.get("top_name") else ""
        parts.append(f"leads:{leads['count']},new:{leads.get('today',0)}{top}")

    # Revenue — dense format
    revenue = ctx.get("revenue", {})
    mrr = revenue.get("mrr", 0)
    pipeline = revenue.get("pipeline", 0)
    if mrr > 0 or pipeline > 0:
        parts.append(f"mrr:${mrr:,.0f},pipe:${pipeline:,.0f}")

    # Activity — truncated
    activity = ctx.get("activity", {})
    a_text = activity.get("text", "") if isinstance(activity, dict) else str(activity)
    if a_text and "no recent" not in a_text.lower():
        parts.append(f"last:{a_text[:50]}")

    # Knowledge sync
    knowledge = ctx.get("knowledge", {})
    if knowledge.get("docs_count", 0) > 0:
        parts.append(f"kb:{knowledge['docs_count']}docs")

    result = "|".join(parts)
    # Hard cap at max_tokens * 4 chars
    return result[:max_tokens * 4]


# ═══════════════════════════════════════
# METADATA FOR CHAT RESPONSES (Fix 4)
# ═══════════════════════════════════════

def build_freshness_metadata(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Append to every ORA response — shows data sources and freshness."""
    weather = ctx.get("weather", {})
    leads = ctx.get("leads", {})

    weather_age = _ago_string(weather.get("as_of", "N/A")) if isinstance(weather, dict) else "N/A"
    leads_age = _ago_string(leads.get("as_of", "N/A")) if isinstance(leads, dict) else "N/A"

    knowledge = ctx.get("knowledge", {})
    synced = knowledge.get("synced_at", "unknown") if isinstance(knowledge, dict) else "unknown"

    # Calculate context age
    ctx_time = ctx.get("datetime", {}).get("iso", "")
    context_age = _ago_string(ctx_time) if ctx_time else "unknown"

    return {
        "data_freshness": f"Live \u2014 pulled {ctx.get('datetime', {}).get('time', 'now')}",
        "context_age": f"< {context_age}" if context_age != "unknown" else "< 60 seconds",
        "weather_as_of": weather_age,
        "leads_as_of": leads_age,
        "knowledge_sync": synced,
        "sources": ctx.get("sources", []),
        "web_searched": bool(ctx.get("web_search", "")),
        "cached": ctx.get("from_cache", False),
    }
