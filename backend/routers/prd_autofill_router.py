"""
PRD Auto-Fill router — iter 282al-8 (Prompt 11).

  POST /api/awb/prd-autofill   body: {lead: {...}}      → full PRD
  POST /api/awb/prd-preview    body: {lead_id: "..."}   → PRD for stored lead
  GET  /api/awb/prd-health
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.prd_auto_fill import auto_fill_prd, prd_summary_for_llm

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server  # noqa: WPS433
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


class LeadIn(BaseModel):
    lead: dict


class LeadIdIn(BaseModel):
    lead_id: str


@router.get("/api/awb/prd-health")
async def prd_health() -> dict:
    return {"ok": True, "service": "prd_auto_fill",
            "ts": datetime.now(timezone.utc).isoformat()}


@router.post("/api/awb/prd-autofill")
async def prd_autofill(payload: LeadIn) -> dict:
    if not isinstance(payload.lead, dict):
        raise HTTPException(status_code=400, detail="lead must be an object")
    prd = auto_fill_prd(payload.lead)
    return {
        "ok": True,
        "prd": prd,
        "llm_block": prd_summary_for_llm(prd),
    }


@router.post("/api/awb/prd-preview")
async def prd_preview(payload: LeadIdIn) -> dict:
    db = _get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="db unavailable")
    if not (payload.lead_id or "").strip():
        raise HTTPException(status_code=400, detail="lead_id required")
    try:
        lead = await db.campaign_leads.find_one(
            {"lead_id": payload.lead_id},
            projection={"_id": 0},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db error: {e}")
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    prd = auto_fill_prd(lead)
    return {
        "ok": True,
        "lead_id": payload.lead_id,
        "prd": prd,
        "llm_block": prd_summary_for_llm(prd),
    }
