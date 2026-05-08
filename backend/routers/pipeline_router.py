"""
Pipeline Router — Full 10-Stage Autonomous Pipeline API
Endpoints for triggering, monitoring, aborting, and querying pipeline runs.
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Header, Body
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])

_db = None


def set_db(database):
    global _db
    _db = database
    from services.flow_coordinator import set_db as set_fc_db
    from services.shadow_mode import set_db as set_sm_db
    from services.gradual_rollout import set_db as set_gr_db
    set_fc_db(database)
    set_sm_db(database)
    set_gr_db(database)


async def _get_admin(authorization: str = Header(None)):
    """Require admin authentication."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    import jwt
    try:
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
        user_id = payload.get("user_id")
        if _db is not None and user_id:
            user = await _db.users.find_one({"id": user_id}, {"_id": 0})
            if user and (user.get("is_admin") or user.get("is_super_admin") or user.get("role") == "admin"):
                return user
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Admin access required")


# ═══════════════════════════════════════
# TRIGGER
# ═══════════════════════════════════════

@router.post("/trigger/{tenant_id}")
async def trigger_pipeline(
    tenant_id: str,
    body: dict = Body(default={}),
    admin=Depends(_get_admin),
):
    """Manually trigger the full 10-stage pipeline for a tenant."""
    trigger_type = body.get("trigger_type", "manual")
    from services.flow_coordinator import run_pipeline
    import asyncio

    # Check for already-running pipeline
    if _db is not None:
        active = await _db.pipeline_runs.find_one({
            "tenant_id": tenant_id,
            "final_status": "running",
        })
        if active:
            raise HTTPException(
                status_code=409,
                detail=f"Pipeline already running for {tenant_id} (run_id={active.get('run_id')})",
            )

    # Run pipeline in background so the HTTP request returns immediately
    async def _run():
        try:
            await run_pipeline(tenant_id, trigger=trigger_type)
        except Exception as e:
            logger.error(f"[PIPELINE] Background run error for {tenant_id}: {e}")

    asyncio.create_task(_run())

    return {
        "status": "triggered",
        "tenant_id": tenant_id,
        "trigger_type": trigger_type,
        "message": f"Pipeline triggered for {tenant_id}",
    }


# ═══════════════════════════════════════
# STATUS (current)
# ═══════════════════════════════════════

@router.get("/status/{tenant_id}")
async def get_pipeline_status(tenant_id: str, admin=Depends(_get_admin)):
    """Get the current/latest pipeline status for a tenant."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    run = await _db.pipeline_runs.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0},
        sort=[("started_at", -1)],
    )
    if not run:
        return {"tenant_id": tenant_id, "status": "no_runs", "message": "No pipeline runs found"}

    stages_list = run.get("stages", [])
    current_stage = run.get("last_stage", "unknown")
    current_status = run.get("last_status", "unknown")

    return {
        "tenant_id": tenant_id,
        "run_id": run.get("run_id"),
        "stage": current_stage,
        "status": current_status,
        "final_status": run.get("final_status"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "stages_completed": len(stages_list),
        "trigger": run.get("trigger"),
    }


# ═══════════════════════════════════════
# HISTORY (all tenants — admin only)
# Must come BEFORE /history/{tenant_id}
# ═══════════════════════════════════════

@router.get("/history/all")
async def get_all_pipeline_history(limit: int = 10, admin=Depends(_get_admin)):
    """Get last N pipeline runs across ALL tenants. Admin only."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    runs = await _db.pipeline_runs.find(
        {}, {"_id": 0}
    ).sort("started_at", -1).to_list(min(limit, 50))

    return {"runs": runs, "total": len(runs)}


# ═══════════════════════════════════════
# HISTORY (per tenant)
# ═══════════════════════════════════════

