"""
OpenFang Lead Ingestion Router — Iteration 215
===============================================
Inbound webhook for RightNow-AI/openfang "Lead Hand" — imports leads into
AUREM's `leads` collection and optionally triggers ORA follow-up.

Endpoints
---------
  POST /api/openfang/leads       — webhook (HMAC-SHA256 signed or plain token)
  GET  /api/openfang/status      — Admin-only health check (last N leads)

OpenFang sends leads individually or in batches. We accept both shapes.

Auth (Iteration 215 — HMAC upgrade)
-----------------------------------
The webhook verifies `X-OpenFang-Signature` using one of two modes,
picked automatically from the header's shape:

  1. HMAC mode  (recommended, default):
       X-OpenFang-Signature: sha256=<hex>
       X-OpenFang-Timestamp: <unix-epoch-seconds or ISO-8601>
     We compute HMAC-SHA256(secret, f"{timestamp}.{raw_body}") and compare.
     Timestamps older than ±5 min are rejected (replay protection).

  2. Plain-token mode (legacy fallback):
       X-OpenFang-Signature: <plain-token>  OR  ?secret=<plain-token>
     Accepted only when OPENFANG_ALLOW_PLAIN_TOKEN=true in env.

Env
---
OPENFANG_WEBHOOK_SECRET     — shared secret (required)
OPENFANG_DEFAULT_TENANT     — default tenant_id (default: "aurem_platform")
OPENFANG_ALLOW_PLAIN_TOKEN  — "true" to accept legacy plain-token (default: true
                              for backward-compat; flip to "false" once Legion
                              is fully migrated to HMAC)
OPENFANG_REPLAY_WINDOW_S    — replay window in seconds (default: 300)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/openfang", tags=["OpenFang Lead Ingestion"])

from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
OPENFANG_SECRET = os.environ.get("OPENFANG_WEBHOOK_SECRET", "")
DEFAULT_TENANT = os.environ.get("OPENFANG_DEFAULT_TENANT", "aurem_platform")
OPENFANG_ALLOW_PLAIN = (os.environ.get("OPENFANG_ALLOW_PLAIN_TOKEN", "true").lower() == "true")
OPENFANG_REPLAY_WINDOW_S = int(os.environ.get("OPENFANG_REPLAY_WINDOW_S", "300"))

_db = None


def set_db(db):
    global _db
    _db = db


# ─────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────
class OpenFangLead(BaseModel):
    business_name: str = Field(..., min_length=1, max_length=300)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    notes: Optional[str] = None
    source_channel: Optional[str] = "openfang:lead_hand"
    confidence: Optional[float] = None
    tenant_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class OpenFangBatch(BaseModel):
    leads: List[OpenFangLead] = Field(..., min_length=1, max_length=500)
    run_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────
async def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = payload.get("role", "")
    if role in ("admin", "super_admin") or payload.get("is_admin") or payload.get("is_super_admin"):
        return payload
    raise HTTPException(403, "Admin only")


def _parse_ts(raw: str) -> Optional[float]:
    """Accept unix epoch (int/float) or ISO-8601. Returns unix seconds."""
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _validate_webhook(request: Request, raw_body: bytes) -> str:
    """
    Validate the inbound webhook. Returns the auth mode used ("hmac"|"plain").
    Raises 401 on failure.
    """
    if not OPENFANG_SECRET:
        raise HTTPException(503, "OPENFANG_WEBHOOK_SECRET not configured")

    sig = request.headers.get("X-OpenFang-Signature") or ""
    ts = request.headers.get("X-OpenFang-Timestamp") or ""

    # HMAC mode: "sha256=<hex>"
    if sig.lower().startswith("sha256="):
        provided_hex = sig.split("=", 1)[1].strip()
        ts_secs = _parse_ts(ts)
        if ts_secs is None:
            raise HTTPException(401, "Missing or malformed X-OpenFang-Timestamp")
        now = datetime.now(timezone.utc).timestamp()
        if abs(now - ts_secs) > OPENFANG_REPLAY_WINDOW_S:
            raise HTTPException(401, "Timestamp outside replay window")
        signed_payload = f"{ts}.".encode() + raw_body
        expected = hmac.new(
            OPENFANG_SECRET.encode(), signed_payload, hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, provided_hex):
            raise HTTPException(401, "Invalid HMAC signature")
        return "hmac"

    # Plain-token legacy fallback
    if OPENFANG_ALLOW_PLAIN:
        provided = sig or request.query_params.get("secret") or ""
        if provided and hmac.compare_digest(provided, OPENFANG_SECRET):
            return "plain"

    raise HTTPException(401, "Invalid webhook signature")


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────
@router.post("/leads")
async def ingest_leads(request: Request):
    """Accept either a single lead or {leads: [...]} batch. HMAC-signed or plain."""
    # Read raw body ONCE — HMAC must hash exactly what the sender signed.
    raw_body = await request.body()
    auth_mode = _validate_webhook(request, raw_body)

    if _db is None:
        raise HTTPException(503, "DB not available")

    import json as _json
    try:
        payload: Dict[str, Any] = _json.loads(raw_body.decode("utf-8") or "{}")
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON body: {e}")

    # Normalize: single obj → list
    leads_raw: List[Dict[str, Any]] = []
    if "leads" in payload:
        leads_raw = payload.get("leads") or []
    elif "business_name" in payload:
        leads_raw = [payload]
    else:
        raise HTTPException(400, "Payload must contain 'business_name' or 'leads' array")

    run_id = payload.get("run_id") or uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()

    inserted = 0
    duplicates = 0
    failed = 0
    results: List[Dict[str, Any]] = []

    for raw in leads_raw[:500]:
        try:
            lead = OpenFangLead(**raw)
        except Exception as e:
            failed += 1
            results.append({"error": str(e), "raw_preview": str(raw)[:160]})
            continue

        tenant_id = lead.tenant_id or DEFAULT_TENANT
        lead_id = f"ofl_{uuid4().hex[:14]}"
        doc = {
            "lead_id": lead_id,
            "tenant_id": tenant_id,
            "source": "openfang",
            "source_channel": lead.source_channel or "openfang:lead_hand",
            "source_run_id": run_id,
            "business_name": lead.business_name,
            "email": lead.email,
            "phone": lead.phone,
            "website": lead.website,
            "industry": lead.industry,
            "city": lead.city,
            "region": lead.region,
            "notes": lead.notes,
            "confidence": lead.confidence,
            "extra": lead.extra or {},
            "status": "new",
            "created_at": now,
            "imported_at": now,
        }

        # Dedup by (tenant_id, business_name+phone or email)
        dedup_q: Dict[str, Any] = {"tenant_id": tenant_id, "business_name": lead.business_name}
        if lead.email:
            dedup_q["email"] = lead.email
        elif lead.phone:
            dedup_q["phone"] = lead.phone

        try:
            exists = await _db.leads.find_one(dedup_q, projection={"_id": 0, "lead_id": 1})
            if exists:
                duplicates += 1
                results.append({"lead_id": exists.get("lead_id"), "duplicate": True})
                continue
            await _db.leads.insert_one(doc)
            inserted += 1
            results.append({"lead_id": lead_id, "imported": True})
        except Exception as e:
            failed += 1
            results.append({"error": str(e), "business_name": lead.business_name})

    # Audit log
    try:
        await _db.openfang_imports.insert_one({
            "run_id": run_id,
            "inserted": inserted,
            "duplicates": duplicates,
            "failed": failed,
            "total": len(leads_raw),
            "auth_mode": auth_mode,
            "ts": now,
        })
    except Exception as e:
        logger.warning(f"[OpenFang] audit insert failed: {e}")

    # Wire into CRM + follow-up pipeline — same A2A event Hunter ORA uses.
    if inserted > 0:
        try:
            from services.a2a_bus import bus as _a2a
            # Group by tenant so Follow-up can fan out per-tenant
            tenants = {(d.get("tenant_id") or DEFAULT_TENANT) for d in [
                {"tenant_id": lead.get("tenant_id")} for lead in leads_raw[:500]
                if isinstance(lead, dict)
            ]}
            for t in tenants:
                await _a2a.emit(
                    "openfang_ingest",
                    "new_leads_batch",
                    {
                        "source": "openfang",
                        "run_id": run_id,
                        "tenant_id": t,
                        "count": inserted,
                    },
                    to_agent="followup_ora",
                )
        except Exception as e:
            logger.warning(f"[OpenFang] A2A notify failed: {e}")

        # Surface in Activity Feed marquee via ora_command_log (consistent schema)
        try:
            await _db.ora_command_log.insert_one({
                "channel": "openfang",
                "user": "openfang:lead_hand",
                "raw": f"import {inserted} lead(s) · run {run_id}",
                "intent": "LEADS_IMPORT",
                "params": {"source": "openfang", "run_id": run_id, "count": inserted},
                "ok": True,
                "reply_preview": f"{inserted} inserted · {duplicates} dup · {failed} failed",
                "timestamp": now,
            })
        except Exception as e:
            logger.warning(f"[OpenFang] marquee log failed: {e}")

    return {
        "ok": True,
        "run_id": run_id,
        "auth_mode": auth_mode,
        "inserted": inserted,
        "duplicates": duplicates,
        "failed": failed,
        "total": len(leads_raw),
        "details": results[:50],  # cap echo
    }


@router.get("/status")
async def status(request: Request):
    await _require_admin(request)
    configured = bool(OPENFANG_SECRET)
    base = {
        "configured": configured,
        "default_tenant": DEFAULT_TENANT,
        "auth": {
            "hmac_enabled": True,
            "plain_token_allowed": OPENFANG_ALLOW_PLAIN,
            "replay_window_s": OPENFANG_REPLAY_WINDOW_S,
        },
    }
    if _db is None:
        return {**base, "last_imports": [], "total_leads_from_openfang": 0}
    total = await _db.leads.count_documents({"source": "openfang"})
    recent = await _db.openfang_imports.find(
        {}, projection={"_id": 0}).sort("ts", -1).limit(10).to_list(length=10)
    # Recent mode breakdown (last 100 imports)
    recent_100 = await _db.openfang_imports.find(
        {}, projection={"_id": 0, "auth_mode": 1}).sort("ts", -1).limit(100).to_list(length=100)
    mode_counts: Dict[str, int] = {}
    for r in recent_100:
        mode_counts[r.get("auth_mode") or "unknown"] = mode_counts.get(r.get("auth_mode") or "unknown", 0) + 1
    return {
        **base,
        "total_leads_from_openfang": total,
        "last_imports": recent,
        "auth_mode_counts_last_100": mode_counts,
    }


@router.get("/leads/recent")
async def recent_leads(request: Request, limit: int = 25):
    """Admin-only — list recent leads imported via OpenFang for the /admin/openfang UI."""
    await _require_admin(request)
    if _db is None:
        return {"items": []}
    limit = max(1, min(200, int(limit)))
    rows = await _db.leads.find(
        {"source": "openfang"},
        projection={"_id": 0},
    ).sort("imported_at", -1).limit(limit).to_list(length=limit)
    return {"items": rows, "count": len(rows)}


class SigProbe(BaseModel):
    timestamp: str
    body: str  # raw JSON string, EXACTLY as it would be sent


@router.post("/verify-signature")
async def verify_signature(request: Request, probe: SigProbe):
    """
    Admin-only helper. Given (timestamp, body), returns the hex HMAC signature
    the Legion node SHOULD send. Useful for curl probes & debugging the pipe.
    """
    await _require_admin(request)
    if not OPENFANG_SECRET:
        raise HTTPException(503, "OPENFANG_WEBHOOK_SECRET not configured")
    signed_payload = f"{probe.timestamp}.".encode() + probe.body.encode("utf-8")
    expected = hmac.new(
        OPENFANG_SECRET.encode(), signed_payload, hashlib.sha256,
    ).hexdigest()
    return {
        "timestamp": probe.timestamp,
        "header_X_OpenFang_Signature": f"sha256={expected}",
        "header_X_OpenFang_Timestamp": probe.timestamp,
        "algorithm": "HMAC-SHA256(secret, f\"{timestamp}.{raw_body}\")",
    }

