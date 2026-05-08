"""
ORA Sovereign DB Oracle — Iter 288.1
=====================================
Founder-only universal database query layer.

Lets the founder ask ORA *anything* about the AUREM system in any language and
get a real answer pulled live from MongoDB. No fabrication, no fake numbers —
either the query hits real data or returns "not found".

Three tiers:
  1) FAST_LOOKUP   — direct collection lookups (BIN, user, lead, tenant)
  2) STRUCTURED    — pre-built reports (list_bins, list_websites, list_tenants…)
  3) NL_TO_QUERY   — LLM translates a free-form question to a Mongo find filter
                     (read-only, sandboxed: no $where, no aggregate stages that
                      mutate, hard 50-doc cap, hard collection allow-list)

Usage:
    from services.ora_db_oracle import (
        lookup_bin, lookup_user, list_bins, list_websites,
        list_tenants_full, db_query
    )
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Collections the oracle is allowed to read. Everything else is denied.
ALLOWED_COLLECTIONS = {
    "platform_users", "users", "tenants", "aurem_onboarding",
    "business_profiles", "ora_leads", "campaign_leads",
    "connector_connections", "tenant_connectors",
    "autopilot_runs", "agent_ledger_entries", "agent_rates",
    "agent_kill_switch_log", "agent_state",
    "subscription_plans", "service_registry",
    "alerts_digest_queue", "truth_logs",
    "ora_command_log",
}

# Fields that must NEVER be returned (PII / secrets)
REDACT_FIELDS = {
    "password", "password_hash", "secret", "api_key", "token", "stripe_secret",
    "twilio_auth_token", "telegram_bot_token", "anthropic_api_key", "openai_api_key",
}


def _redact(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(doc, dict):
        return doc
    out = {}
    for k, v in doc.items():
        if k.lower() in REDACT_FIELDS or any(s in k.lower() for s in ("password", "secret", "_key", "token")):
            out[k] = "****REDACTED****"
        elif isinstance(v, dict):
            out[k] = _redact(v)
        elif isinstance(v, list):
            out[k] = [_redact(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


# ─────────────────────────────────────────────────────────────
# TIER 1 — FAST LOOKUP
# ─────────────────────────────────────────────────────────────
async def lookup_bin(db, bin_code: str) -> Dict[str, Any]:
    """Lookup a Business ID across platform_users + users."""
    if db is None or not bin_code:
        return {"ok": False, "reply": "DB unavailable or empty BIN."}
    code = bin_code.strip().upper().replace(" ", "")

    # Try exact + normalized
    queries = [{"business_id": code}, {"bid": code}, {"business_code": code}]
    for q in queries:
        for col in ["platform_users", "users", "aurem_onboarding"]:
            try:
                doc = await db[col].find_one(q, {"_id": 0})
                if doc:
                    return _format_bin_hit(col, _redact(doc))
            except Exception:
                continue

    # Regex contains (suffix typo tolerance)
    rgx = re.escape(code.split("-")[0]) if "-" in code else re.escape(code)
    for col in ["platform_users", "users"]:
        try:
            cur = db[col].find({"business_id": {"$regex": rgx, "$options": "i"}},
                               {"_id": 0, "business_id": 1, "email": 1, "company_name": 1, "full_name": 1})
            cands = await cur.to_list(length=5)
            if cands:
                lines = [f"❌ *{code}* not found. Did you mean one of these?"]
                for c in cands:
                    lines.append(f"• `{c.get('business_id','?')}` — {c.get('company_name', c.get('email','?'))}")
                return {"ok": False, "reply": "\n".join(lines), "candidates": cands}
        except Exception:
            pass

    return {"ok": False, "reply": f"❌ BIN `{code}` does not exist in the database."}


def _format_bin_hit(col: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    bid = doc.get("business_id") or doc.get("bid") or "?"
    lines = [f"✅ *BIN {bid}* (in `{col}`)"]
    fields = [
        ("Email",       doc.get("email")),
        ("Company",     doc.get("company_name") or doc.get("company") or doc.get("business_name")),
        ("Owner",       doc.get("full_name") or " ".join(filter(None, [doc.get("first_name"), doc.get("last_name")]))),
        ("Phone",       doc.get("phone")),
        ("City",        doc.get("city")),
        ("Industry",    doc.get("industry")),
        ("Plan",        doc.get("plan")),
        ("Role",        doc.get("role")),
        ("Tenant ID",   doc.get("tenant_id")),
        ("Website",     doc.get("website")),
        ("Wizard done", doc.get("onboarding_wizard_complete")),
        ("Active",      doc.get("business_id_active")),
        ("Onboarded",   str(doc.get("smart_onboarded_at") or doc.get("created_at") or "—")[:19]),
        ("Last login",  str(doc.get("last_login") or "—")[:19]),
    ]
    for label, val in fields:
        if val not in (None, "", "—"):
            lines.append(f"• *{label}*: {val}")
    return {"ok": True, "reply": "\n".join(lines), "data": doc}


async def lookup_user(db, identifier: str) -> Dict[str, Any]:
    """Lookup user by email, name, or phone."""
    if db is None or not identifier:
        return {"ok": False, "reply": "DB unavailable or empty identifier."}
    ident = identifier.strip()
    rgx = re.escape(ident)
    pipe = {"$or": [
        {"email": {"$regex": rgx, "$options": "i"}},
        {"full_name": {"$regex": rgx, "$options": "i"}},
        {"first_name": {"$regex": rgx, "$options": "i"}},
        {"last_name": {"$regex": rgx, "$options": "i"}},
        {"company_name": {"$regex": rgx, "$options": "i"}},
        {"company": {"$regex": rgx, "$options": "i"}},
        {"phone": {"$regex": rgx, "$options": "i"}},
    ]}
    hits = []
    for col in ["platform_users", "users"]:
        try:
            cur = db[col].find(pipe, {"_id": 0}).limit(5)
            async for d in cur:
                hits.append((col, _redact(d)))
        except Exception:
            pass
    if not hits:
        return {"ok": False, "reply": f"❌ No user matches `{ident}`."}
    lines = [f"✅ *Found {len(hits)} match(es) for* `{ident}`"]
    for col, d in hits:
        lines.append(
            f"• `{d.get('business_id') or d.get('tenant_id','?')}` · {d.get('email','?')} · "
            f"{d.get('full_name') or d.get('company_name','—')} (in `{col}`)"
        )
    return {"ok": True, "reply": "\n".join(lines), "matches": hits}


# ─────────────────────────────────────────────────────────────
# TIER 2 — STRUCTURED REPORTS
# ─────────────────────────────────────────────────────────────
async def list_bins(db) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reply": "DB unavailable."}
    bins: List[Dict[str, Any]] = []
    try:
        cur = db.platform_users.find({}, {"_id": 0, "business_id": 1, "email": 1,
                                           "company_name": 1, "full_name": 1, "city": 1,
                                           "industry": 1, "plan": 1, "business_id_active": 1,
                                           "onboarding_wizard_complete": 1,
                                           "smart_onboarded_at": 1})
        async for d in cur:
            bins.append(d)
    except Exception as e:
        return {"ok": False, "reply": f"Fetch failed: {e}"}

    if not bins:
        return {"ok": True, "reply": "📋 No BINs in the database yet.", "bins": []}

    lines = [f"📋 *All BINs in AUREM* ({len(bins)})"]
    for b in bins:
        bid = b.get("business_id", "—")
        active = "🟢" if str(b.get("business_id_active")).lower() in ("true", "1") else "⚪"
        wiz = "✅" if str(b.get("onboarding_wizard_complete")).lower() in ("true", "1") else "⏳"
        company = b.get("company_name") or "(no company)"
        plan = b.get("plan") or "free"
        city = b.get("city") or "—"
        ind = b.get("industry") or "—"
        lines.append(f"{active}{wiz} `{bid}` — {company} · {plan} · {city}/{ind} · {b.get('email','?')}")
    return {"ok": True, "reply": "\n".join(lines), "bins": bins, "count": len(bins)}


async def list_websites(db) -> Dict[str, Any]:
    """List every website / domain linked to AUREM (across multiple sources)."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable."}
    sites: List[Dict[str, Any]] = []
    seen = set()

    sources = [
        ("platform_users",   {"website": {"$exists": True, "$ne": ""}},
                             ["business_id", "email", "company_name", "website"]),
        ("aurem_onboarding", {"website": {"$exists": True, "$ne": ""}},
                             ["tenant_id", "email", "company_name", "website", "platform_detected"]),
        ("business_profiles",{"website": {"$exists": True, "$ne": ""}},
                             ["tenant_id", "business_name", "website", "industry", "city"]),
        ("ora_leads",        {"website": {"$exists": True, "$ne": ""}},
                             ["business_id", "email", "full_name", "website", "city", "industry"]),
        ("campaign_leads",   {"website": {"$exists": True, "$ne": ""}},
                             ["lead_id", "email", "full_name", "website", "city", "industry", "sources"]),
    ]
    for col, query, proj in sources:
        try:
            cur = db[col].find(query, {"_id": 0, **{k: 1 for k in proj}}).limit(100)
            async for d in cur:
                w = (d.get("website") or "").strip().lower()
                if not w or w in ("none", "—", "null"):
                    continue
                key = re.sub(r"^https?://(www\.)?", "", w).rstrip("/")
                if key in seen:
                    continue
                seen.add(key)
                d["_source_collection"] = col
                sites.append(d)
        except Exception:
            continue

    if not sites:
        return {"ok": True, "reply": "🌐 No websites linked yet.", "sites": []}

    lines = [f"🌐 *All linked websites* ({len(sites)})"]
    for s in sites:
        owner = s.get("company_name") or s.get("business_name") or s.get("full_name") or s.get("email", "?")
        lines.append(f"• {s.get('website')} — {owner} (`{s.get('_source_collection')}`)")
    return {"ok": True, "reply": "\n".join(lines), "sites": sites, "count": len(sites)}


