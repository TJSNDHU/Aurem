"""
Founders Console — Business Action Dispatcher.

When `preprocess_input` classifies the founder's message as a BUSINESS
intent (SCOUT, STATUS, LEADS, PAUSE, BLAST), the Founders Console used to
push it through Council → multi-model race → code-edit. That is wrong for
ops actions.

This module short-circuits non-BUILD intents and fires the actual existing
gated endpoints, returning a real result for the chat surface.

Action keys — keep names in sync with INTENT_KEYWORDS in
services/founders_pipeline.py:
    SCOUT, BLAST, PAUSE, STATUS, LEADS

Each handler returns:
  { "ok": bool, "summary": str, "data": {...}, "intent": "<INTENT>" }
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Intents that should bypass the code-build pipeline.
ACTION_INTENTS = {"SCOUT", "BLAST", "PAUSE", "STATUS", "LEADS"}


# ─── Parsers ───────────────────────────────────────────────────────────
_CITY_HINTS = (
    "in ", "for ", "near ", "around ", "from ",
    "ke liye ", "me ", "mein ", "ka ",
)
_CANADIAN_CITIES = (
    "mississauga", "toronto", "brampton", "ottawa", "vancouver",
    "calgary", "edmonton", "montreal", "halifax", "winnipeg",
    "burlington", "oakville", "hamilton", "kitchener", "london",
)
_INDUSTRY_HINTS = (
    "plumb", "auto", "dentist", "salon", "barber", "lawyer",
    "accountant", "electrician", "hvac", "cleaner", "landscap",
    "roof", "spa", "yoga", "cafe", "restaurant", "bakery",
    "real estate", "realtor", "fitness", "tattoo", "florist",
    "pharmacy", "clinic", "vet", "garage", "mechanic",
)


def _extract_city(text: str) -> str:
    low = text.lower()
    for c in _CANADIAN_CITIES:
        if c in low:
            return c.title()
    # "scout in <X>"
    m = re.search(r"\b(?:in|for|near|around|from)\s+([A-Za-z][A-Za-z\s-]{2,30})$", text)
    if m:
        return m.group(1).strip().title()
    return ""


def _extract_industry(text: str) -> str:
    low = text.lower()
    for kw in _INDUSTRY_HINTS:
        if kw in low:
            # Pull the surrounding token (e.g. "auto-repair", "plumbers")
            m = re.search(r"\b([a-z]*" + kw + r"[a-z\- ]*)\b", low)
            if m:
                return m.group(1).strip(" -")
    return ""


def _extract_count(text: str) -> int:
    m = re.search(r"\b(\d{1,3})\b", text)
    return int(m.group(1)) if m else 10


# ─── Handlers ──────────────────────────────────────────────────────────
async def _h_scout(message: str, db) -> Dict[str, Any]:
    industry = _extract_industry(message)
    city = _extract_city(message)
    query = (industry + " " + city).strip() or message
    try:
        from services.business_scout import scout_business
        result = await scout_business(query, city)
    except Exception as e:
        logger.warning(f"[founders-action SCOUT] scout_business failed: {e}")
        return {
            "ok": False,
            "intent": "SCOUT",
            "summary": f"Scout couldn't run: {e}",
            "data": {"query": query, "city": city, "error": str(e)},
        }
    found = bool(result and result.get("name"))
    name = (result or {}).get("name") if found else None
    sources = (result or {}).get("sources_tried") or []
    summary = (
        f"Found '{name}' in {city or 'auto-detected location'} "
        f"(sources tried: {', '.join(sources) or 'all'})."
        if found else
        f"No business match for '{query}' yet — "
        f"tried: {', '.join(sources) or 'all sources'}. "
        "Try a more specific name or check the Google/Tavily keys."
    )
    return {"ok": found, "intent": "SCOUT", "summary": summary,
            "data": {"query": query, "city": city, "result": result}}


async def _h_status(message: str, db) -> Dict[str, Any]:
    """Real database counts — no LLM."""
    out: Dict[str, Any] = {}
    try:
        out["leads"] = await db.campaign_leads.count_documents(
            {"business_id": FOUNDER_BIN})
    except Exception:
        out["leads"] = 0
    try:
        out["leads_today"] = await db.campaign_leads.count_documents(
            {"created_at": {"$gte": _today_start()}, "business_id": FOUNDER_BIN}
        )
    except Exception:
        out["leads_today"] = 0
    try:
        out["campaigns"] = await db.campaigns.count_documents({})
    except Exception:
        out["campaigns"] = 0
    try:
        out["council_decisions"] = await db.council_decisions.count_documents({})
    except Exception:
        out["council_decisions"] = 0
    try:
        out["customers"] = await db.platform_users.count_documents({"is_active": True})
    except Exception:
        out["customers"] = 0
    try:
        out["unified_profiles"] = await db.bin_unified_profiles.count_documents({})
    except Exception:
        out["unified_profiles"] = 0
    summary = (
        f"📊 STATUS — {out['leads']} total leads ({out['leads_today']} today) · "
        f"{out['campaigns']} campaigns · "
        f"{out['council_decisions']} council decisions · "
        f"{out['customers']} active customers · "
        f"{out['unified_profiles']} matched intel profiles."
    )
    return {"ok": True, "intent": "STATUS", "summary": summary, "data": out}


async def _h_leads(message: str, db) -> Dict[str, Any]:
    """Lead pipeline by stage."""
    stages = ["discovered", "contacted", "responded", "qualified", "won"]
    counts: Dict[str, int] = {}
    for s in stages:
        try:
            counts[s] = await db.campaign_leads.count_documents(
                {"lifecycle_stage": s, "business_id": FOUNDER_BIN})
        except Exception:
            counts[s] = 0
    total = sum(counts.values())
    summary = (
        "📈 LEADS PIPELINE — " +
        " · ".join(f"{s}:{counts[s]}" for s in stages) +
        f" · TOTAL:{total}"
    )
    return {"ok": True, "intent": "LEADS", "summary": summary, "data": counts}


async def _h_blast(message: str, db) -> Dict[str, Any]:
    """Quick proximity blast count — actually running the blast needs lat/lng
    that the chat input doesn't have. Return a guarded preview that tells
    the founder exactly what's needed to fire.
    """
    target = _extract_count(message)
    city = _extract_city(message)
    return {
        "ok": True,
        "intent": "BLAST",
        "summary": (
            f"Blast staged — target {target} leads"
            + (f" near {city}" if city else "")
            + ". To fire, hit /api/blast (needs lat/lng) "
              "or open the Proximity Blast UI."
        ),
        "data": {"target_count": target, "city": city,
                  "fire_endpoint": "/api/blast"},
    }


async def _h_pause(message: str, db) -> Dict[str, Any]:
    """Pause all active campaigns for the founder's BIN."""
    try:
        res = await db.campaigns.update_many(
            {"status": {"$in": ["active", "running"]}},
            {"$set": {"status": "paused", "paused_at": _now()}},
        )
        return {
            "ok": True, "intent": "PAUSE",
            "summary": f"⏸ Paused {res.modified_count} active campaigns.",
            "data": {"modified": res.modified_count},
        }
    except Exception as e:
        return {"ok": False, "intent": "PAUSE",
                "summary": f"Pause failed: {e}", "data": {"error": str(e)}}


HANDLERS = {
    "SCOUT": _h_scout, "STATUS": _h_status, "LEADS": _h_leads,
    "BLAST": _h_blast, "PAUSE": _h_pause,
}


# ─── Public entry ──────────────────────────────────────────────────────
async def maybe_dispatch_action(task: Dict[str, Any], db) -> Optional[Dict[str, Any]]:
    """If task's intent is in ACTION_INTENTS, run the handler and return
    its result. Otherwise return None and the caller falls through to the
    code-build pipeline.
    """
    intent = (task or {}).get("intent") or ""
    if intent not in ACTION_INTENTS or db is None:
        return None
    h = HANDLERS.get(intent)
    if not h:
        return None
    try:
        return await h(task.get("raw_input") or task.get("description") or "", db)
    except Exception as e:
        logger.warning(f"[founders-action] handler {intent} crashed: {e}")
        return {
            "ok": False, "intent": intent,
            "summary": f"Action {intent} failed: {e}", "data": {"error": str(e)},
        }


# ─── Helpers ───────────────────────────────────────────────────────────
def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _today_start():
    from datetime import datetime, timezone
    n = datetime.now(timezone.utc)
    return n.replace(hour=0, minute=0, second=0, microsecond=0)
