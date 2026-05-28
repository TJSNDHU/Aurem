"""
routers/cto_tools_router.py — iter D-49

Real tool-execution surface for the AUREM CTO chat. The CTO no longer
only "plans" — it can now actually run a Ghost Scout cycle, import a
CSV/list of leads, kick auto-blast, and pull live DB stats.

Endpoints (founder/admin only — same `_current_dev` admin-bypass as
the rest of the developer portal):

  POST /api/developers/cto/tools/run-scout
        body: {"city": str, "category": str, "count": int (1..50),
               "country": "ca"|"us" (default ca)}
        → harvests one batch via OSM/Places, inserts into campaign_leads

  POST /api/developers/cto/tools/import-leads
        body: {"leads": [{"business_name":..., "email":..., "phone":...,
                          "city":..., "country":...}]}
        → upserts each into campaign_leads with channel-gating pre-seeded

  POST /api/developers/cto/tools/run-blast
        body: {"tenant_id": str (default "global"), "force": bool}
        → triggers one auto_blast_engine cycle synchronously, returns
          processed/sent counts

  GET  /api/developers/cto/tools/db-stats
        → live counts: campaign_leads, fresh, emailed, sent_emails_today,
          customers, recent_blast runs.

Design notes
------------
- Pure FastAPI, no Emergent imports.
- Each tool wraps an existing service (`ghost_scout_iproyal.harvest_leads`,
  `auto_blast_engine.run_auto_blast_cycle`, `csv_leads_upload` insertion
  logic) so we don't duplicate business rules.
- Every call is audited to `cto_tool_runs` so the founder has a history.
"""
from __future__ import annotations

import logging
import re
import secrets as _secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/developers/cto/tools", tags=["cto-tools"])

