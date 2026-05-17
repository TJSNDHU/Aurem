"""
AUREM — Admin AWB Maintenance Router (iter 305i)
================================================
Admin-only endpoints to run idempotent maintenance on the
`db.auto_built_sites` collection without needing direct Atlas access.

Endpoints (all require super_admin JWT via Authorization: Bearer):
  POST /api/admin/awb/backfill-particles
       body: {dry_run: bool}            (default false)
       returns: {candidates, updated, already_injected, no_hero_container}

  POST /api/admin/awb/backfill-dedup-keys
       body: {dry_run: bool}            (default false)
       returns: {updated, skipped, leads_missing}

  GET  /api/admin/awb/maintenance-stats
       returns row counts + key completeness for quick health check.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/awb", tags=["Admin · AWB Maintenance"])

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"

_db = None


def set_db(database):
    global _db
    _db = database


# ─── Auth gate ──────────────────────────────────────────────────────────────

def _require_super_admin(request: Request) -> dict:
    if not JWT_SECRET:
        raise HTTPException(status_code=503, detail="Auth not configured")
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not (
        payload.get("is_super_admin")
        or payload.get("is_admin")
        or payload.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(status_code=403, detail="admin required")
    return payload


# ─── Particles backfill ─────────────────────────────────────────────────────

class BackfillRequest(BaseModel):
    dry_run: bool = Field(default=False)


@router.post("/backfill-particles")
async def backfill_particles(body: BackfillRequest, request: Request):
    _require_super_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    from services.awb_particles_injector import inject_particles, _SENTINEL

    q = {
        "status": {"$in": ["rendered", "published", "deployed"]},
        "rendered_html": {"$exists": True, "$ne": ""},
    }
    candidates = await _db.auto_built_sites.count_documents(q)
    cur = _db.auto_built_sites.find(
        q, {"_id": 0, "site_id": 1, "rendered_html": 1}
    )
    updated = already = unchanged = 0
    async for site in cur:
        html = site.get("rendered_html") or ""
        if _SENTINEL in html:
            already += 1
            continue
        new_html = inject_particles(html)
        if new_html == html:
            unchanged += 1
            continue
        if not body.dry_run:
            await _db.auto_built_sites.update_one(
                {"site_id": site["site_id"]},
                {"$set": {"rendered_html": new_html}},
            )
        updated += 1

    logger.info(
        f"[admin/awb] backfill-particles dry={body.dry_run} "
        f"updated={updated} already={already} unchanged={unchanged}"
    )
    return {
        "candidates": candidates,
        "updated": updated,
        "already_injected": already,
        "no_hero_container": unchanged,
        "dry_run": body.dry_run,
    }


# ─── Dedup keys backfill ────────────────────────────────────────────────────

def _norm_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        digits = "1" + digits
    return digits if 10 <= len(digits) <= 15 else None


def _norm_name(name: str) -> Optional[str]:
    if not name:
        return None
    out = re.sub(r"[^a-z0-9]", "", name.lower().strip())
    return out or None


def _extract_domain(url: str) -> Optional[str]:
    if not url:
        return None
    u = re.sub(r"^https?://", "", str(url).lower().strip()).split("/")[0]
    u = u.removeprefix("www.")
    return u or None


@router.post("/backfill-dedup-keys")
async def backfill_dedup_keys(body: BackfillRequest, request: Request):
    _require_super_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    q = {
        "$or": [
            {"phone_normalized": {"$in": [None, ""]}},
            {"phone_normalized": {"$exists": False}},
            {"website_domain": {"$in": [None, ""]}},
            {"website_domain": {"$exists": False}},
            {"business_name_normalized": {"$in": [None, ""]}},
            {"business_name_normalized": {"$exists": False}},
            {"city": {"$exists": False}},
        ]
    }
    candidates = await _db.auto_built_sites.count_documents(q)
    cur = _db.auto_built_sites.find(q, {
        "_id": 1, "lead_id": 1, "business_name": 1,
        "phone_normalized": 1, "website_domain": 1,
        "business_name_normalized": 1, "city": 1,
    })

    updated = skipped = leads_missing = 0
    async for site in cur:
        biz_name = site.get("business_name")
        phone = website = city = None
        lead_id = site.get("lead_id")
        if lead_id:
            lead = await _db.campaign_leads.find_one(
                {"lead_id": lead_id},
                {"_id": 0, "phone": 1, "business_phone": 1,
                 "website": 1, "website_url": 1, "city": 1,
                 "business_name": 1},
            )
            if lead:
                phone = lead.get("phone") or lead.get("business_phone") or ""
                website = lead.get("website") or lead.get("website_url") or ""
                city = (lead.get("city") or "").strip()
                biz_name = biz_name or lead.get("business_name")
            else:
                leads_missing += 1
        else:
            leads_missing += 1

        patch = {}
        pn = _norm_phone(phone)
        if pn and not site.get("phone_normalized"):
            patch["phone_normalized"] = pn
        dom = _extract_domain(website or "")
        if dom and not site.get("website_domain"):
            patch["website_domain"] = dom
        nn = _norm_name(biz_name or "")
        if nn and not site.get("business_name_normalized"):
            patch["business_name_normalized"] = nn
        if city and not site.get("city"):
            patch["city"] = city.lower()

        if patch and not body.dry_run:
            await _db.auto_built_sites.update_one(
                {"_id": site["_id"]}, {"$set": patch}
            )
        if patch:
            updated += 1
        else:
            skipped += 1

    return {
        "candidates": candidates,
        "updated": updated,
        "skipped_no_source_data": skipped,
        "leads_missing": leads_missing,
        "dry_run": body.dry_run,
    }


# ─── Stats ──────────────────────────────────────────────────────────────────

@router.get("/maintenance-stats")
async def maintenance_stats(request: Request):
    _require_super_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    total = await _db.auto_built_sites.count_documents({})
    by_status: dict = {}
    async for d in _db.auto_built_sites.aggregate([
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]):
        by_status[d["_id"] or "(none)"] = d["n"]

    has_phone = await _db.auto_built_sites.count_documents({
        "phone_normalized": {"$exists": True, "$nin": [None, ""]}
    })
    has_domain = await _db.auto_built_sites.count_documents({
        "website_domain": {"$exists": True, "$nin": [None, ""]}
    })
    has_name = await _db.auto_built_sites.count_documents({
        "business_name_normalized": {"$exists": True, "$nin": [None, ""]}
    })
    has_city = await _db.auto_built_sites.count_documents({
        "city": {"$exists": True, "$nin": [None, ""]}
    })
    has_particles = await _db.auto_built_sites.count_documents({
        "rendered_html": {"$regex": "aurem-particles-v1"}
    })

    return {
        "total_sites": total,
        "by_status": by_status,
        "dedup_keys": {
            "phone_normalized": has_phone,
            "website_domain": has_domain,
            "business_name_normalized": has_name,
            "city": has_city,
        },
        "particles_injected": has_particles,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
