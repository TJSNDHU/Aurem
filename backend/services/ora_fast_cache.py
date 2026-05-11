"""
ORA Fast-Cache (voice short-circuit)
=====================================
Bypasses the full LLM call for trivial voice queries that have a known
authoritative answer. Cuts response latency from ~1.3s → <50ms.

Strategy:
- Pattern-match the user message against a small set of high-frequency
  voice queries (date, time, day, lead count, customer count).
- Return a templated answer pulled from live DB / wall-clock.
- Cache the templated answer for a short TTL so back-to-back asks are
  near-instant.

NOT a general LLM cache — only fires for *exact* known intents whose
answer is deterministic and can't hallucinate. Anything else falls
through to the normal chat pipeline.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# In-process TTL cache (survives requests, dies on pod restart).
_CACHE: dict = {}  # key → (answer, expires_at)


def _cache_get(key: str) -> Optional[str]:
    item = _CACHE.get(key)
    if not item:
        return None
    answer, exp = item
    if time.time() > exp:
        _CACHE.pop(key, None)
        return None
    return answer


def _cache_put(key: str, answer: str, ttl_s: int) -> None:
    _CACHE[key] = (answer, time.time() + ttl_s)


# ─── Intent patterns (compiled once) ──────────────────────────
# ── iter 322bn — BIN grounding (anti-hallucination, P0 Founder Override)
# When user asks about a BIN by its code (e.g. "AURE-XXXX" or "tell me
# about BIN PINX-K3JN"), do NOT let the LLM guess. Query db.platform_users
# (and db.users for admins) and return ONLY what the DB returns. If the
# BIN is missing → say "not found in our records".
_BIN_RX = re.compile(
    r"\b([A-Z]{3,5}-[A-Z0-9]{3,6})\b"
)


async def _ans_bin_lookup(bin_value: str) -> Optional[str]:
    """Deterministic BIN lookup. Returns a human reply or None."""
    bid = (bin_value or "").upper().strip()
    if not bid:
        return None
    try:
        import server
        db = getattr(server, "db", None)
        if db is None:
            return "I can't reach the customer database right now."
        # Try platform_users first (customers), then users (admins/founders)
        cust = await db.platform_users.find_one(
            {"business_id": bid},
            {"_id": 0, "email": 1, "first_name": 1, "company_name": 1,
             "business_name": 1, "plan": 1, "plan_label": 1, "role": 1,
             "created_at": 1},
        )
        if not cust:
            cust = await db.users.find_one(
                {"business_id": bid},
                {"_id": 0, "email": 1, "name": 1, "company_name": 1,
                 "business_name": 1, "plan": 1, "role": 1, "is_admin": 1},
            )
        if not cust:
            return f"BIN `{bid}` is not in our records. I will not guess — confirm the code or search by email instead."
        name = (cust.get("company_name") or cust.get("business_name")
                or cust.get("first_name") or cust.get("name") or "—")
        email = cust.get("email") or "—"
        plan = cust.get("plan_label") or cust.get("plan") or "—"
        is_admin = bool(cust.get("is_admin") or cust.get("role") in ("admin", "super_admin"))
        role_str = "Founder/Admin" if is_admin else "Customer"
        return (
            f"BIN `{bid}` → {name} · {email} · {role_str} · plan: {plan}. "
            f"(Source: db.{'users' if is_admin else 'platform_users'}, "
            "ground-truth — no LLM inference.)"
        )
    except Exception as e:
        logger.debug(f"[ora-fast] bin_lookup err: {e}")
        return "I can't reach the customer database right now."


# Date — bare "today / date / today's date / aaj / kya date" + "what's"
_DATE_RX = re.compile(
    r"^\s*(?:today|today'?s?\s+date|date|today\s+date|today\s+is|"
    r"current\s+date|what\s+is\s+today|what'?s\s+today|"
    r"what\s+is\s+the\s+date|what'?s\s+the\s+date|"
    r"what\s+is\s+today'?s?\s+date|what'?s\s+today'?s?\s+date|"
    r"aaj|aaj\s+kya\s+(?:hai|date|din)|kya\s+date\s+hai|"
    r"date\s+today|tell\s+me\s+(?:the\s+)?(?:today'?s?\s+)?date)"
    r"\s*\??\s*$",
    re.IGNORECASE,
)

# Time — "time / what time / kitne baje / samay"
_TIME_RX = re.compile(
    r"^\s*(?:time|current\s+time|what\s+time(?:\s+is\s+it)?|"
    r"what'?s\s+the\s+time|tell\s+me\s+(?:the\s+)?time|"
    r"kya\s+time\s+hai|samay|kitne\s+baje)"
    r"\s*\??\s*$",
    re.IGNORECASE,
)

_LEADS_RX = re.compile(
    r"^\s*(?:how\s+many\s+leads?|leads?\s+count|count\s+of\s+leads?|"
    r"total\s+leads?|leads?\s+today|how\s+many\s+leads?\s+today)"
    r"\s*\??\s*$",
    re.IGNORECASE,
)

_CUSTOMERS_RX = re.compile(
    r"^\s*(?:how\s+many\s+(?:customers?|tenants?|clients?)(?:\s+(?:are\s+)?(?:healthy|active|signed\s+up|on\s+the\s+platform))?|"
    r"customers?\s+count|tenants?\s+count|"
    r"(?:total\s+)?customers?\s+(?:total|active|healthy)?|"
    r"customer\s+health(?:\s+status)?|how\s+is\s+everyone|"
    r"how\s+are\s+(?:my\s+)?customers?(?:\s+doing)?|"
    r"any\s+customers?\s+(?:in\s+)?critical|critical\s+customers?)"
    r"\s*\??\s*$",
    re.IGNORECASE,
)


# ─── Answer builders (pull live data, no LLM) ─────────────────
def _ans_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        now = datetime.now(ZoneInfo("America/Toronto"))
        return f"Today is {now.strftime('%A, %B %d, %Y')}."
    except Exception:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return f"Today is {now.strftime('%A, %B %d, %Y')} UTC."


def _ans_time() -> str:
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        now = datetime.now(ZoneInfo("America/Toronto"))
        return f"It's {now.strftime('%-I:%M %p')} Toronto time."
    except Exception:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return f"It's {now.strftime('%-I:%M %p')} UTC."


async def _ans_leads_count() -> str:
    cached = _cache_get("ora_fast:leads_count")
    if cached:
        return cached
    try:
        import server
        db = getattr(server, "db", None)
        if db is None:
            return "I can't reach the lead database right now."
        total = await db.leads.count_documents({})
        from datetime import datetime, timezone, timedelta
        since = datetime.now(timezone.utc) - timedelta(days=1)
        today = await db.leads.count_documents(
            {"created_at": {"$gte": since.isoformat()}}
        )
        ans = (f"You have {total} total leads, {today} added in the last 24 hours."
               if today else f"You have {total} total leads.")
    except Exception as e:
        logger.debug(f"[ora-fast] leads_count err: {e}")
        return "I can't pull the lead count right now."
    _cache_put("ora_fast:leads_count", ans, 30)
    return ans


async def _ans_customers_health() -> str:
    cached = _cache_get("ora_fast:customers_health")
    if cached:
        return cached
    try:
        import server
        db = getattr(server, "db", None)
        if db is None:
            return "I can't reach the customer database right now."
        summary = await db.customer_health_summary.find_one(
            {"_id": "latest"}, {"_id": 0}
        )
        if not summary:
            return "I haven't run the customer health scan yet today."
        c = summary.get("counts", {}) or {}
        h, d, cr = c.get("healthy", 0), c.get("degraded", 0), c.get("critical", 0)
        if cr > 0:
            ans = (f"Heads up — {cr} customer{'s' if cr != 1 else ''} in critical, "
                   f"{d} degraded, {h} healthy.")
        elif d > 0:
            ans = (f"{h} customers healthy, {d} degraded, none critical.")
        else:
            ans = f"All {h} customers are healthy."
    except Exception as e:
        logger.debug(f"[ora-fast] customers_health err: {e}")
        return "I can't pull customer health right now."
    _cache_put("ora_fast:customers_health", ans, 30)
    return ans


# ─── Public entry point ───────────────────────────────────────

async def try_short_circuit(message: str) -> Optional[str]:
    """If the message matches a known fast-path intent, return the
    templated answer. Otherwise return None and let normal chat run."""
    if not message:
        return None
    msg = message.strip()

    # iter 322bn — BIN grounding (anti-hallucination). Matches any BIN-like
    # code anywhere in the message. Bypasses length limit because users
    # naturally write "Tell me about BIN PINX-K3JN, who owns it?"
    bin_match = _BIN_RX.search(msg)
    if bin_match:
        ans = await _ans_bin_lookup(bin_match.group(1))
        if ans is not None:
            return ans

    if len(msg) > 80:
        return None  # only short voice phrases short-circuit

    if _TIME_RX.search(msg):
        return _ans_time()
    if _DATE_RX.search(msg):
        return _ans_date()
    if _LEADS_RX.search(msg):
        return await _ans_leads_count()
    if _CUSTOMERS_RX.search(msg):
        return await _ans_customers_health()
    return None


def cache_size() -> int:
    return len(_CACHE)
