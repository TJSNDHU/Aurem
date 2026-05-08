"""
ORA Phase 2.5 Router — Sovereign Customer Handler endpoints
==============================================================
Admin (auth-gated):
  GET  /api/admin/ora-25/retention                — queued retention candidates
  POST /api/admin/ora-25/retention/{id}/send      — fire the message
  GET  /api/admin/ora-25/upsell                   — queued upsell candidates
  POST /api/admin/ora-25/upsell/{id}/send         — fire the message
  GET  /api/admin/ora-25/next-actions?limit       — generated NBAs
  POST /api/admin/ora-25/scan-now                 — manual retention+upsell scan
  GET  /api/admin/ora-25/policy-log?limit         — guardian audit trail
  POST /api/admin/ora-25/guardian-test            — dry-run a policy check
  GET  /api/admin/ora-25/health                   — public liveness

Public (NO auth):
  GET  /api/public/repair-quote/{quote_id}        — read-only shareable report
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from utils.admin_guard import verify_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/ora-25", tags=["ORA Phase 2.5 Customer Handler"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


def _strip(d: Dict[str, Any]) -> Dict[str, Any]:
    if not d:
        return {}
    return {k: v for k, v in d.items() if k != "_id"}


# ─────────────────────────────────────────────────────────────────
# ADMIN — Retention
# ─────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"ok": True, "db_wired": _get_db() is not None}


@router.get("/retention")
async def list_retention(
    authorization: Optional[str] = Header(None),
    status: str = Query("queued"),
    limit: int = Query(50, ge=1, le=200),
):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    cursor = db.ora_retention_actions.find({"status": status}).sort("created_at", -1).limit(limit)
    items = [_strip(d) async for d in cursor]
    return {"ok": True, "count": len(items), "items": items}


@router.post("/retention/{action_id}/send")
async def send_retention(action_id: str, authorization: Optional[str] = Header(None)):
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    doc = await db.ora_retention_actions.find_one({"_id": _to_oid(action_id)} if _is_oid(action_id) else {"action_id": action_id})
    if not doc:
        # Try kind+email fallback
        doc = await db.ora_retention_actions.find_one({"created_at": action_id})
    if not doc:
        raise HTTPException(404, "Retention action not found")

    from services.ora_phase_25 import guardian_check
    target = doc.get("phone") or doc.get("email")
    channel = "whatsapp" if doc.get("phone") else "email"
    body = doc.get("suggested_msg") or ""
    decision = await guardian_check(
        db, action_kind=channel, target=target or "",
        body=body, channel=channel,
    )
    if not decision["allowed"]:
        await _mark_status(db, doc, "blocked", reason=decision["reason"])
        return {"ok": False, "blocked": True, "policy": decision}

    final_body = decision["fixes"].get("sanitized_body") or body
    sent: Dict[str, Any] = {}
    try:
        if channel == "whatsapp" and doc.get("phone"):
            from services.twilio_whatsapp import send_whatsapp
            res = await send_whatsapp(to_phone=doc["phone"], body=final_body[:1500])
            sent = {"channel": "whatsapp", "sid": (res or {}).get("sid"), "ok": bool(res and res.get("sid"))}
        else:
            from services.email_service_resend import send_email
            ok = await send_email(
                to=doc.get("email"),
                subject=f"AUREM check-in — {doc.get('biz') or doc.get('email')}",
                html=f"<pre style='font-family:system-ui;white-space:pre-wrap'>{final_body}</pre>",
            )
            sent = {"channel": "email", "ok": bool(ok)}
    except Exception as e:
        sent = {"ok": False, "error": str(e)[:120]}

    await _mark_status(db, doc, "sent" if sent.get("ok") else "send_failed", extra={"sent": sent, "sender": payload.get("email")})
    return {"ok": bool(sent.get("ok")), "sent": sent}


# ─────────────────────────────────────────────────────────────────
# ADMIN — Upsell
# ─────────────────────────────────────────────────────────────────
@router.get("/upsell")
async def list_upsell(
    authorization: Optional[str] = Header(None),
    status: str = Query("queued"),
    limit: int = Query(50, ge=1, le=200),
):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    cursor = db.ora_upsell_actions.find({"status": status}).sort("created_at", -1).limit(limit)
    items = [_strip(d) async for d in cursor]
    return {"ok": True, "count": len(items), "items": items}


@router.post("/upsell/{email}/send")
async def send_upsell(email: str, authorization: Optional[str] = Header(None)):
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    doc = await db.ora_upsell_actions.find_one({"email": email, "status": "queued"})
    if not doc:
        raise HTTPException(404, f"No queued upsell for {email}")

    from services.ora_phase_25 import guardian_check
    body = doc.get("suggested_msg") or ""
    decision = await guardian_check(db, action_kind="email", target=email, body=body, channel="email")
    if not decision["allowed"]:
        await _mark_status(db, doc, "blocked", reason=decision["reason"], collection="ora_upsell_actions")
        return {"ok": False, "blocked": True, "policy": decision}

    final_body = decision["fixes"].get("sanitized_body") or body
    sent: Dict[str, Any] = {}
    try:
        from services.email_service_resend import send_email
        ok = await send_email(
            to=email,
            subject=f"AUREM — let's talk about your {doc.get('suggested_plan') or 'upgrade'}",
            html=f"<pre style='font-family:system-ui;white-space:pre-wrap'>{final_body}</pre>",
        )
        sent = {"channel": "email", "ok": bool(ok)}
    except Exception as e:
        sent = {"ok": False, "error": str(e)[:120]}

    await _mark_status(
        db, doc, "sent" if sent.get("ok") else "send_failed",
        extra={"sent": sent, "sender": payload.get("email")},
        collection="ora_upsell_actions",
    )
    return {"ok": bool(sent.get("ok")), "sent": sent}


# ─────────────────────────────────────────────────────────────────
# ADMIN — Next Best Action + Policy Log + Manual Scan
# ─────────────────────────────────────────────────────────────────
@router.get("/next-actions")
async def list_next_actions(
    authorization: Optional[str] = Header(None),
    limit: int = Query(20, ge=1, le=100),
):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    cursor = db.ora_next_actions.find().sort("generated_at", -1).limit(limit)
    items = [_strip(d) async for d in cursor]
    return {"ok": True, "count": len(items), "items": items}


@router.post("/scan-now")
async def scan_now(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    from services.ora_phase_25 import scan_retention_candidates, scan_upsell_candidates
    r = await scan_retention_candidates(db)
    u = await scan_upsell_candidates(db)
    return {"ok": True, "retention_found": len(r), "upsell_found": len(u)}


@router.get("/policy-log")
async def policy_log(
    authorization: Optional[str] = Header(None),
    limit: int = Query(50, ge=1, le=200),
    only_blocked: bool = Query(False),
):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not wired")
    q = {"allowed": False} if only_blocked else {}
    cursor = db.ora_policy_log.find(q).sort("created_at", -1).limit(limit)
    items = [_strip(d) async for d in cursor]
    return {"ok": True, "count": len(items), "items": items}


class GuardianTestReq(BaseModel):
    action_kind: str = "email"
    target: str = ""
    body: str = ""
    cost_cents: int = 0
    channel: str = "chat"


@router.post("/guardian-test")
async def guardian_test(req: GuardianTestReq, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    db = _get_db()
    from services.ora_phase_25 import guardian_check
    return await guardian_check(
        db,
        action_kind=req.action_kind,
        target=req.target,
        body=req.body,
        cost_cents=req.cost_cents,
        channel=req.channel,
    )


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────
def _is_oid(s: str) -> bool:
    return isinstance(s, str) and len(s) == 24 and all(c in "0123456789abcdef" for c in s.lower())


def _to_oid(s: str):
    try:
        from bson import ObjectId
        return ObjectId(s)
    except Exception:
        return None


async def _mark_status(db, doc, new_status, *, reason=None, extra=None, collection="ora_retention_actions"):
    update = {"status": new_status, "actioned_at": datetime.now(timezone.utc).isoformat()}
    if reason:
        update["reason"] = reason
    if extra:
        update.update(extra)
    try:
        if "_id" in doc:
            await db[collection].update_one({"_id": doc["_id"]}, {"$set": update})
        elif doc.get("email") and doc.get("kind"):
            await db[collection].update_one(
                {"email": doc["email"], "kind": doc["kind"]},
                {"$set": update},
            )
    except Exception:
        pass