async def list_tenants_full(db) -> Dict[str, Any]:
    """Aggregate tenant intelligence: platform_users + business_profiles + leads_count."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable."}
    tenants: Dict[str, Dict[str, Any]] = {}
    try:
        async for u in db.users.find({}, {"_id": 0}):
            tid = u.get("tenant_id") or u.get("email", "—")
            tenants.setdefault(tid, {"tenant_id": tid, "users": []})["users"].append(_redact(u))
        async for p in db.platform_users.find({}, {"_id": 0}):
            tid = p.get("tenant_id") or p.get("business_id") or p.get("email", "—")
            t = tenants.setdefault(tid, {"tenant_id": tid, "users": []})
            t["business_id"] = p.get("business_id")
            t["company_name"] = p.get("company_name")
            t["plan"] = p.get("plan", "free")
            t["industry"] = p.get("industry")
            t["city"] = p.get("city")
        async for b in db.business_profiles.find({}, {"_id": 0}):
            tid = b.get("tenant_id")
            if tid in tenants:
                tenants[tid].setdefault("business_profile", {}).update(b)
    except Exception as e:
        return {"ok": False, "reply": f"Aggregate failed: {e}"}

    rows = list(tenants.values())
    rows.sort(key=lambda r: (r.get("plan") != "enterprise", r.get("company_name") or ""))

    lines = [f"🏢 *All Tenants* ({len(rows)})"]
    for r in rows:
        comp = r.get("company_name") or r.get("business_profile", {}).get("business_name") or r.get("tenant_id")
        plan = r.get("plan", "free")
        bid = r.get("business_id", "—")
        lines.append(f"• `{bid}` — {comp} · {plan} · {len(r.get('users', []))} user(s)")
    return {"ok": True, "reply": "\n".join(lines), "tenants": rows, "count": len(rows)}


# ─────────────────────────────────────────────────────────────
# TIER 3 — NL_TO_QUERY (LLM-translated MongoDB find)
# ─────────────────────────────────────────────────────────────
_DB_QUERY_PROMPT = """You are an AUREM database oracle. Translate a founder's
natural-language question (any language) into a SAFE read-only MongoDB query.