_db = None
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _audit(tool: str, actor: str, payload: dict[str, Any],
                  result: dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        await _db.cto_tool_runs.insert_one({
            "tool":   tool,
            "actor":  actor,
            "ts":     _now(),
            "input":  payload,
            "result": {k: v for k, v in result.items() if k != "leads"},
        })
    except Exception as e:  # never let audit failure block the tool
        logger.warning(f"[cto-tools] audit insert failed: {e}")


async def _require_admin(authorization: str | None) -> str:
    """Admin gate — accepts founder/admin JWT directly so the CTO chat
    can call these tools without needing a separate developer account.

    iter D-49a — `_current_dev`'s auto-bootstrapped row strips
    `is_admin`, so we decode the JWT ourselves first. Fall back to
    `_current_dev` only for true developer accounts that happen to
    carry `role=admin`.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        import jwt as _jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass

    # Developer JWT path — only allow if the row carries an admin role.
    from routers.developer_portal_router import _current_dev
    acc = await _current_dev(authorization)
    if acc.get("is_admin") or acc.get("is_super_admin") or \
            acc.get("role") in ("admin", "super_admin", "founder"):
        return acc.get("email") or "admin"
    raise HTTPException(403, "admin_required")


# ── Models ───────────────────────────────────────────────────────────

class ScoutBody(BaseModel):
    city:     str = Field(..., min_length=2, max_length=80)
    category: str = Field(..., min_length=2, max_length=80)
    count:    int = Field(10, ge=1, le=50)
    country:  str = Field("ca", pattern="^(us|ca)$")


class LeadIn(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=200)
    email:         str = ""
    phone:         str = ""
    city:          str = ""
    country:       str = "ca"
    website:       str = ""


class ImportLeadsBody(BaseModel):
    leads: list[LeadIn] = Field(..., min_length=1, max_length=1000)


class BlastBody(BaseModel):
    tenant_id: str = "global"
    force:     bool = True


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/run-scout")
async def run_scout(body: ScoutBody,
                     authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    from services.ghost_scout_iproyal import harvest_leads
    res = await harvest_leads(
        query=body.category, location=body.city,
        country=body.country, limit=body.count,
    )
    out = {
        "ok":          bool(res.get("ok")),
        "fetched":     res.get("fetched", 0),
        "with_contact": res.get("with_contact", 0),
        "inserted":    res.get("inserted", 0),
        "skipped_dup": res.get("skipped_dup", 0),
        "ts":          _now(),
    }
    await _audit("run_scout", actor, body.model_dump(), out)
    return out


@router.post("/import-leads")
async def import_leads(body: ImportLeadsBody,
                        authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db_unavailable")

    inserted = 0
    skipped_dup = 0
    skipped_invalid = 0
    lead_ids: list[str] = []
    now = _now()

    for lead in body.leads:
        email = (lead.email or "").strip().lower()
        phone = (lead.phone or "").strip()
        if not email and not phone:
            skipped_invalid += 1
            continue
        if email and not _EMAIL_RE.match(email):
            email = ""  # keep lead but mark email unusable
        # dedup by email or phone
        dup_q: dict[str, Any] = {"$or": []}
        if email:
            dup_q["$or"].append({"email": email})
        if phone:
            dup_q["$or"].append({"phone": phone})
        if dup_q["$or"] and await _db.campaign_leads.find_one(dup_q, {"_id": 1}):
            skipped_dup += 1
            continue

        lead_id = f"CTO_{_secrets.token_hex(10)}"
        doc = {
            "lead_id":      lead_id,
            "business_name": lead.business_name.strip(),
            "email":        email,
            "phone":        phone,
            "city":         lead.city.strip(),
            "country":      (lead.country or "ca").lower(),
            "website":      (lead.website or "").strip(),
            "source":       "cto_import",
            "status":       "new",
            "created_at":   now,
            "verification": {
                "verified_at": now,
                "source":      "cto_tool",
                "channel_gating": {
                    "email":    bool(email),
                    "sms":      bool(phone),
                    "call":     bool(phone),
                    "whatsapp": False,
                },
            },
        }
        try:
            await _db.campaign_leads.insert_one(doc)
            inserted += 1
            lead_ids.append(lead_id)
        except Exception as e:
            logger.warning(f"[cto-tools] import lead failed: {e}")
            skipped_invalid += 1

    out = {
        "ok":              True,
        "inserted":        inserted,
        "skipped_dup":     skipped_dup,
        "skipped_invalid": skipped_invalid,
        "lead_ids":        lead_ids[:50],
        "ts":              _now(),
    }
    await _audit("import_leads", actor,
                  {"count": len(body.leads)}, out)
    return out


@router.post("/run-blast")
async def run_blast(body: BlastBody,
                     authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    from services.auto_blast_engine import run_auto_blast_cycle
    res = await run_auto_blast_cycle(force=body.force)
    out = {
        "ok":              bool(res.get("ok")),
        "tenants_run":     res.get("tenants_run", 0),
        "total_processed": res.get("total_processed", 0),
        "total_sent":      res.get("total_sent", 0),
        "summaries":       res.get("summaries", []),
        "ts":              _now(),
    }
    await _audit("run_blast", actor, body.model_dump(), out)
    return out


@router.get("/db-stats")
async def db_stats(authorization: str = Header(None)) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "db_unavailable")

    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    today_iso = today.isoformat()

    cl_total = await _db.campaign_leads.count_documents({})
    cl_fresh = await _db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "status": {"$in": ["new", "queued"]},
    })
    cl_emailed = await _db.campaign_leads.count_documents({
        "status": "emailed",
    })
    sent_today = await _db.sent_emails.count_documents({
        "$or": [
            {"sent_at": {"$gte": today}},
            {"sent_at": {"$gte": today_iso}},
        ],
    })
    customers = await _db.aurem_customers.count_documents({})

    last_blast_run = await _db.auto_blast_config.find_one(
        {"tenant_id": "global"},
        {"_id": 0, "last_run_at": 1, "last_run_sent": 1,
         "last_run_processed": 1, "last_run_note": 1},
    )

    out = {
        "ok":             True,
        "campaign_leads": {
            "total":   cl_total,
            "fresh":   cl_fresh,
            "emailed": cl_emailed,
        },
        "sent_emails_today": sent_today,
        "customers":         customers,
        "last_blast_run":    last_blast_run or {},
        "ts":                _now(),
    }
    await _audit("db_stats", actor, {}, out)
    return out
