"""
Customer Council-Gated Repair router (iter D-84 §4)
═════════════════════════════════════════════════════════════════════════════
The customer's "Initiate AUREM Repair" button (/my/website). Wraps the EXISTING
customer-repair primitives with a Council gate, rate-limit, scope-lock and
honest live-apply — NO new parallel repair system.

Flow (job phases: queued → analyzing → council_review → applying → verifying → done/failed):
  1. scope-lock — repair only the caller's own BIN/site (server-derived).
  2. rate-limit — max 3 repairs / BIN / 24h (collection-backed) → 429.
  3. analyzing — REAL audit via services.website_audit_service.real_audit.
  4. council_review — REAL services.council_deliberate.deliberate (CASL+QA).
  5. applying —
       • pixel INSTALLED (recent pixel_events for this BIN) → Council-approved
         safe DOM fixes (meta/title) written to `pending_pixel_patches`
         (tenant_id-scoped) — the pixel applies them live.
       • otherwise → LLM repair plan + Resend email (existing honest path).
  6. verifying / done — pixel reports back via patch_reports; plan path = ready.
  Rollback: on failure during apply, inserted patches are marked `revoked`.

Reuses: website_audit_service, auto_fix_engine, council_deliberate, and the
plan/email helpers already in customer_website_repair_router.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer/repair", tags=["customer · council repair"])

_db = None
RATE_LIMIT = 3
RATE_WINDOW_H = 24
JOBS = "repair_council_jobs"

PHASES = [
    ("queued", "Queued", "#7A7468"),
    ("analyzing", "Analysing your site", "#4A8FD4"),
    ("council_review", "Council reviewing fixes", "#9B6DD4"),
    ("applying", "Applying approved fixes", "#C9A227"),
    ("verifying", "Verifying", "#4AD4A0"),
    ("done", "Done", "#4AD4A0"),
]


def set_db(database) -> None:
    global _db
    _db = database


def _customer_bin(request: Request) -> str:
    from routers.missing_endpoints_router import _customer_bin as _shared
    return _shared(request)


def _customer_email(request: Request) -> str:
    from routers.missing_endpoints_router import _decode
    p = _decode(request)
    return p.get("email") or ""


def _db_or_503():
    if _db is None:
        raise HTTPException(503, "Database unavailable")
    return _db


async def _resolve_website(bin_id: str) -> str:
    db = _db
    ts = await db.tenant_settings.find_one({"tenant_id": bin_id}, {"_id": 0, "website_url": 1, "website": 1})
    site = (ts or {}).get("website_url") or (ts or {}).get("website") or ""
    if not site:
        last = await db.customer_scans.find_one(
            {"tenant_bin": bin_id}, sort=[("created_at", -1)], projection={"website": 1, "_id": 0})
        site = (last or {}).get("website", "")
    return (site or "").strip()


async def _pixel_installed(bin_id: str) -> bool:
    db = _db
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    try:
        n = await db.pixel_events.count_documents(
            {"$or": [{"tenant_id": bin_id}, {"business_id": bin_id}], "received_at": {"$gte": cutoff}})
        return n > 0
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════
# Background repair job
# ═══════════════════════════════════════════════════════════════════════════
async def _set(job_id: str, fields: Dict[str, Any]) -> None:
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db[JOBS].update_one({"job_id": job_id}, {"$set": fields})


async def _event(job_id: str, phase: str, message: str) -> None:
    await _db[JOBS].update_one({"job_id": job_id}, {"$push": {"events": {
        "at": datetime.now(timezone.utc).isoformat(), "phase": phase, "message": message}}})


def _phase(name: str) -> Dict[str, Any]:
    for p, label, color in PHASES:
        if p == name:
            return {"current_phase": p, "current_phase_label": label, "current_phase_color": color}
    return {"current_phase": name, "current_phase_label": name, "current_phase_color": "#7A7468"}


async def _run(job_id: str, bin_id: str, website: str, email: str) -> None:
    inserted_patch_ids: List[str] = []
    try:
        # ── analyzing ──
        await _set(job_id, {**_phase("analyzing"), "progress_pct": 15})
        await _event(job_id, "analyzing", f"Auditing {website}")
        from services.website_audit_service import real_audit
        audit = await real_audit(website)
        if not audit.get("ok"):
            await _set(job_id, {"status": "failed", **_phase("failed"),
                                "error": audit.get("error") or "audit_failed", "progress_pct": 100})
            await _event(job_id, "failed", f"Audit failed: {audit.get('error')}")
            return
        issues = audit.get("issues") or []
        await _set(job_id, {"score_before": audit.get("overall_score"), "issues": issues, "progress_pct": 35})
        await _event(job_id, "analyzing", f"Score {audit.get('overall_score')}/100 · {len(issues)} issues")

        # ── council review ──
        await _set(job_id, {**_phase("council_review"), "progress_pct": 50})
        from services.council_deliberate import deliberate
        verdict = await deliberate(
            action="customer_site_repair", agent="customer_repair_council",
            payload={"bin": bin_id, "website": website,
                     "issue_count": len(issues),
                     "issue_types": [i.get("auto_fix") or i.get("type") for i in issues][:20]},
            required=["casl", "qa"], advisory=["security"])
        approved = verdict.get("verdict", "APPROVED") == "APPROVED"
        await _event(job_id, "council_review", f"Council: {verdict.get('verdict')} (conf {verdict.get('confidence', 0)})")
        if not approved:
            await _set(job_id, {"status": "rejected", **_phase("failed"),
                                "council": verdict, "progress_pct": 100})
            await _event(job_id, "failed", "Council declined auto-fix — escalated to human review.")
            return

        # ── applying ──
        await _set(job_id, {**_phase("applying"), "council": verdict, "progress_pct": 70})
        from services.auto_fix_engine import run_auto_fixes
        fixes = await run_auto_fixes(_db, bin_id, issues)  # real fix plan items
        applied_live = 0
        pixel = await _pixel_installed(bin_id)

        if pixel:
            # Convert the safe DOM fixes into live pixel patches (tenant-scoped).
            for fx in fixes:
                if not fx.get("fixed"):
                    continue
                patch = _fix_to_patch(fx, bin_id)
                if not patch:
                    continue
                await _db.pending_pixel_patches.insert_one(patch)
                inserted_patch_ids.append(patch["id"])
                applied_live += 1
            await _event(job_id, "applying",
                         f"{applied_live} Council-approved patches queued to your live pixel"
                         if applied_live else "No auto-applyable patches; full plan emailed")
        # Always generate + email the human-readable plan too (honest fallback/record).
        try:
            from routers.customer_website_repair_router import _generate_repair_plan_via_llm, _email_repair_plan, _lookup_first_name
            plan = await _generate_repair_plan_via_llm(audit, email, website)
            await _set(job_id, {"repair_plan": plan})
            if email:
                er = await _email_repair_plan(email, website, plan, audit, first_name=await _lookup_first_name(email))
                await _event(job_id, "applying", f"Plan emailed to {email}" if er.get("ok") else f"Email skipped: {er.get('error')}")
        except Exception as e:  # noqa: BLE001
            logger.warning("[repair %s] plan/email step soft-failed: %s", job_id, e)

        # ── verifying / done ──
        await _set(job_id, {**_phase("verifying"), "applied_live": applied_live,
                            "pixel_installed": pixel, "progress_pct": 90})
        await _event(job_id, "verifying",
                     "Pixel will report patch application back to AUREM" if applied_live
                     else "Plan ready — apply the items and re-scan to update your score")
        await _set(job_id, {"status": "done", **_phase("done"), "progress_pct": 100,
                            "patch_ids": inserted_patch_ids,
                            "completed_at": datetime.now(timezone.utc).isoformat()})
        await _event(job_id, "done",
                     f"Repair complete — {applied_live} live fix(es) applied"
                     if applied_live else "Repair plan ready")
    except Exception as e:  # noqa: BLE001
        logger.exception("[repair %s] crashed: %s", job_id, e)
        # Rollback any live patches we queued
        for pid in inserted_patch_ids:
            try:
                await _db.pending_pixel_patches.update_one(
                    {"id": pid, "tenant_id": bin_id}, {"$set": {"status": "revoked", "revoked_reason": "job_failed"}})
            except Exception:
                pass
        await _set(job_id, {"status": "failed", **_phase("failed"), "error": str(e)[:400],
                            "rolled_back": len(inserted_patch_ids), "progress_pct": 100})
        await _event(job_id, "failed", f"Repair failed — {len(inserted_patch_ids)} patch(es) rolled back")


def _fix_to_patch(fx: Dict[str, Any], bin_id: str) -> Optional[Dict[str, Any]]:
    """Map a safe auto-fix into a tenant-scoped pending pixel patch.
    Only DOM-safe head injections are auto-applied; everything else stays in the plan."""
    ft = fx.get("fix_type")
    base = {"id": f"px_{uuid.uuid4().hex[:12]}", "tenant_id": bin_id,
            "status": "pending", "source": "council_repair", "failure_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat()}
    if ft == "add_meta_description":
        return {**base, "type": "meta", "selector": "head",
                "attrs": {"name": "description", "content": fx.get("fix_value", "")}}
    if ft == "add_page_title":
        return {**base, "type": "title", "selector": "head", "content": fx.get("fix_value", "")}
    if ft == "add_viewport":
        return {**base, "type": "meta", "selector": "head",
                "attrs": {"name": "viewport", "content": "width=device-width, initial-scale=1"}}
    return None  # other fixes → plan/email only (not auto-applied)


# ═══════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════
class InitiateBody(BaseModel):
    scan_id: Optional[str] = None


@router.get("/eligibility")
async def eligibility(request: Request) -> Dict[str, Any]:
    """Should the button be enabled? Enabled only if the site has open findings."""
    bin_id = _customer_bin(request)
    db = _db_or_503()
    last = await db.customer_scans.find_one(
        {"tenant_bin": bin_id}, sort=[("created_at", -1)],
        projection={"_id": 0, "issues": 1, "overall_score": 1, "score": 1, "website": 1, "created_at": 1})
    issues = (last or {}).get("issues") or []
    used = await db[JOBS].count_documents({
        "bin_id": bin_id,
        "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=RATE_WINDOW_H)).isoformat()}})
    return {
        "bin_id": bin_id,
        "eligible": bool(issues) and used < RATE_LIMIT,
        "open_findings": len(issues),
        "score": (last or {}).get("overall_score") or (last or {}).get("score"),
        "website": (last or {}).get("website"),
        "rate_used": used, "rate_limit": RATE_LIMIT,
        "reason": (None if issues else "No open findings — run a scan first")
                  if used < RATE_LIMIT else f"Daily repair limit reached ({RATE_LIMIT}/24h)",
    }


@router.post("/initiate")
async def initiate(body: InitiateBody, request: Request) -> Dict[str, Any]:
    bin_id = _customer_bin(request)
    email = _customer_email(request)
    db = _db_or_503()

    # rate-limit (scope-locked to this BIN)
    since = (datetime.now(timezone.utc) - timedelta(hours=RATE_WINDOW_H)).isoformat()
    used = await db[JOBS].count_documents({"bin_id": bin_id, "created_at": {"$gte": since}})
    if used >= RATE_LIMIT:
        raise HTTPException(429, f"Repair limit reached ({RATE_LIMIT}/24h). Try again later.")

    website = await _resolve_website(bin_id)
    if not website:
        raise HTTPException(400, "No website on file — set your site URL and run a scan first.")

    job_id = f"crj_{uuid.uuid4().hex[:14]}"
    doc = {
        "job_id": job_id, "bin_id": bin_id, "email": email, "website": website,
        "status": "running", **_phase("queued"), "progress_pct": 0,
        "score_before": None, "events": [], "repair_plan": [], "patch_ids": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db[JOBS].insert_one(doc)
    doc.pop("_id", None)
    asyncio.create_task(_run(job_id, bin_id, website, email))
    return {"ok": True, "job_id": job_id,
            "disclaimer": "Council-reviewed fixes apply live only on pixel-installed sites; "
                          "all other fixes arrive as an actionable plan by email."}


@router.get("/{job_id}")
async def status(job_id: str, request: Request) -> Dict[str, Any]:
    bin_id = _customer_bin(request)  # scope-lock: only own jobs
    db = _db_or_503()
    job = await db[JOBS].find_one({"job_id": job_id, "bin_id": bin_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Repair job not found")
    return job


print("[STARTUP] Customer Council Repair router loaded (§4)", flush=True)
