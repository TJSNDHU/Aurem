"""
AUREM Scout Source-Stats router (iter 322n)
============================================
Admin-only endpoint that powers the "Source Attribution" dashboard.
Reads the `scout_source_runs` collection populated by
`services/total_scout.py` and returns a per-source rollup for the
last N days (default 7).

Routes
------
- ``GET /api/admin/scout/source-stats?days=7``  → rollup dict
- ``POST /api/admin/scout/run-now``             → fire a one-shot scout
                                                   (admin smoke test only)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict

import jwt
from fastapi import APIRouter, HTTPException, Request

from services.total_scout import discover_leads_total_scout, get_source_stats


router = APIRouter(prefix="/api/admin/scout", tags=["admin-scout"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            token,
            os.environ.get("JWT_SECRET", "aurem_default_secret"),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin") or
            payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")
    return payload


@router.get("/source-stats")
async def source_stats(request: Request, days: int = 7) -> Dict[str, Any]:
    """Return last-N-days rollup of which scout source delivered what.

    Useful for the admin dashboard to see at-a-glance whether Yelp,
    Google Places, OSM, YellowPages, Tavily or DuckDuckGo is pulling
    its weight — and where to invest.
    """
    _require_admin(request)
    days = max(1, min(int(days), 90))
    return await get_source_stats(_db, days=days)


@router.post("/qa-no-website")
async def qa_no_website(request: Request) -> Dict[str, Any]:
    """Build prospect site → augment claim CTA + pixel → run A2A 6-pt auto-tests.

    Body: ``{ "lead_id": "...", "save": true }``

    Reuses existing `auto_website_builder.build_site_for_lead` (idempotent —
    won't rebuild if already exists). Retries failed checks up to 2× per spec.
    """
    _require_admin(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    lead_id = (body.get("lead_id") or "").strip()
    save = bool(body.get("save", True))
    if not lead_id:
        raise HTTPException(400, "lead_id required")
    if _db is None:
        raise HTTPException(503, "database unavailable")

    from services.prospect_site_qa import build_and_qa_no_website
    result = await build_and_qa_no_website(_db, lead_id, save=save)
    if not result.get("ok", False) and "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/qa-has-website")
async def qa_has_website(request: Request) -> Dict[str, Any]:
    """Run full QA pipeline for a single `has_website` lead.

    Body: ``{ "lead_id": "...", "url": "..." (override), "save": true }``

    Performs: audit → render blast artifacts → verify report URL →
    A2A 5-point checklist. Returns ``ready_to_blast: True`` only when
    all 5 checks pass.
    """
    _require_admin(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    lead_id = (body.get("lead_id") or "").strip()
    save = bool(body.get("save", True))
    if not lead_id:
        raise HTTPException(400, "lead_id required")
    if _db is None:
        raise HTTPException(503, "database unavailable")
    lead = await _db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "lead not found")
    url = (body.get("url") or lead.get("website")
           or lead.get("website_url") or "").strip()

    from services.website_qa import (
        audit_website, render_blast_artifacts,
        verify_report_url, qa_has_website_checklist,
    )
    audit = await audit_website(url)
    await render_blast_artifacts(lead, audit)
    lead["report_url_status_ok"] = await verify_report_url(lead.get("report_url", ""))
    checklist = qa_has_website_checklist(lead, audit)

    if save:
        try:
            await _db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "website_audit": audit,
                    "blast_email_subject": lead.get("blast_email_subject"),
                    "blast_email_body": lead.get("blast_email_body"),
                    "blast_sms_body": lead.get("blast_sms_body"),
                    "blast_retell_script": lead.get("blast_retell_script"),
                    "report_url": lead.get("report_url"),
                    "qa_checklist": checklist,
                    "qa_ready_to_blast": checklist["passed"],
                    "qa_at": datetime.now(timezone.utc),
                }},
            )
        except Exception:
            pass

    return {
        "lead_id": lead_id,
        "audit": audit,
        "lead_artifacts": {
            "report_url": lead.get("report_url"),
            "email_subject": lead.get("blast_email_subject"),
            "sms_body": lead.get("blast_sms_body"),
            "retell_script": lead.get("blast_retell_script"),
        },
        "checklist": checklist,
        "ready_to_blast": checklist["passed"],
    }


@router.post("/sort")
async def sort_now(request: Request) -> Dict[str, Any]:
    """Run lead-sort + validation over the last Scout batch (or a body of leads).

    Body:
        {
          "leads": [...],     # optional — if omitted, pulls last 100 from
                              # campaign_leads where sort_queue is missing
        }
    """
    _require_admin(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    leads = body.get("leads") or []
    if not leads and _db is not None:
        cursor = _db.campaign_leads.find(
            {"sort_queue": {"$exists": False}},
            {"_id": 0},
        ).sort("created_at", -1).limit(100)
        async for L in cursor:
            leads.append(L)

    from services.lead_sort import sort_leads
    queues = await sort_leads(leads, db=_db)
    return {
        "queued": {k: len(v) for k, v in queues.items()},
        "sample": {
            k: [{"name": L.get("name") or L.get("business_name"),
                 "score": L.get("score"),
                 "industry": L.get("industry")} for L in v[:3]]
            for k, v in queues.items()
        },
    }


@router.post("/run-now")
async def run_now(request: Request) -> Dict[str, Any]:
    """Smoke-test endpoint — admin can fire a one-shot Total-Scout run
    from the dashboard. Body: ``{query, location, limit?}``.
    """
    _require_admin(request)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    query = (body.get("query") or "").strip()
    location = (body.get("location") or "").strip()
    if not query or not location:
        raise HTTPException(400, "query and location are required")
    limit = max(1, min(int(body.get("limit") or 10), 50))
    return await discover_leads_total_scout(
        query, location, limit=limit, db=_db,
    )


@router.post("/enrich-deep")
async def enrich_deep(request: Request) -> Dict[str, Any]:
    """Fire on-demand Dark Scout deep-intel on ONE lead.

    Body schema:
        {
          "lead_id":  str,                  # required
          "lead":     {business_name, city, website, ...},  # required
          "preset":   "brand_monitor"|"competitor_intel"|
                      "breach_detection"|"threat_landscape",
          "tenant_id": str (optional)
        }

    Returns the persisted intel doc. Designed for admin click-through
    on Sovereign-Gold leads — NOT for batch auto-fire (LLM cost).
    """
    payload = _require_admin(request)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    lead_id = (body.get("lead_id") or "").strip()
    lead = body.get("lead") or {}
    if not lead_id or not isinstance(lead, dict) or not lead.get("business_name"):
        raise HTTPException(400, "lead_id and lead.business_name are required")
    preset = (body.get("preset") or "brand_monitor").strip()
    tenant_id = (body.get("tenant_id") or payload.get("tenant_id") or "system").strip()

    from services.lead_deep_intel import enrich_lead
    return await enrich_lead(
        _db,
        lead_id=lead_id, lead=lead, preset=preset, tenant_id=tenant_id,
    )


@router.get("/deep-intel/{lead_id}")
async def deep_intel_for_lead(lead_id: str, request: Request) -> Dict[str, Any]:
    """Read-side: fetch the cached deep-intel doc for a lead.
    Returns 404 when no enrichment has been run yet."""
    _require_admin(request)
    from services.lead_deep_intel import get_deep_intel
    doc = await get_deep_intel(_db, lead_id)
    if doc is None:
        raise HTTPException(404, "no_intel_yet")
    return doc


# ─── Agent A2A Self-Heal admin actions (iter 322o) ─────────────────────
@router.get("/wedges")
async def list_wedged_agents(request: Request) -> Dict[str, Any]:
    """Admin read-side: which agents are currently judged wedged?"""
    _require_admin(request)
    from services.agent_wedge_detector import (
        detect_wedged_agents, get_wedge_stats,
    )
    wedged = await detect_wedged_agents(_db)
    stats = await get_wedge_stats(_db, hours=24)
    return {"wedged_now": wedged, "stats_24h": stats}


@router.post("/heal-agent")
async def manual_heal_agent(request: Request) -> Dict[str, Any]:
    """Admin override — force a heal cascade on one agent.

    Body: ``{ "agent_id": str }``. Bypasses the cooldown so an admin
    can clear a stuck "boot-XXX · NNm" pill on demand.
    """
    _require_admin(request)
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    agent_id = (body.get("agent_id") or "").strip()
    if not agent_id:
        raise HTTPException(400, "agent_id is required")
    from services.agent_wedge_detector import auto_heal_agent
    return await auto_heal_agent(_db, agent_id, force=True)
