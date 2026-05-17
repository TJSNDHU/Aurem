"""
Customer Intelligence Router — endpoints for the BIN intelligence stack.

  POST /api/pixel/event                              — Pixel ingest (public, no auth)
  POST /api/customer/intelligence/import-csv         — CSV invoice import
  GET  /api/customer/intelligence/buckets            — 3-bucket contact view
  POST /api/customer/intelligence/bucket-confirm     — promote 'likely' → 'verified'
  POST /api/customer/intelligence/mobile-scores      — ORA mobile score upload
  GET  /api/customer/intelligence/summary            — counts-only snapshot
  POST /api/customer/intelligence/merge-now          — trigger merge for caller BIN
  DELETE /api/customer/intelligence/purge            — customer-initiated purge

Privacy:
  • Body inputs that contain emails/phones are immediately hashed
    by services.bin_intelligence before storage.
  • Responses NEVER include emails, phones, names — only hashes/scores.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile

from services import bin_intelligence as bi

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["BIN Intelligence"])

_db = None


def set_db(db) -> None:
    global _db
    _db = db


def _decode(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET") or ""
    if not secret:
        raise HTTPException(500, "JWT secret not configured")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _ctx(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    claims = _decode(auth[7:])
    bin_id = claims.get("business_id") or ""
    email = (claims.get("email") or "").lower()
    if not bin_id and email and _db is not None:
        u = await _db.platform_users.find_one(
            {"email": email}, {"_id": 0, "business_id": 1}
        )
        bin_id = (u or {}).get("business_id") or ""
    if not bin_id:
        raise HTTPException(403, "Token missing business context")
    return {"business_id": bin_id, "email": email}


# ═══════════════════════════════════════════════════════════════════════
# Pixel — Part 1.
# ═══════════════════════════════════════════════════════════════════════
@router.post("/pixel/event")
async def pixel_event(request: Request, body: Dict[str, Any] = Body(...)):
    """Public pixel beacon endpoint. NO auth — the BIN ID is the secret.

    Body:
      {
        bin_id, visitor_hash, page, time_spent, referrer, device,
        form_filled?, form_email?, form_phone?
      }

    `form_email` and `form_phone` are hashed immediately — never stored.
    """
    if _db is None:
        raise HTTPException(503, "DB not ready")
    bin_id = (body.get("bin_id") or "").strip()
    if not bin_id:
        raise HTTPException(400, "bin_id required")

    result = await bi.record_pixel_event(
        _db,
        business_id=bin_id,
        visitor_hash=(body.get("visitor_hash") or "")[:64],
        page=body.get("page") or "",
        time_spent=int(body.get("time_spent") or 0),
        referrer=body.get("referrer") or body.get("source") or "",
        device=body.get("device") or "desktop",
        form_filled=bool(body.get("form_filled") or False),
        form_email=body.get("form_email") or "",
        form_phone=body.get("form_phone") or "",
    )
    # iter 322ar — ORA universal learner hook (HOOK 9: pixel)
    try:
        import asyncio as _asyncio
        _asyncio.create_task(_learn_pixel_event(bin_id, body))
    except Exception:
        pass
    return result
    # NOTE: hook 9 (pixel) is wired in the wrapper below via _learn_pixel_event
    # because Python returns above; see line ~104.


async def _learn_pixel_event(bin_id: str, body: Dict[str, Any]) -> None:
    try:
        from services.ora_universal_learner import ora_learn as _ora_learn
        await _ora_learn({
            "source": "pixel",
            "event": "PIXEL_EVENT",
            "category": "pixel_intelligence",
            "summary": (
                f"Visitor page={body.get('page') or '?'} "
                f"time={int(body.get('time_spent') or 0)}s "
                f"form_filled={bool(body.get('form_filled'))} "
                f"device={body.get('device') or 'desktop'}"
            ),
            "outcome": "tracked",
            "agent": "pixel",
            "bin_id": bin_id,
        })
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
# CSV invoice import — Part 4.
# ═══════════════════════════════════════════════════════════════════════
@router.post("/customer/intelligence/import-csv")
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    casl_accepted: str = Form("false"),
):
    """Upload a CSV of past invoices. Auto-detects columns.

    Form field `casl_accepted` MUST be "true" — CASL+PIPEDA requires
    explicit consent that an existing business relationship exists.
    """
    ctx = await _ctx(request)
    if (casl_accepted or "").lower() not in ("true", "1", "yes"):
        raise HTTPException(400, "CASL consent checkbox is required")

    raw = await file.read()
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, "file too large (10MB max)")
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        raise HTTPException(400, "could not decode file as UTF-8")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(400, "empty CSV")
    header = rows[0]
    canon_map: Dict[int, str] = {}
    for idx, h in enumerate(header):
        c = bi.detect_column(h)
        if c:
            canon_map[idx] = c
    if not canon_map:
        raise HTTPException(400, "could not detect any known columns "
                                "(name/phone/email/amount/date/service)")

    # Log CASL consent BEFORE writing any contacts.
    ip = (request.client.host if request.client else "") or request.headers.get("x-forwarded-for", "")
    consent_id = await bi.log_casl_consent(
        _db,
        business_id=ctx["business_id"],
        basis="existing_relationship",
        source="invoice_csv",
        record_count=len(rows) - 1,
        ip=ip,
        user_email=ctx.get("email"),
    )

    parsed: List[Dict[str, Any]] = []
    for r in rows[1:]:
        d: Dict[str, Any] = {}
        for idx, val in enumerate(r):
            canon = canon_map.get(idx)
            if canon:
                d[canon] = val
        if d:
            parsed.append(d)

    res = await bi.import_invoice_rows(
        _db,
        business_id=ctx["business_id"],
        rows=parsed,
        consent_id=consent_id,
    )
    return {
        "ok": True,
        "filename": file.filename,
        "columns_detected": list(canon_map.values()),
        "rows_seen": len(parsed),
        "casl": {"basis": "existing_relationship", "consent_id": consent_id},
        **res,
    }


# ═══════════════════════════════════════════════════════════════════════
# 3-Bucket view — Part 7.
# ═══════════════════════════════════════════════════════════════════════
@router.get("/customer/intelligence/buckets")
async def buckets(request: Request, limit: int = 50):
    """Return contacts grouped into Verified / Likely / Unclear.

    Each row carries only contact_hash + scores + source — NO PII.
    """
    ctx = await _ctx(request)
    bin_id = ctx["business_id"]
    rows: List[Dict[str, Any]] = []
    cursor = _db.bin_intelligence.find(
        {"bin_id": bin_id},
        {"_id": 0, "contact_hash": 1, "source": 1, "business_score": 1,
         "metadata": 1, "last_seen": 1, "first_seen": 1},
    ).sort([("business_score", -1)]).limit(max(1, min(limit, 200)))
    async for r in cursor:
        rows.append(r)

    out = {"verified": [], "likely": [], "unclear": []}
    for r in rows:
        b = bi.bucket_for(int(r.get("business_score") or 0), r.get("source") or "")
        evidence = _evidence_line(r)
        out[b].append({
            "contact_hash": (r.get("contact_hash") or "")[:16],
            "source": r.get("source"),
            "business_score": int(r.get("business_score") or 0),
            "evidence": evidence,
            "first_seen": r["first_seen"].isoformat() if isinstance(r.get("first_seen"), datetime) else None,
        })
    return {
        "ok": True,
        "counts": {k: len(v) for k, v in out.items()},
        "buckets": out,
    }


def _evidence_line(r: Dict[str, Any]) -> str:
    """One-line anonymous evidence for the customer review screen."""
    src = r.get("source") or "?"
    md = r.get("metadata") or {}
    if src == "invoice":
        sh = (md.get("service_history") or [{}])[0]
        amt = sh.get("amount", 0)
        return f"Past invoice (${amt:,.0f})" if amt else "Past invoice"
    if src == "email":
        kw = md.get("keywords") or []
        n = md.get("frequency") or 0
        return f"{n} business email{'s' if n != 1 else ''}" + (f" · {', '.join(kw[:3])}" if kw else "")
    if src == "phone" or src == "mobile":
        return f"Call pattern: {md.get('pattern', '—')} ({md.get('frequency_bucket','?')})"
    if src == "pixel":
        return "Filled form on website" if md.get("form_filled") else "Website visitor"
    return src


@router.post("/customer/intelligence/bucket-confirm")
async def bucket_confirm(request: Request, body: Dict[str, Any] = Body(...)):
    """Customer confirms a 'likely' contact → promote to 'verified'."""
    ctx = await _ctx(request)
    contact_hash = (body.get("contact_hash") or "").strip()
    if not contact_hash:
        raise HTTPException(400, "contact_hash required")
    res = await _db.bin_intelligence.update_many(
        {"bin_id": ctx["business_id"], "contact_hash": contact_hash},
        {"$set": {"customer_confirmed": True, "business_score": 100}},
    )
    # iter 322ar — ORA universal learner hook (HOOK 11: contact verify)
    try:
        import asyncio as _asyncio
        from services.ora_universal_learner import ora_learn as _ora_learn
        _asyncio.create_task(_ora_learn({
            "source": "intelligence",
            "event": "CONTACT_VERIFIED",
            "category": "lead_intelligence",
            "summary": (
                f"Customer verified contact (hash={contact_hash[:12]}). "
                f"Promoted to verified bucket. updated={res.modified_count}."
            ),
            "outcome": "verified",
            "agent": "intelligence_merge",
            "bin_id": ctx["business_id"],
        }))
    except Exception:
        pass
    return {"ok": True, "updated": res.modified_count}


# ═══════════════════════════════════════════════════════════════════════
# Mobile scores ingest — Part 3 (stub backend, no native shell yet).
# ═══════════════════════════════════════════════════════════════════════
@router.post("/customer/intelligence/mobile-scores")
async def mobile_scores(request: Request, body: Dict[str, Any] = Body(...)):
    """ORA mobile uploads encrypted scores. Body:
      {scores: [{contact_hash, business_score, pattern, frequency_bucket}]}
    """
    ctx = await _ctx(request)
    scores = body.get("scores") or []
    if not isinstance(scores, list):
        raise HTTPException(400, "scores must be a list")
    accepted = 0
    for s in scores[:1000]:
        ch = (s.get("contact_hash") or "").strip()
        if not ch:
            continue
        await bi.ingest_mobile_score(
            _db,
            business_id=ctx["business_id"],
            contact_hash=ch,
            business_score=int(s.get("business_score") or 0),
            pattern=str(s.get("pattern") or ""),
            frequency_bucket=str(s.get("frequency_bucket") or "med"),
        )
        accepted += 1
    return {"ok": True, "accepted": accepted}


# ═══════════════════════════════════════════════════════════════════════
# Snapshot summary — for Morning Brief + dashboard.
# ═══════════════════════════════════════════════════════════════════════
@router.get("/customer/intelligence/summary")
async def intel_summary(request: Request):
    ctx = await _ctx(request)
    return {
        "ok": True,
        "bin_id": ctx["business_id"],
        "summary": await bi.intelligence_summary(_db, ctx["business_id"]),
    }


@router.post("/customer/intelligence/merge-now")
async def merge_now(request: Request):
    ctx = await _ctx(request)
    res = await bi.merge_bin(_db, ctx["business_id"])
    return {"ok": True, **res}


@router.delete("/customer/intelligence/purge")
async def purge_intel(request: Request):
    """Customer-initiated full purge of intelligence data for their BIN."""
    ctx = await _ctx(request)
    bin_id = ctx["business_id"]
    r1 = await _db.bin_intelligence.delete_many({"bin_id": bin_id})
    r2 = await _db.bin_unified_profiles.delete_many({"bin_id": bin_id})
    r3 = await _db.pixel_events.delete_many({"bin_id": bin_id})
    return {
        "ok": True,
        "deleted": {
            "bin_intelligence": r1.deleted_count,
            "bin_unified_profiles": r2.deleted_count,
            "pixel_events": r3.deleted_count,
        },
    }
