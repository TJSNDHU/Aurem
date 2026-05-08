"""
iter 282al-15 — Site QA admin router
====================================
Tiny router that exposes the Pillars Map chip health for test-lab.ai
site QA + a morning-brief summary endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/site-qa", tags=["Site QA"])

_db = None


def set_db(db):
    global _db
    _db = db


@router.get("/health")
async def site_qa_health() -> Dict[str, Any]:
    """Pillars-map chip endpoint. GREEN/YELLOW/GREY based on last 5 runs."""
    from services.site_qa_service import get_qa_health
    return await get_qa_health(_db)


@router.get("/brief")
async def site_qa_brief() -> Dict[str, Any]:
    """Morning-brief numbers: audits / verified / sent / paid / failed (today)."""
    if _db is None:
        return {"audits": 0, "verified": 0, "sent": 0, "paid": 0, "failed": 0}
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        audits   = await _db.site_audits.count_documents({"audit_ts": {"$gte": since}})
    except Exception:
        audits = 0
    try:
        verified = await _db.site_test_results.count_documents(
            {"ts": {"$gte": since}, "failed": 0},
        )
    except Exception:
        verified = 0
    try:
        failed   = await _db.site_test_results.count_documents(
            {"ts": {"$gte": since}, "failed": {"$gt": 0}},
        )
    except Exception:
        failed = 0
    try:
        sent     = await _db.sites_sent.count_documents({"ts": {"$gte": since}})
    except Exception:
        sent = 0
    try:
        paid     = await _db.campaign_leads.count_documents(
            {"repair_paid_at": {"$gte": since}},
        )
    except Exception:
        paid = 0
    try:
        second_chance = await _db.campaign_leads.count_documents(
            {"second_chance_sent_at": {"$gte": since}},
        )
    except Exception:
        second_chance = 0
    return {
        "audits": audits, "verified": verified, "sent": sent,
        "paid": paid, "second_chance": second_chance, "failed": failed,
    }
