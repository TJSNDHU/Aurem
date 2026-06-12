"""
Admin endpoints for the 3 platform-spine services (iter 296).
Mounts at /api/admin/platform/*

  GET  /a2a/tasks?status=&limit=          — recent tasks
  GET  /a2a/chain/{chain_id}              — full chain
  POST /a2a/test-handoff                  — emits a Scout→Architect→Envoy→Closer demo
  GET  /council/recent?limit=             — last decisions
  POST /council/deliberate                — manual deliberation (debug + Founders Console)
  GET  /council/escalations               — pending escalations
  POST /council/resolve/{decision_id}     — TJ approves/vetos an escalation
  GET  /ora/feed?limit=                   — live feed
  GET  /ora/patterns?limit=               — pattern library
  GET  /ora/stats                         — outcome breakdown
  POST /ora/test-log                      — emit a test action
  GET  /spine/health                      — single endpoint Founders Console reads
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/platform", tags=["Platform Spine"])


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin authentication required")
    import jwt
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"],
        )
        if payload.get("is_admin") or payload.get("role") == "admin" or payload.get("email"):
            return payload
        raise HTTPException(403, "Admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


# ── A2A ─────────────────────────────────────────────────────────────────────
@router.get("/a2a/tasks")
async def a2a_tasks(status: Optional[str] = None, limit: int = 50,
                    authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.a2a_task_queue import tq
    return {"tasks": await tq.recent(limit=limit, status=status), "stats": await tq.stats()}


@router.get("/a2a/chain/{chain_id}")
async def a2a_chain(chain_id: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.a2a_task_queue import tq
    return {"chain": await tq.chain(chain_id)}


@router.post("/a2a/test-handoff")
async def a2a_test_handoff(authorization: Optional[str] = Header(None)):
    """Emit a Scout→Architect→Envoy→Closer demo chain."""
    _verify_admin(authorization)
    from services.a2a_task_queue import tq
    t1 = await tq.submit("scout", "architect", "build_site",
                         {"lead_id": "demo-lead-001", "domain": "example.com", "niche": "auto-repair"})
    chain_id = (await tq.chain(t1))[0]["chain_id"]
    t2 = await tq.submit("architect", "envoy", "send_outreach",
                         {"lead_id": "demo-lead-001", "site_url": "https://demo.aurem.live"},
                         parent_task_id=t1)
    t3 = await tq.submit("envoy", "closer", "follow_up",
                         {"lead_id": "demo-lead-001", "channel": "email"},
                         parent_task_id=t2)
    return {"ok": True, "chain_id": chain_id, "tasks": [t1, t2, t3]}


# ── Council ─────────────────────────────────────────────────────────────────
class DeliberatePayload(BaseModel):
    action_kind: str
    payload: dict = {}
    cost_usd: float = 0.0
    llm_voters: Optional[bool] = None


@router.get("/council/recent")
async def council_recent(limit: int = 50, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.council import council
    return {"decisions": await council.recent(limit=limit)}


@router.post("/council/deliberate")
async def council_deliberate(body: DeliberatePayload, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.council import council
    return await council.deliberate(
        action_kind=body.action_kind,
        payload=body.payload,
        cost_usd=body.cost_usd,
        llm_voters=body.llm_voters,
    )


@router.get("/council/escalations")
async def council_escalations(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.council import council
    return {"pending": await council.pending_escalations()}


@router.post("/council/resolve/{decision_id}")
async def council_resolve(decision_id: str, action: str = "approve",
                          authorization: Optional[str] = Header(None)):
    user = _verify_admin(authorization)
    if action not in ("approve", "veto"):
        raise HTTPException(400, "action must be approve|veto")
    import server
    db = getattr(server, "db", None)
    if db is None:
        raise HTTPException(503, "DB unavailable")
    await db.pending_escalations.update_one(
        {"decision_id": decision_id, "status": "pending"},
        {"$set": {"status": f"resolved_{action}",
                  "resolved_by": user.get("email", "unknown"),
                  "resolved_at": datetime.now(timezone.utc).isoformat()}},
    )
    await db.council_decisions.update_one(
        {"decision_id": decision_id},
        {"$set": {"founder_override": action,
                  "decision": "approve" if action == "approve" else "veto"}},
    )
    return {"ok": True, "action": action}


# ── ORA Learning ────────────────────────────────────────────────────────────
@router.get("/ora/feed")
async def ora_feed(limit: int = 50, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.ora_learning import ora
    return {"feed": await ora.feed(limit=limit)}


@router.get("/ora/patterns")
async def ora_patterns(limit: int = 50, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.ora_learning import ora
    return {"patterns": await ora.patterns(limit=limit)}


@router.get("/ora/stats")
async def ora_stats(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.ora_learning import ora
    return await ora.stats()


@router.post("/ora/test-log")
async def ora_test_log(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.ora_learning import ora
    aid = await ora.log_action(
        agent="scout", action="enrich_lead",
        input_data={"lead_id": "demo-lead-001", "domain": "example.com"},
        output_data={"success": True, "phone_confidence": "HIGH"},
        cost_usd=0.0001,
    )
    await ora.update_outcome(aid, "success")
    return {"ok": True, "action_id": aid}


# ── Spine combined health ──────────────────────────────────────────────────
@router.get("/spine/health")
async def spine_health(authorization: Optional[str] = Header(None)):
    """One call for Founders Console / Admin HUD."""
    _verify_admin(authorization)
    from services.a2a_task_queue import tq
    from services.council import council
    from services.ora_learning import ora
    a2a = await tq.stats()
    cl = await council.pending_escalations()
    o = await ora.stats()
    return {
        "a2a": {
            "stats": a2a,
            "queued": a2a.get("queued", 0),
            "in_progress": a2a.get("in_progress", 0),
            "complete": a2a.get("complete", 0),
            "failed": a2a.get("failed", 0),
            "vetoed": a2a.get("vetoed", 0),
        },
        "council": {
            "pending_escalations": len(cl),
            "escalations": cl[:5],
        },
        "ora": o,
        "ts": datetime.now(timezone.utc).isoformat(),
    }



# ── Channel-Gating Refresh (iter 297) ───────────────────────────────────────
@router.post("/maintenance/refresh-channel-gating")
async def refresh_channel_gating_endpoint(
    dry: bool = False,
    limit: int = 0,
    authorization: Optional[str] = Header(None),
):
    """Re-run channel_gating rules over all verified leads (no rescrape)."""
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        raise HTTPException(503, "DB unavailable")
    from scripts.refresh_channel_gating import refresh_channel_gating
    return await refresh_channel_gating(db, dry_run=bool(dry), limit=int(limit))


@router.get("/maintenance/refresh-channel-gating/history")
async def refresh_channel_gating_history(
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        return {"runs": []}
    runs = await db.channel_gating_refresh_log.find(
        {}, {"_id": 0, "sample_diffs": 0},
    ).sort("completed_at", -1).limit(int(limit)).to_list(int(limit))
    return {"runs": runs}



# ── Auto Website Builder (iter 297 — P1 #4) ─────────────────────────────────
@router.post("/website-builder/build/{lead_id}")
async def website_builder_build(lead_id: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        raise HTTPException(503, "DB unavailable")
    from services.auto_website_builder import build_site_for_lead
    return await build_site_for_lead(db, lead_id)


@router.post("/website-builder/run-batch")
async def website_builder_batch(limit: int = 3, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        raise HTTPException(503, "DB unavailable")
    from services.auto_website_builder import build_batch
    return await build_batch(db, limit=int(limit))


@router.get("/website-builder/list")
async def website_builder_list(limit: int = 50, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        return {"sites": []}
    from services.auto_website_builder import list_sites
    return {"sites": await list_sites(db, limit=int(limit))}


@router.post("/website-builder/themes/{slug}")
async def admin_themes_for_site(slug: str, authorization: Optional[str] = Header(None)):
    """Admin: pre-discover themes for a site (Cockpit 'Pick Theme' button)."""
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        raise HTTPException(503, "DB unavailable")
    site = await db.auto_built_sites.find_one({"slug": slug}, {"_id": 0, "lead_id": 1, "niche": 1})
    if not site:
        raise HTTPException(404, "site not found")
    lead = await db.campaign_leads.find_one(
        {"lead_id": site["lead_id"], "business_id": FOUNDER_BIN},
        {"_id": 0, "city": 1, "niche": 1, "category": 1},
    ) or {}
    biz_type = site.get("niche") or lead.get("niche") or lead.get("category") or "service business"
    city = lead.get("city") or "Toronto"
    from services.awb_themes import discover_themes
    themes = await discover_themes(business_type=biz_type, city=city, n=4)
    if themes:
        await db.auto_built_sites.update_one(
            {"slug": slug},
            {"$set": {"theme_options": themes, "theme_options_at": datetime.now(timezone.utc).isoformat()}},
        )
    return {"slug": slug, "n": len(themes), "themes": themes}



@router.get("/website-builder/preview/{site_id}")
async def website_builder_preview(site_id: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        raise HTTPException(503, "DB unavailable")
    from services.auto_website_builder import get_site_html
    html = await get_site_html(db, site_id)
    if not html:
        raise HTTPException(404, "site not found or not rendered yet")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)



@router.get("/website-builder/cockpit")
async def website_builder_cockpit(authorization: Optional[str] = Header(None)):
    """Aggregated state for AdminShell Cockpit tile."""
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        return {"counters": {}, "recent": [], "queue_size": 0}

    from services.cloudflare_dns import is_configured as cf_ready

    pipe = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    counters = {row["_id"]: row["n"] async for row in db.auto_built_sites.aggregate(pipe)}

    recent = await db.auto_built_sites.find(
        {}, {"_id": 0, "rendered_html": 0, "gemini_draft": 0, "claude_refined": 0},
    ).sort("created_at", -1).limit(5).to_list(5)

    # Queue: leads eligible for AWB but not yet built
    built_lead_ids = await db.auto_built_sites.distinct("lead_id")
    queue_size = await db.campaign_leads.count_documents({
        "business_id": FOUNDER_BIN,
        "lead_id": {"$nin": built_lead_ids or []},
        "$or": [
            {"website": {"$in": [None, ""]}},
            {"verification.has_website": False},
            {"website_quality": {"$in": ["poor", "broken", None]}},
        ],
    })

    return {
        "counters": {
            "total": sum(counters.values()),
            "drafted": counters.get("drafted", 0) + counters.get("drafting", 0),
            "rendered": counters.get("rendered", 0),
            "published": counters.get("published", 0),
            "deployed": counters.get("deployed", 0),
            "vetoed": counters.get("vetoed", 0),
            "failed": counters.get("failed", 0),
        },
        "recent": recent,
        "queue_size": queue_size,
        "cloudflare_ready": cf_ready(),
        "r2_ready": _r2_ready(),
    }


@router.get("/website-builder/domains")
async def website_builder_domains(authorization: Optional[str] = Header(None)):
    """Aggregate registered customer domains + business names for the
    AWB Cockpit Domains tab. Iter 312."""
    _verify_admin(authorization)
    import server
    db = getattr(server, "db", None)
    if db is None:
        return {"domains": [], "count": 0}

    rows = await db.customer_domains.find({}, {"_id": 0}) \
        .sort("registered_at", -1).limit(200).to_list(200)
    if not rows:
        return {"domains": [], "count": 0}

    lead_ids = list({r.get("lead_id") for r in rows if r.get("lead_id")})
    leads: Dict[str, Optional[str]] = {}
    if lead_ids:
        async for L in db.campaign_leads.find(
            {"id": {"$in": lead_ids}, "business_id": FOUNDER_BIN},
            {"_id": 0, "id": 1, "business_name": 1},
        ):
            leads[L["id"]] = L.get("business_name")

    out = []
    for r in rows:
        out.append({
            **r,
            "business_name": leads.get(r.get("lead_id")),
            "charged_cad": r.get("charged_cad")
                or float(os.environ.get("AUREM_DOMAIN_PRICE_CAD", "29")),
        })
    # Compute expiring buckets
    now = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc)
    buckets = {"7d": [], "14d": [], "30d": []}
    for r in out:
        exp_str = r.get("expires_at") or ""
        try:
            from datetime import datetime as _dt
            exp = _dt.fromisoformat(str(exp_str).replace("Z", "+00:00"))
            days = (exp - now).days
            r["days_until_expiry"] = max(0, days)
            if 0 <= days <= 7:
                buckets["7d"].append(r["domain"])
            elif days <= 14:
                buckets["14d"].append(r["domain"])
            elif days <= 30:
                buckets["30d"].append(r["domain"])
        except Exception:
            r["days_until_expiry"] = None
    return {"domains": out, "count": len(out),
             "expiring": buckets}


def _r2_ready() -> bool:
    try:
        from services.cloudflare_r2 import is_configured
        return is_configured()
    except Exception:
        return False


# ── AWB Auto-Pilot (iter 299) ───────────────────────────────────────────────
class AutoPilotPayload(BaseModel):
    enabled: bool
    batch_size: Optional[int] = None
    interval_minutes: Optional[int] = None


@router.get("/website-builder/autopilot")
async def autopilot_get(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.awb_autopilot import autopilot
    return await autopilot.get_state()


@router.post("/website-builder/autopilot")
async def autopilot_set(body: AutoPilotPayload, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.awb_autopilot import autopilot
    return await autopilot.set_enabled(
        body.enabled,
        batch_size=body.batch_size,
        interval_minutes=body.interval_minutes,
    )


@router.post("/website-builder/autopilot/run-now")
async def autopilot_trigger(batch_size: Optional[int] = None,
                            authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.awb_autopilot import autopilot
    return await autopilot.trigger_now(batch_size=batch_size)


@router.get("/website-builder/autopilot/history")
async def autopilot_history(limit: int = 20,
                            authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.awb_autopilot import autopilot
    return {"runs": await autopilot.history(limit=limit)}
