"""
AUREM Accurate Scout Router
============================
Exposes multi-source business verification endpoints.

  POST /api/scout/verify                  — verify by name + city
  POST /api/scout/verify/lead/{lead_id}   — verify existing lead + persist
  GET  /api/scout/verify/lead/{lead_id}   — fetch stored verified profile
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scout", tags=["Accurate Scout"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


class VerifyRequest(BaseModel):
    business_name: str
    city: str
    country: Optional[str] = "ca"
    website_url: Optional[str] = None


@router.post("/verify")
async def verify_business(body: VerifyRequest):
    """
    Run the full parallel verification pipeline on an ad-hoc business.
    Does NOT persist — use /verify/lead/{lead_id} to persist.
    """
    from services.accurate_scout import full_business_verify
    result = await full_business_verify(
        body.business_name, body.city,
        country=body.country or "ca",
        website_url=body.website_url,
    )
    return result


@router.post("/verify/lead/{lead_id}")
async def verify_and_persist(lead_id: str):
    """Verify an existing lead and persist the verified profile."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN}, {"_id": 0})
    if not lead:
        raise HTTPException(404, f"Lead '{lead_id}' not found")

    name = lead.get("business_name") or ""
    city = lead.get("city") or ""
    country = "ca" if ("ON" in (lead.get("address") or "") or lead.get("city", "").lower() in
                       ("toronto", "brampton", "mississauga", "ottawa", "vancouver", "calgary",
                        "edmonton", "montreal", "quebec")) else "us"
    website = lead.get("website_url") or lead.get("website") or ""

    from services.accurate_scout import full_business_verify, save_verified_profile
    result = await full_business_verify(name, city, country=country, website_url=website)
    await save_verified_profile(db, lead_id, result)
    return result


@router.get("/verify/lead/{lead_id}")
async def get_verified(lead_id: str):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    doc = await db.verified_lead_profile.find_one({"lead_id": lead_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "No verified profile — run POST /verify/lead first")
    return doc


@router.post("/reverify/run-now")
async def reverify_run_now():
    """Manually trigger the nightly re-verification cycle (admin/debug)."""
    from services.accurate_scout_cron import run_reverification_cycle
    return await run_reverification_cycle()