Return STRICT JSON only — no markdown, no prose:
{"collection": "<one of allowed>", "filter": {...}, "projection": {...optional...}, "limit": 25, "sort": [["field", -1]]}

Allowed collections: """ + ", ".join(sorted(ALLOWED_COLLECTIONS)) + """

Hard rules:
1. Read-only: filter MUST NOT contain $where, $function, $accumulator, $eval.
2. Limit ≤ 50. Default 25.
3. Always exclude _id (projection: {"_id": 0}) plus password-like fields.
4. Use case-insensitive regex for free-text matches: {"$regex": "...", "$options": "i"}.
5. If the user asks for a count, set limit=0 and add "count_only": true at top level.
6. If unsure which collection, pick the most likely one. If impossible, return {"error": "...short reason..."}.

Examples:
- "show me all enterprise users" → {"collection":"platform_users","filter":{"plan":"enterprise"},"projection":{"_id":0,"password_hash":0},"limit":25}
- "kitne leads aaye Toronto se" → {"collection":"campaign_leads","filter":{"city":{"$regex":"toronto","$options":"i"}},"limit":0,"count_only":true}
- "last 5 autopilot runs" → {"collection":"autopilot_runs","filter":{},"projection":{"_id":0},"limit":5,"sort":[["started_at",-1]]}
"""


async def db_query(db, question: str, max_docs: int = 25) -> Dict[str, Any]:
    """LLM-translated NL → MongoDB find. Read-only, sandboxed, founder-only."""
    if db is None:
        return {"ok": False, "reply": "DB unavailable."}
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return {"ok": False, "reply": "LLM key missing — cannot translate query."}

    try:
        import json as _json
        import uuid as _uuid
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        chat = LlmChat(api_key=api_key,
                       session_id=f"db_oracle_{_uuid.uuid4().hex[:6]}",
                       system_message=_DB_QUERY_PROMPT)
        chat.with_model("openai", "gpt-4o-mini")
        raw = (await chat.send_message(UserMessage(text=question))).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```\s*$", "", raw)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {"ok": False, "reply": "Could not parse query plan."}
        plan = _json.loads(m.group(0))
    except Exception as e:
        logger.warning(f"[ORACLE] LLM translate failed: {e}")
        return {"ok": False, "reply": f"Query translation failed: {e}"}

    if "error" in plan:
        return {"ok": False, "reply": f"❌ {plan['error']}"}

    col = plan.get("collection", "")
    if col not in ALLOWED_COLLECTIONS:
        return {"ok": False, "reply": f"❌ Collection `{col}` is not allowed."}

    filt = plan.get("filter", {}) or {}
    # Block dangerous operators
    blacklist = ("$where", "$function", "$accumulator", "$eval", "$expr")
    flat = _json_str = _json.dumps(filt) if 'json' in dir() else str(filt)
    import json as _j
    flat = _j.dumps(filt)
    for bad in blacklist:
        if bad in flat:
            return {"ok": False, "reply": f"❌ Query contains blocked operator `{bad}`."}

    proj = plan.get("projection") or {"_id": 0}
    proj["_id"] = 0
    for f in REDACT_FIELDS:
        proj[f] = 0
    limit = max(0, min(int(plan.get("limit") or 25), max_docs))
    sort = plan.get("sort") or []

    # Count-only mode
    if plan.get("count_only") or limit == 0:
        try:
            cnt = await db[col].count_documents(filt)
            return {"ok": True,
                    "reply": f"📊 *{col}* matching → *{cnt}* documents",
                    "plan": plan, "count": cnt}
        except Exception as e:
            return {"ok": False, "reply": f"Count failed: {e}"}

    try:
        cur = db[col].find(filt, proj)
        if sort:
            cur = cur.sort(sort)
        cur = cur.limit(limit)
        docs = await cur.to_list(length=limit)
    except Exception as e:
        return {"ok": False, "reply": f"Query failed: {e}"}

    docs = [_redact(d) for d in docs]
    if not docs:
        return {"ok": True, "reply": f"📭 No `{col}` documents match.", "plan": plan, "results": []}

    # Format compact preview
    lines = [f"📊 *{col}* — {len(docs)} result(s)"]
    for i, d in enumerate(docs[:10], 1):
        # Pick the 4-5 most informative fields
        preview_keys = [k for k in ("business_id", "email", "company_name", "full_name",
                                     "tenant_id", "name", "title", "status", "city",
                                     "industry", "plan", "stage", "amount_usd", "cost_usd",
                                     "agent_id", "started_at", "created_at", "timestamp",
                                     "lead_id", "phone", "website")
                         if k in d]
        snip = " · ".join(f"{k}={str(d[k])[:40]}" for k in preview_keys[:5])
        lines.append(f"{i}. {snip}")
    if len(docs) > 10:
        lines.append(f"… (+{len(docs) - 10} more)")
    return {"ok": True, "reply": "\n".join(lines), "plan": plan, "results": docs, "count": len(docs)}