@router.get("/history/{tenant_id}")
async def get_pipeline_history(tenant_id: str, limit: int = 10, admin=Depends(_get_admin)):
    """Get last N pipeline runs for a specific tenant."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    runs = await _db.pipeline_runs.find(
        {"tenant_id": tenant_id}, {"_id": 0}
    ).sort("started_at", -1).to_list(min(limit, 50))

    return {"tenant_id": tenant_id, "runs": runs, "total": len(runs)}


# ═══════════════════════════════════════
# ABORT
# ═══════════════════════════════════════

@router.post("/abort/{run_id}")
async def abort_pipeline(run_id: str, admin=Depends(_get_admin)):
    """Emergency abort a running pipeline. Triggers rollback if closer already ran."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    run = await _db.pipeline_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.get("final_status") != "running":
        return {
            "status": "already_finished",
            "run_id": run_id,
            "final_status": run.get("final_status"),
        }

    # Check if closer stage already ran
    stages = run.get("stages", [])
    closer_ran = any(s.get("stage") == "closer" and s.get("status") == "completed" for s in stages)

    now = datetime.now(timezone.utc).isoformat()
    abort_status = "aborted_with_rollback" if closer_ran else "aborted"

    await _db.pipeline_runs.update_one(
        {"run_id": run_id},
        {"$set": {
            "final_status": abort_status,
            "aborted_at": now,
            "aborted_by": admin.get("email", "admin"),
        }, "$push": {"stages": {
            "stage": "abort",
            "status": abort_status,
            "data": {"closer_ran": closer_ran, "aborted_by": admin.get("email")},
            "timestamp": now,
        }}}
    )

    if closer_ran:
        tenant_id = run.get("tenant_id")
        if tenant_id:
            await _db.tenant_optimization_profiles.update_one(
                {"tenant_id": tenant_id},
                {"$set": {
                    "optimization_enabled": False,
                    "optimization_stage": "rolled_back",
                    "rollback_at": now,
                    "rollback_reasons": [f"Manual abort by {admin.get('email', 'admin')} after closer stage"],
                }}
            )

    return {
        "status": abort_status,
        "run_id": run_id,
        "closer_ran": closer_ran,
        "rollback_triggered": closer_ran,
    }


# ═══════════════════════════════════════
# ACTIVE RUNS
# ═══════════════════════════════════════

@router.get("/runs/active")
async def get_active_runs(admin=Depends(_get_admin)):
    """Get all currently running pipelines with current stage info."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    runs = await _db.pipeline_runs.find(
        {"final_status": "running"}, {"_id": 0}
    ).sort("started_at", -1).to_list(50)

    return {"active_runs": runs, "count": len(runs)}


# ═══════════════════════════════════════
# AGGREGATE STATS
# ═══════════════════════════════════════

@router.get("/stats")
async def get_pipeline_stats(admin=Depends(_get_admin)):
    """Get aggregate pipeline statistics."""
    from services.flow_coordinator import get_pipeline_stats
    stats = await get_pipeline_stats()
    return stats


# ═══════════════════════════════════════
# SHADOW MODE ENDPOINTS
# ═══════════════════════════════════════

@router.get("/shadow/{tenant_id}")
async def get_shadow_results(tenant_id: str, admin=Depends(_get_admin)):
    """Get shadow test results for a tenant (Gate 2)."""
    from services.shadow_mode import get_shadow_results
    return await get_shadow_results(tenant_id)


@router.post("/shadow/simulate/{tenant_id}")
async def simulate_shadow(tenant_id: str, body: dict = Body(default={}), admin=Depends(_get_admin)):
    """Simulate shadow test data for demo/testing."""
    from services.shadow_mode import simulate_shadow_test
    num = body.get("num_queries", 60)
    return await simulate_shadow_test(tenant_id, num_queries=num)


@router.post("/shadow/check/{tenant_id}")
async def check_shadow_exit(tenant_id: str, admin=Depends(_get_admin)):
    """Check if tenant should exit shadow mode (Gate 2 → Gate 3)."""
    from services.shadow_mode import check_shadow_exit_criteria
    return await check_shadow_exit_criteria(tenant_id)


# ═══════════════════════════════════════
# GRADUAL ROLLOUT ENDPOINTS
# ═══════════════════════════════════════

@router.get("/rollout/metrics/{tenant_id}")
async def get_rollout_metrics(tenant_id: str, days: int = 7, admin=Depends(_get_admin)):
    """Get rollout metrics for a tenant's current stage."""
    from services.gradual_rollout import get_rollout_metrics
    return await get_rollout_metrics(tenant_id, days=days)


@router.post("/rollout/check/{tenant_id}")
async def check_rollout_advancement(tenant_id: str, admin=Depends(_get_admin)):
    """Check if tenant should advance to next rollout stage."""
    from services.gradual_rollout import check_stage_advancement
    return await check_stage_advancement(tenant_id)


@router.get("/rollout/{tenant_id}")
async def get_rollout_status(tenant_id: str, admin=Depends(_get_admin)):
    """Get rollout timeline for a tenant (Gate 3)."""
    from services.gradual_rollout import get_rollout_timeline
    return await get_rollout_timeline(tenant_id)


# ═══════════════════════════════════════
# DEMO MODE — Investor Presentations
# ═══════════════════════════════════════

