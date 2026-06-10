"""
Customer Website Status + Repair — /my/website page backend.

Two feature areas in one router:
  A. Pixel status  → GET /api/customer/pixel/status
  B. Scan + Repair → POST /api/customer/website/scan
                     POST /api/customer/website/repair/start
                     GET  /api/customer/website/repair/status/{job_id}

iter D-75 honesty rewrite
-------------------------
Pre-D-75, `_run_repair_job` was a 90-second timer that:
  • added `rng.randint(24, 38)` to the scan score (fake improvement),
  • generated random commit hashes via `hashlib.sha1(rng.random())`,
  • emitted fake events ("Canary rollout to 10%", "SOC 2 audit-chain
    appended", "42/42 assertions passed"),
  • built a hardcoded "improvements" array via `lcp * 0.35` math
  • marked the job `status: completed` without ever touching the
    customer's website.

D-75 replaced that with HONEST work:
  • Re-runs the real `website_audit_service.real_audit()` probe.
  • Calls `services.llm_gateway_v2.route()` (DeepSeek V3.1 via
    OpenRouter — same path as the autonomous CTO repair agent which
    D-73 confirmed is working) to generate per-issue actionable fix
    proposals with real DIFF snippets.
  • Optionally emails the plan to the customer via Resend (best-effort).
  • Saves status `plan_ready_for_customer` — NOT `completed`, because
    we cannot apply fixes to the customer's server. `score_after`
    stays `None` until the customer applies the fixes AND triggers a
    re-scan.
  • No random deltas, no fake commit hashes, no fake "deployed".
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import asyncio
import random
import logging
import hashlib
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer", tags=["Customer Website"])

db = None


def set_db(database):
    global db
    db = database


# ─────────────────────── Auth dependency ───────────────────────
# Reuse the platform user token verification
def _verify_platform_user(request: Request) -> dict:
    try:
        import jwt
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(401, "missing bearer token")
        token = auth[7:]
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise HTTPException(500, "JWT_SECRET not configured")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        return decoded  # should have email, role
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _resolve_tenant(user: dict) -> dict:
    """Resolve the platform_users doc from the JWT email + normalize BIN field."""
    if db is None:
        raise HTTPException(503, "service not ready")
    email = (user.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "token missing email")
    doc = await db.platform_users.find_one({"email": email})
    if not doc:
        raise HTTPException(404, "user not found")
    # Normalize the BIN field — handle legacy field names
    doc["bin"] = doc.get("bin") or doc.get("business_id") or doc.get("business_bin") or doc.get("tenant_id")
    return doc


# ═══════════════════════════════════════════════════════════════
# PHASE A — Pixel status badge
# ═══════════════════════════════════════════════════════════════

@router.get("/pixel/status")
async def pixel_status(request: Request, user: dict = Depends(_verify_platform_user)):
    """
    Returns live pixel online/offline state for the authenticated client.
    ONLINE = at least one pixel_event within the last 15 minutes for this tenant.
    """
    tenant = await _resolve_tenant(user)
    bin_id = tenant.get("bin")
    email = tenant.get("email")

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    cutoff_iso = cutoff.isoformat()

    # Match by either tenant_id (bin) OR email — pixel script may report either
    query = {
        "$or": [
            {"tenant_id": bin_id} if bin_id else {"email": email},
            {"email": email},
        ],
        "received_at": {"$gte": cutoff_iso},
    }
    try:
        last = await db.pixel_events.find_one(query, sort=[("received_at", -1)], projection={"_id": 0, "received_at": 1, "event": 1, "url": 1})
    except Exception as e:
        logger.warning(f"[pixel_status] query failed: {e}")
        last = None

    if last:
        return {
            "status": "online",
            "last_event_at": last.get("received_at"),
            "last_event_type": last.get("event"),
            "last_url": last.get("url"),
            "source": "live",
        }

    # Fallback — check any event ever for this tenant (offline but installed)
    try:
        any_ever = await db.pixel_events.find_one({
            "$or": [
                {"tenant_id": bin_id} if bin_id else {"email": email},
                {"email": email},
            ]
        }, sort=[("received_at", -1)], projection={"_id": 0, "received_at": 1})
    except Exception:
        any_ever = None

    if any_ever:
        return {
            "status": "offline",
            "last_event_at": any_ever.get("received_at"),
            "source": "stale",
        }

    return {"status": "not_installed", "source": "none"}


# ═══════════════════════════════════════════════════════════════
# PHASE B — Scan + Repair
# ═══════════════════════════════════════════════════════════════

# Seed RNG deterministically per tenant so a given client sees stable numbers
def _seeded_random(bin_id: str, salt: str = "") -> random.Random:
    seed = int(hashlib.sha256(f"{bin_id}:{salt}".encode()).hexdigest()[:10], 16)
    return random.Random(seed)


async def _sample_real_issues(n: int = 5) -> List[dict]:
    """Pull a diverse slice of REAL issues from sentinel_diagnoses to show the client."""
    if db is None:
        return []
    try:
        # Severity convention in this DB is P0/P1/P2/P3 — include top 3
        pipeline = [
            {"$match": {"severity": {"$in": ["P0", "P1", "P2"]}}},
            {"$sample": {"size": n}},
            {"$project": {
                "_id": 0,
                "severity": 1,
                "service": 1,
                "diagnosis": 1,
                "proposed_fix": 1,
                "timestamp": 1,
            }}
        ]
        cursor = db.sentinel_diagnoses.aggregate(pipeline)
        issues = []
        async for d in cursor:
            issues.append(d)
        return issues
    except Exception as e:
        logger.warning(f"[website_scan] issue sample failed: {e}")
        return []


class ScanRequest(BaseModel):
    website: Optional[str] = Field(default=None, max_length=300)


@router.post("/website/scan")
async def website_scan(body: ScanRequest, user: dict = Depends(_verify_platform_user)):
    """Run a real diagnostic scan via website_audit_service. No mocks."""
    tenant = await _resolve_tenant(user)
    bin_id = tenant.get("bin") or "UNKNOWN"
    website = (body.website or tenant.get("website") or "").strip()
    if not website:
        raise HTTPException(400, "no_website_on_tenant")

    from services.website_audit_service import real_audit
    audit = await real_audit(website)
    if not audit.get("ok"):
        raise HTTPException(400, audit.get("error") or "audit_failed")

    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    doc = {
        "scan_id": scan_id,
        "tenant_bin": bin_id,
        "email": tenant.get("email"),
        "website": audit["url"],
        # Real audit results
        "ssl": audit["ssl"],
        "pagespeed": audit["pagespeed"],
        "mobile": audit["mobile"],
        "broken_links": audit["broken_links"],
        "contact_form": audit["contact_form"],
        "social_links": audit["social_links"],
        "copyright_year": audit["copyright_year"],
        "google_maps": audit["google_maps"],
        "score_breakdown": audit["score_breakdown"],
        "overall_score": audit["overall_score"],
        "score": audit["overall_score"],   # legacy alias
        "issues": audit["issues"],
        "repair_recommended": audit["repair_recommended"],
        "rebuild_recommended": audit["rebuild_recommended"],
        "duration_s": audit["duration_s"],
        "created_at": audit["finished_at"],
    }
    try:
        await db.customer_scans.insert_one(doc)
        doc.pop("_id", None)
    except Exception as e:
        logger.warning(f"[website_scan] insert failed: {e}")
    doc.pop("_id", None)
    return doc


# ─────────────────────── Repair engine (D-75 honest rewrite) ───────────────

# iter D-75 — REAL phases. No fake "deployed" / "Canary rollout" lies.
# We can't push code to the customer's server; we can analyze + generate
# an actionable plan + email it. Customer applies + re-scans to update score.
REAL_REPAIR_PHASES = [
    ("scanning",   "Running real audit probe (SSL, Lighthouse, broken links, schema)…", 0, 35, "#EF4444"),
    ("planning",   "Generating actionable repair plan via DeepSeek V3.1…",              35, 80, "#F97316"),
    ("emailing",   "Emailing the repair plan to your inbox…",                           80, 95, "#EAB308"),
    ("plan_ready", "Plan ready. Apply the fixes and trigger a re-scan to update your score.", 95, 100, "#22C55E"),
]


async def _generate_repair_plan_via_llm(
    audit: dict, customer_email: str, website: str,
) -> List[dict]:
    """For each issue in the audit, ask the LLM gateway for a concrete
    fix proposal. Returns a list of plan items — never mocks, returns
    `[]` if the gateway is unavailable so the caller surfaces the
    failure honestly.

    Uses the same llm_gateway_v2.route() as the autonomous CTO repair
    agent (D-73 confirmed working — DeepSeek V3.1 via OpenRouter)."""
    issues = audit.get("issues") or []
    if not issues:
        return []

    try:
        from services.llm_gateway_v2 import route
    except Exception as e:
        logger.warning(f"[repair_plan] gateway import failed: {e}")
        return []

    plan: List[dict] = []
    # Cap to top-5 issues so plan generation stays under 30s + cost stays bounded
    for i, issue in enumerate(issues[:5]):
        title = issue.get("title") or issue.get("name") or f"Issue {i+1}"
        severity = issue.get("severity") or "medium"
        category = issue.get("category") or "general"
        detail = issue.get("detail") or issue.get("description") or ""

        system = (
            "You are a senior web performance + security engineer. "
            "An automated audit found an issue on a customer site. "
            "Respond with EXACTLY this structure (no preamble):\n"
            "  ROOT CAUSE: one sentence.\n"
            "  FIX STEPS: numbered list, 2-5 concrete steps the website "
            "owner (or their developer) can apply.\n"
            "  CODE SNIPPET: a single fenced code block with the exact "
            "file/config to change, OR the exact CLI command. If no code "
            "applies (e.g. external action needed), write `(no code — "
            "external action: <action>)`."
        )
        prompt = (
            f"website  : {website}\n"
            f"issue    : {title}\n"
            f"category : {category}\n"
            f"severity : {severity}\n"
            f"detail   : {detail[:600]}\n"
        )
        try:
            res = await route(
                task_type="repair_diagnose",
                prompt=prompt,
                system=system,
                max_tokens=600,
            )
        except Exception as e:
            logger.warning(f"[repair_plan] gateway exc on {title}: {e}")
            continue
        if not (res or {}).get("ok") or not (res.get("text") or "").strip():
            continue
        plan.append({
            "issue_title": title,
            "severity": severity,
            "category": category,
            "llm_response": res.get("text", "")[:4000],
            "llm_provider": res.get("provider"),
            "llm_model": res.get("model"),
            "llm_latency_ms": res.get("latency_ms"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })
    return plan


async def _email_repair_plan(customer_email: str, website: str,
                              plan: List[dict], audit: dict) -> dict:
    """Email the plan to the customer via Resend. Best-effort — returns
    {"ok": bool, "error": str?} so the caller can surface it.
    NO MOCK: if Resend is unconfigured or fails, we return ok=False
    with the real error string."""
    if not plan:
        return {"ok": False, "error": "no_plan_items_to_email"}
    if not customer_email:
        return {"ok": False, "error": "no_customer_email"}
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return {"ok": False, "error": "resend_not_configured"}

    # Build a clean text body
    lines = [
        f"AUREM Repair Plan for {website}",
        f"Audit score: {audit.get('overall_score','?')}/100",
        f"Issues found: {len(audit.get('issues') or [])}",
        "",
        "=" * 60,
    ]
    for i, item in enumerate(plan, 1):
        lines.append(f"\n[{i}] {item['issue_title']}  (severity: {item['severity']})")
        lines.append("-" * 60)
        lines.append(item["llm_response"])
    body = "\n".join(lines)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}",
                         "Content-Type": "application/json"},
                json={
                    "from": os.environ.get("RESEND_FROM_ADDRESS",
                                           "AUREM <repairs@aurem.live>"),
                    "to": [customer_email],
                    "subject": f"Your AUREM repair plan for {website}",
                    "text": body,
                },
            )
    except Exception as e:
        return {"ok": False, "error": f"resend_exc:{type(e).__name__}:{str(e)[:120]}"}
    if r.status_code not in (200, 201, 202):
        return {"ok": False, "error": f"resend_http_{r.status_code}",
                "detail": r.text[:200]}
    try:
        return {"ok": True, "email_id": r.json().get("id")}
    except Exception:
        return {"ok": True}


async def _run_repair_job(job_id: str, tenant_bin: str, website: str,
                          customer_email: str):
    """D-75 honest implementation. Real audit → real LLM plan → real
    email. Status = `plan_ready_for_customer` (NOT `completed`).
    `score_after` stays None until customer applies fixes + re-scans."""

    async def _set(fields: dict):
        try:
            fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            await db.repair_jobs.update_one({"job_id": job_id}, {"$set": fields})
        except Exception as e:
            logger.warning(f"[repair_job {job_id}] set failed: {e}")

    async def _event(phase: str, message: str):
        try:
            await db.repair_jobs.update_one(
                {"job_id": job_id},
                {"$push": {"events": {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "phase": phase,
                    "message": message,
                }}},
            )
        except Exception as e:
            logger.warning(f"[repair_job {job_id}] event failed: {e}")

    try:
        # Phase 1 — REAL audit
        ph = REAL_REPAIR_PHASES[0]
        await _set({"current_phase": ph[0], "current_phase_label": ph[1],
                    "current_phase_color": ph[4], "progress_pct": ph[2]})
        await _event(ph[0], f"Probing {website} — SSL, Lighthouse, broken links, schema")

        from services.website_audit_service import real_audit
        audit = await real_audit(website)
        if not audit.get("ok"):
            await _set({"status": "failed",
                        "error": audit.get("error") or "audit_failed",
                        "current_phase": "failed",
                        "current_phase_color": "#EF4444"})
            await _event("failed", f"Audit failed: {audit.get('error')}")
            return

        await _event(ph[0],
                     f"Score: {audit.get('overall_score')}/100 — "
                     f"{len(audit.get('issues') or [])} issues found")
        await _set({"score_before": audit.get("overall_score"),
                    "audit_snapshot": {k: audit.get(k) for k in (
                        "url", "overall_score", "score_breakdown",
                        "ssl", "pagespeed", "mobile",
                        "broken_links", "contact_form", "social_links",
                        "copyright_year", "google_maps",
                        "repair_recommended", "rebuild_recommended",
                        "finished_at", "duration_s",
                    )},
                    "issues": audit.get("issues") or [],
                    "progress_pct": ph[3]})

        # Phase 2 — REAL LLM plan generation
        ph = REAL_REPAIR_PHASES[1]
        await _set({"current_phase": ph[0], "current_phase_label": ph[1],
                    "current_phase_color": ph[4], "progress_pct": ph[2]})
        await _event(ph[0], f"Generating plan for top {min(5, len(audit.get('issues') or []))} issues")
        plan = await _generate_repair_plan_via_llm(audit, customer_email, website)
        if plan:
            await _event(ph[0],
                         f"Plan generated — {len(plan)} actionable items "
                         f"via {plan[0].get('llm_provider')}/{plan[0].get('llm_model')}")
        else:
            await _event(ph[0],
                         "LLM gateway unavailable or no issues to repair — plan empty")
        await _set({"repair_plan": plan, "progress_pct": ph[3]})

        # Phase 3 — REAL email via Resend (best-effort)
        ph = REAL_REPAIR_PHASES[2]
        await _set({"current_phase": ph[0], "current_phase_label": ph[1],
                    "current_phase_color": ph[4], "progress_pct": ph[2]})
        email_result = await _email_repair_plan(customer_email, website, plan, audit)
        if email_result.get("ok"):
            await _event(ph[0], f"Plan emailed to {customer_email}")
        else:
            await _event(ph[0],
                         f"Email skipped: {email_result.get('error')}")
        await _set({"email_result": email_result, "progress_pct": ph[3]})

        # Phase 4 — PLAN READY (not "deployed" — customer must apply)
        ph = REAL_REPAIR_PHASES[3]
        await _set({
            "status": "plan_ready_for_customer",
            "current_phase": ph[0],
            "current_phase_label": ph[1],
            "current_phase_color": ph[4],
            "progress_pct": 100,
            "score_after": None,  # only re-scan updates this — HONEST
            "next_step": (
                "Apply the plan items above (DIY or hand to your developer), "
                "then click `Re-scan` to see your updated score."
            ),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        await _event(ph[0],
                     f"Plan ready with {len(plan)} items. "
                     "Re-scan after applying to update your score.")
    except Exception as e:
        logger.exception(f"[repair_job {job_id}] failed: {e}")
        try:
            await db.repair_jobs.update_one(
                {"job_id": job_id},
                {"$set": {"status": "failed", "error": str(e)[:500],
                          "current_phase": "failed",
                          "current_phase_color": "#EF4444"}},
            )
        except Exception:
            pass


class RepairStart(BaseModel):
    scan_id: Optional[str] = None


@router.post("/website/repair/start")
async def repair_start(body: RepairStart, user: dict = Depends(_verify_platform_user)):
    """Kicks off the REAL repair-plan job. Returns the job_id for polling.
    The plan is generated via the LLM gateway; we never claim to have
    deployed code to the customer's server."""
    tenant = await _resolve_tenant(user)
    bin_id = tenant.get("bin") or "UNKNOWN"
    website = (tenant.get("website") or "").strip()
    if not website:
        # Try to resolve from the most recent scan
        last = await db.customer_scans.find_one(
            {"tenant_bin": bin_id}, sort=[("created_at", -1)],
            projection={"website": 1, "_id": 0},
        )
        website = (last or {}).get("website", "")
    if not website:
        raise HTTPException(400, "no_website_on_tenant — set your site URL first")

    # Carry forward a recent scan_id if the customer passed one (for the UI's
    # "score before" — final value comes from the live audit anyway).
    scan = None
    if body.scan_id:
        scan = await db.customer_scans.find_one({"scan_id": body.scan_id})

    job_id = f"rep_{uuid.uuid4().hex[:14]}"
    doc = {
        "job_id": job_id,
        "tenant_bin": bin_id,
        "email": tenant.get("email"),
        "website": website,
        "status": "running",
        "current_phase": "scanning",
        "current_phase_label": "Starting real audit…",
        "current_phase_color": "#EF4444",
        "progress_pct": 0,
        "score_before": (scan or {}).get("overall_score") or (scan or {}).get("score"),
        "score_after": None,  # NEVER pre-populated — only re-scan fills this
        "scan_id": (scan or {}).get("scan_id"),
        "events": [],
        "repair_plan": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.repair_jobs.insert_one(doc)
        doc.pop("_id", None)
    except Exception as e:
        logger.error(f"[repair_start] insert failed: {e}")
        raise HTTPException(500, "could not start repair") from None

    # Real background work — audit + LLM plan + email
    asyncio.create_task(
        _run_repair_job(job_id, bin_id, website, tenant.get("email") or ""),
    )

    return {"ok": True, "job_id": job_id,
            "score_before": doc.get("score_before"),
            "honest_disclaimer": (
                "AUREM generates an actionable repair PLAN — we do not "
                "deploy code to your site. Apply the plan and re-scan to "
                "update your score."
            )}


@router.get("/website/repair/status/{job_id}")
async def repair_status(job_id: str, user: dict = Depends(_verify_platform_user)):
    """Polled by the frontend every ~1 sec to animate progress."""
    tenant = await _resolve_tenant(user)
    job = await db.repair_jobs.find_one({"job_id": job_id, "tenant_bin": tenant.get("bin")}, {"_id": 0})
    if not job:
        raise HTTPException(404, "repair job not found")
    # Trim events to last 14 for UI
    events = job.get("events", [])
    job["events"] = events[-14:]
    job["events_total"] = len(events)
    return job


@router.get("/website/repair/latest")
async def repair_latest(user: dict = Depends(_verify_platform_user)):
    """Get the most recent repair job for this tenant (to resume UI)."""
    tenant = await _resolve_tenant(user)
    job = await db.repair_jobs.find_one({"tenant_bin": tenant.get("bin")}, sort=[("created_at", -1)], projection={"_id": 0})
    return job or {}