DEMO_LEADS = [
    {"name": "Sarah Chen", "city": "Mississauga", "score": 89, "source": "Instagram DM", "product": "AURA-GEN", "vip": True},
    {"name": "Mike Torres", "city": "Toronto", "score": 74, "source": "Website form", "product": "Skincare", "vip": False},
    {"name": "Jennifer Park", "city": "Oakville", "score": 67, "source": "Facebook Ad", "product": "", "vip": False},
    {"name": "David Kim", "city": "Brampton", "score": 82, "source": "WhatsApp inquiry", "product": "", "vip": False},
    {"name": "Lisa Wong", "city": "Etobicoke", "score": 91, "source": "Referral", "product": "", "vip": True},
]

DEMO_INVOICES = [
    {"invoice_id": "INV-DEMO-001", "amount": 349, "currency": "CAD", "status": "overdue", "days_overdue": 5},
    {"invoice_id": "INV-DEMO-002", "amount": 149, "currency": "CAD", "status": "sent", "days_overdue": 0},
    {"invoice_id": "INV-DEMO-003", "amount": 897, "currency": "CAD", "status": "draft", "days_overdue": 0},
]

DEMO_MESSAGES = [
    {"text": "Do you ship to Vancouver?", "from": "Customer via WhatsApp"},
    {"text": "What's the difference between the two products?", "from": "Customer via Email"},
    {"text": "Can I get a bulk discount?", "from": "Customer via Website Chat"},
]

DEMO_SITE_ISSUES = [
    {"type": "missing_meta", "description": "Missing meta description on homepage", "severity": "P1"},
    {"type": "missing_alt", "description": "Image alt text missing (3 images)", "severity": "P2"},
    {"type": "render_blocking", "description": "CSS render-blocking resource", "severity": "P2"},
    {"type": "duplicate_h1", "description": "H1 tag duplicate", "severity": "P1"},
]


@router.post("/demo/launch")
async def launch_demo(admin=Depends(_get_admin)):
    """Launch investor demo — seeds data, triggers pipeline with visual delays."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    import time
    tenant_id = f"demo_investor_{int(time.time())}"
    now = datetime.now(timezone.utc)

    # Seed leads
    for lead in DEMO_LEADS:
        await _db.leads.insert_one({
            "tenant_id": tenant_id,
            "name": lead["name"],
            "city": lead["city"],
            "score": lead["score"],
            "source": lead["source"],
            "product": lead["product"],
            "vip": lead["vip"],
            "status": "new",
            "created_at": now.isoformat(),
        })

    # Seed invoices (as orders for scout to find)
    from datetime import timedelta
    for inv in DEMO_INVOICES:
        created = now - timedelta(days=35) if inv["status"] == "overdue" else now - timedelta(days=3)
        await _db.orders.insert_one({
            "tenant_id": tenant_id,
            "order_id": inv["invoice_id"],
            "total": inv["amount"],
            "currency": inv["currency"],
            "status": "pending" if inv["status"] != "draft" else "draft",
            "created_at": created.isoformat(),
        })

    # Seed messages
    from datetime import timedelta
    for msg in DEMO_MESSAGES:
        await _db.messages.insert_one({
            "tenant_id": tenant_id,
            "text": msg["text"],
            "from": msg["from"],
            "status": "unanswered",
            "created_at": (now - timedelta(hours=3)).isoformat(),
        })

    # Seed site audit
    await _db.site_audits.insert_one({
        "tenant_id": tenant_id,
        "health_score": 62,
        "issues": DEMO_SITE_ISSUES,
        "created_at": now.isoformat(),
    })

    # Seed known fixes so architect/envoy have strategies
    for issue in DEMO_SITE_ISSUES:
        await _db.known_fixes.insert_one({
            "tenant_id": tenant_id,
            "fix_type": "pixel_css_fix",
            "validated": True,
            "success_rate": 0.95,
            "last_success": now.isoformat(),
        })

    return {
        "status": "seeded",
        "tenant_id": tenant_id,
        "seeded": {
            "leads": len(DEMO_LEADS),
            "invoices": len(DEMO_INVOICES),
            "messages": len(DEMO_MESSAGES),
            "site_issues": len(DEMO_SITE_ISSUES),
        },
        "message": f"Demo tenant {tenant_id} ready. Trigger pipeline next.",
    }


@router.post("/demo/run/{tenant_id}")
async def run_demo_pipeline(tenant_id: str, admin=Depends(_get_admin)):
    """Run the pipeline with visual delays between stages for live presentation."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not tenant_id.startswith("demo_investor_"):
        raise HTTPException(status_code=400, detail="Only demo tenants allowed")

    import asyncio
    import uuid

    run_id = f"demo_{str(uuid.uuid4())[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    # Initialize pipeline run
    await _db.pipeline_runs.insert_one({
        "run_id": run_id,
        "tenant_id": tenant_id,
        "trigger": "demo",
        "started_at": now,
        "stages": [],
        "final_status": "running",
        "is_demo": True,
    })

    async def _demo_stage(stage: str, status: str, data: dict, delay: float):
        await asyncio.sleep(delay)
        stage_entry = {
            "stage": stage,
            "status": status,
            "data": data,
            "error": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await _db.pipeline_runs.update_one(
            {"run_id": run_id},
            {"$push": {"stages": stage_entry},
             "$set": {"last_stage": stage, "last_status": status,
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    async def _run_demo():
        try:
            await _demo_stage("scout", "running", {}, 0)
            await _demo_stage("scout", "completed", {"findings": 5, "leads": 5, "invoices_overdue": 1, "messages": 3, "site_score": 62}, 2.0)

            await _demo_stage("architect", "running", {}, 0)
            await _demo_stage("architect", "completed", {"planned": 5, "p1_count": 3, "p2_count": 2, "strategies": ["queue_outreach", "send_reminder", "draft_ora_response", "pixel_css_fix"]}, 2.0)

            await _demo_stage("risk_gate", "running", {}, 0)
            await _demo_stage("risk_gate", "passed", {"risk": "GREEN", "score": 2, "checks": ["new_tenant"]}, 1.0)

            await _demo_stage("envoy", "running", {}, 0)
            await _demo_stage("envoy", "completed", {"actions": 5, "auto_approved": 4, "needs_human": 1}, 2.0)

            await _demo_stage("human_loop", "running", {}, 0)
            await _demo_stage("human_loop", "completed", {"approved": 5, "pending": 0, "mode": "auto_approved_demo"}, 1.0)

            await _demo_stage("shadow_test", "running", {}, 0)
            await _demo_stage("shadow_test", "passed", {"tested": 1, "skipped": 4, "reason": "known_validated"}, 0.5)

            await _demo_stage("closer", "running", {}, 0)
            await _demo_stage("closer", "completed", {
                "executed": 5,
                "round_1": ["5 leads scored", "1 invoice reminder", "3 messages drafted"],
                "round_2": ["4 SEO fixes applied"],
                "all_success": True,
            }, 3.0)

            await _demo_stage("origin_lock", "running", {}, 0)
            await _demo_stage("origin_lock", "completed", {"anchored": 5, "phase": "phase_2_locked"}, 2.0)

            await _demo_stage("verifier", "running", {}, 0)
            await _demo_stage("verifier", "completed", {"verified": 5, "failed": 0, "all_verified": True}, 2.0)

            await _demo_stage("learn", "running", {}, 0)
            await _demo_stage("learn", "completed", {"updates": 5, "knowledge_base_updated": True}, 1.0)

            # Finalize
            await _db.pipeline_runs.update_one(
                {"run_id": run_id},
                {"$set": {
                    "final_status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "demo_summary": {
                        "leads_scored": 5,
                        "vip_flagged": 2,
                        "invoice_reminders": 1,
                        "seo_fixes": 4,
                        "messages_drafted": 3,
                        "ai_cost": "$0 (free model rotation)",
                    }
                }}
            )
        except Exception as e:
            logger.error(f"[DEMO] Pipeline error: {e}")
            await _db.pipeline_runs.update_one(
                {"run_id": run_id},
                {"$set": {"final_status": "error", "error": str(e)}}
            )

    asyncio.create_task(_run_demo())

    return {"status": "running", "run_id": run_id, "tenant_id": tenant_id}


@router.get("/demo/progress/{run_id}")
async def get_demo_progress(run_id: str, admin=Depends(_get_admin)):
    """Poll demo pipeline progress — returns stages completed so far."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    run = await _db.pipeline_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Demo run not found")

    return run


@router.post("/demo/cleanup/{tenant_id}")
async def cleanup_demo(tenant_id: str, admin=Depends(_get_admin)):
    """Remove all demo tenant data cleanly."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")
    if not tenant_id.startswith("demo_investor_"):
        raise HTTPException(status_code=400, detail="Only demo tenants can be cleaned")

    deleted = {}
    for coll in ["leads", "orders", "messages", "site_audits", "known_fixes",
                 "pipeline_runs", "pipeline_completions", "origin_commits",
                 "auto_heal_log", "tenant_optimization_profiles",
                 "shadow_test_results", "rollout_metrics",
                 "approval_queue", "approval_patterns"]:
        result = await _db[coll].delete_many({"tenant_id": tenant_id})
        if result.deleted_count > 0:
            deleted[coll] = result.deleted_count

    return {"status": "cleaned", "tenant_id": tenant_id, "deleted": deleted}
