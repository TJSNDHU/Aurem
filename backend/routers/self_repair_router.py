"""
AUREM Self-Repair API Router
============================
Endpoints for manually triggering self-scans, viewing repair history,
and managing auto-scan sites.
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
from typing import Optional
import jwt
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/self-repair", tags=["Self-Repair"])

_db = None
_jwt_secret = None
_jwt_algorithm = "HS256"


def set_db(database):
    global _db
    _db = database
    from services.self_repair_loop import set_db as set_repair_db
    set_repair_db(database)


def set_jwt(secret, algorithm="HS256"):
    global _jwt_secret, _jwt_algorithm
    _jwt_secret = secret
    _jwt_algorithm = algorithm


async def _require_admin(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    # Bug-fix 133/147 — was returning payload unconditionally; any valid JWT
    # could trigger production file writes via /unfixable/.../fix-with-builder.
    # Now require explicit admin/super-admin claim, role, or whitelisted email.
    from utils.admin_guard import is_admin_email
    is_admin = (
        payload.get("is_admin")
        or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
        or is_admin_email(payload.get("email"))
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


@router.get("/status")
async def get_status():
    """Get self-repair loop status and summary."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    from services.self_repair_loop import AUTO_SCAN_SITES, SCAN_INTERVAL_HOURS

    latest = await _db["system_auto_repairs"].find_one(
        {}, {"_id": 0}, sort=[("scanned_at", -1)]
    )

    total_scans = await _db["system_auto_repairs"].count_documents({})
    total_repairs = 0
    if total_scans > 0:
        pipeline = [
            {"$project": {"repair_count": {"$size": {"$ifNull": ["$repairs", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$repair_count"}}},
        ]
        agg = await _db["system_auto_repairs"].aggregate(pipeline).to_list(1)
        if agg:
            total_repairs = agg[0].get("total", 0)

    return {
        "active": True,
        "scan_interval_hours": SCAN_INTERVAL_HOURS,
        "monitored_sites": [s["label"] for s in AUTO_SCAN_SITES],
        "total_scans": total_scans,
        "total_repairs_detected": total_repairs,
        "last_scan": latest,
    }


@router.post("/trigger")
async def trigger_scan(request: Request, site_url: Optional[str] = None):
    """Manually trigger a self-repair scan. Requires JWT auth."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    from services.self_repair_loop import run_all_scans, run_self_scan, AUTO_SCAN_SITES

    if site_url:
        match = next((s for s in AUTO_SCAN_SITES if s["url"] == site_url), None)
        if not match:
            results = [await run_self_scan(site_url, "manual", site_url)]
        else:
            results = [await run_self_scan(match["url"], match["tenant_id"], match["label"])]
    else:
        results = await run_all_scans()

    # SOC 2 Audit Trail
    auth = request.headers.get("Authorization", "")
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else ""
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algorithm])
        actor_id = payload.get("user_id", "admin")
    except Exception:
        actor_id = "admin"

    await _db["aurem_audit_logs"].insert_one({
        "action": "self_repair_triggered",
        "business_id": "platform",
        "actor_id": actor_id,
        "actor_type": "admin",
        "resource_type": "self_repair",
        "resource_id": site_url or "all_sites",
        "details": {"sites_scanned": len(results)},
        "ip_address": request.headers.get("x-forwarded-for", request.client.host if request.client else ""),
        "user_agent": request.headers.get("user-agent", ""),
        "success": True,
        "timestamp": datetime.now(timezone.utc),
        "_immutable": True,
    })

    return {"triggered_at": datetime.now(timezone.utc).isoformat(), "results": results}


@router.get("/history")
async def get_repair_history(tenant_id: Optional[str] = None, limit: int = 20):
    """Get past self-repair scan history."""
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    from services.self_repair_loop import get_repair_history
    history = await get_repair_history(tenant_id=tenant_id, limit=limit)
    return {"count": len(history), "history": history}


@router.get("/sites")
async def get_monitored_sites():
    """List all sites being auto-scanned."""
    from services.self_repair_loop import AUTO_SCAN_SITES
    return {"sites": AUTO_SCAN_SITES}


# ═══════════════════════════════════════════════════════════════
# /admin/self-repair page — customer-centric views
# ═══════════════════════════════════════════════════════════════

def _flame_tone(score: int) -> str:
    """Colour band for a flame score (0–100)."""
    if score >= 90:
        return "gold"    # on-fire
    if score >= 75:
        return "good"    # burning
    if score >= 60:
        return "warn"    # smoking
    return "bad"         # cold / needs help


@router.get("/customers")
async def list_customers(request: Request):
    """
    Return one row per monitored customer/site with:
      - current Flame Score (latest scan overall_score)
      - last 10 scores for a sparkline
      - critical / warning / unfixable counts
    Used by the /admin/self-repair dashboard.
    """
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    # Discover every site the scanner covers (baseline + workspaces).
    from services.self_repair_loop import _discover_scan_targets
    targets = await _discover_scan_targets()

    # Pull in any tenant that has scans but isn't in the live target list
    # (e.g., de-activated workspace) so history is still visible.
    distinct_labels = await _db["system_auto_repairs"].distinct("label")
    target_labels = {t["label"] for t in targets}
    for lbl in distinct_labels:
        if lbl not in target_labels:
            doc = await _db["system_auto_repairs"].find_one({"label": lbl}, {"_id": 0, "site_url": 1, "tenant_id": 1})
            if doc:
                targets.append({
                    "url": doc.get("site_url", ""),
                    "tenant_id": doc.get("tenant_id", "unknown"),
                    "label": lbl,
                    "inactive": True,
                })

    customers = []
    for t in targets:
        label = t["label"]
        tenant_id = t.get("tenant_id") or "unknown"
        # Last scan
        latest = await _db["system_auto_repairs"].find_one(
            {"label": label},
            {"_id": 0, "overall_score": 1, "scores": 1, "critical_count": 1,
             "warning_count": 1, "scanned_at": 1, "repairs": 1},
            sort=[("scanned_at", -1)],
        )
        # Trend (last 10 scans, oldest → newest)
        trend_cursor = _db["system_auto_repairs"].find(
            {"label": label},
            {"_id": 0, "overall_score": 1, "scanned_at": 1},
        ).sort("scanned_at", -1).limit(10)
        trend_docs = await trend_cursor.to_list(10)
        trend = [
            {"score": d.get("overall_score", 0), "at": d.get("scanned_at", "")}
            for d in reversed(trend_docs)
        ]

        unfixable_count = await _db["unfixable_issues_queue"].count_documents(
            {"tenant_id": tenant_id, "status": "queued"}
        )

        score = latest.get("overall_score", 0) if latest else 0
        delta = None
        if len(trend) >= 2:
            delta = trend[-1]["score"] - trend[-2]["score"]

        customers.append({
            "tenant_id": tenant_id,
            "label": label,
            "site_url": t.get("url", ""),
            "inactive": bool(t.get("inactive")),
            "flame_score": score,
            "flame_tone": _flame_tone(score),
            "delta": delta,
            "scores": (latest or {}).get("scores", {}),
            "critical_count": (latest or {}).get("critical_count", 0),
            "warning_count": (latest or {}).get("warning_count", 0),
            "unfixable_queued": unfixable_count,
            "last_scanned_at": (latest or {}).get("scanned_at"),
            "trend": trend,
        })

    # Sort: lowest flame first (those who need attention)
    customers.sort(key=lambda c: (c["flame_score"], -c["unfixable_queued"]))

    avg = round(sum(c["flame_score"] for c in customers) / max(len(customers), 1))
    total_unfixable = sum(c["unfixable_queued"] for c in customers)

    return {
        "count": len(customers),
        "average_flame_score": avg,
        "total_unfixable": total_unfixable,
        "customers": customers,
    }


@router.get("/customers/{tenant_id}/trend")
async def customer_trend(tenant_id: str, request: Request, days: int = 30, limit: int = 60):
    """Full Flame Score trend for one customer (for the detail graph)."""
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))).isoformat()

    cursor = _db["system_auto_repairs"].find(
        {"tenant_id": tenant_id, "scanned_at": {"$gte": since}},
        {"_id": 0, "overall_score": 1, "scanned_at": 1, "scores": 1,
         "critical_count": 1, "warning_count": 1, "label": 1, "site_url": 1},
    ).sort("scanned_at", 1).limit(max(1, min(limit, 200)))
    docs = await cursor.to_list(limit)
    if not docs:
        return {"tenant_id": tenant_id, "points": [], "label": None}

    points = [
        {
            "score": d.get("overall_score", 0),
            "at": d.get("scanned_at"),
            "critical": d.get("critical_count", 0),
            "warning": d.get("warning_count", 0),
            "scores": d.get("scores", {}),
        }
        for d in docs
    ]
    return {
        "tenant_id": tenant_id,
        "label": docs[-1].get("label"),
        "site_url": docs[-1].get("site_url"),
        "points": points,
        "current_flame": points[-1]["score"],
        "flame_tone": _flame_tone(points[-1]["score"]),
    }


@router.get("/unfixable")
async def list_unfixable(request: Request, tenant_id: Optional[str] = None,
                         status: str = "queued", limit: int = 100):
    """
    Issues the auto-patcher could NOT repair — candidates for AUREM Builder.
    """
    await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    query: dict = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if status:
        query["status"] = status

    cursor = _db["unfixable_issues_queue"].find(query, {"_id": 0}).sort(
        [("severity", -1), ("last_seen", -1)]
    ).limit(max(1, min(limit, 500)))
    items = await cursor.to_list(limit)
    return {"count": len(items), "items": items}


@router.post("/unfixable/{fingerprint}/fix-with-builder")
async def fix_with_builder(fingerprint: str, request: Request):
    """
    Bridge: take an unfixable issue and fire it into the AUREM Builder
    as a natural-language feature request. Returns the builder build_id
    so the admin can track progress from /admin/builder/{id}.
    """
    admin_payload = await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    issue = await _db["unfixable_issues_queue"].find_one({"fingerprint": fingerprint}, {"_id": 0})
    if not issue:
        raise HTTPException(status_code=404, detail="Unfixable issue not found")

    admin_email = admin_payload.get("email") or admin_payload.get("sub") or "admin"
    result = await bridge_issue_to_builder(
        _db, issue, actor_email=admin_email, source="admin_ui",
    )

    # SOC 2 audit trail
    await _db["aurem_audit_logs"].insert_one({
        "action": "self_repair_bridge_to_builder",
        "business_id": issue.get("tenant_id", "platform"),
        "actor_id": admin_email,
        "actor_type": "admin",
        "resource_type": "unfixable_issue",
        "resource_id": fingerprint,
        "details": {"build_id": result["build_id"], "issue": issue.get("issue", "")[:160]},
        "ip_address": request.headers.get("x-forwarded-for", request.client.host if request.client else ""),
        "user_agent": request.headers.get("user-agent", ""),
        "success": True,
        "timestamp": datetime.now(timezone.utc),
        "_immutable": True,
    })

    return result


async def bridge_issue_to_builder(db, issue: dict, actor_email: str = "sentinel",
                                  source: str = "admin_ui") -> dict:
    """
    Reusable bridge: convert an unfixable-issue document into a Builder build.
    Callable from HTTP handlers AND from background services (Sentinel Guard).
    Returns {success, build_id, builder_url, status, fingerprint}.

    iter D-71h — `tenant_id` was being passed through as the literal string
    "unknown" (default fallback in upstream scan loops) for sites that
    have a row in system_auto_repairs but no matching tenant_customers
    record. This caused Builder to log
       "Customer: reroots.ca (tenant_id=unknown)"
    and tanked the Builder success-rate KPI. We now resolve tenant_id
    from the `site_url` via tenant_customers as a last-mile fallback.
    """
    from services import aurem_builder
    from routers.aurem_builder_router import _run_build_and_log
    import asyncio as _asyncio

    fingerprint = issue.get("fingerprint")

    # iter D-71h — resolve tenant_id from site_url when missing/unknown.
    tenant_id = issue.get("tenant_id")
    if not tenant_id or tenant_id == "unknown":
        site_url = (issue.get("site_url") or "").strip()
        if site_url:
            from urllib.parse import urlparse
            try:
                host = urlparse(site_url if "://" in site_url else f"https://{site_url}").netloc.lower()
                host = host.replace("www.", "")
            except Exception:
                host = ""
            if host:
                # Look up tenant by exact website match, then by domain match
                for q in (
                    {"website": {"$regex": host, "$options": "i"}},
                    {"website_url": {"$regex": host, "$options": "i"}},
                    {"domain": host},
                    {"primary_domain": host},
                ):
                    try:
                        tdoc = await db.tenant_customers.find_one(q, {"tenant_id": 1, "business_id": 1, "_id": 0})
                        if tdoc:
                            tenant_id = tdoc.get("tenant_id") or tdoc.get("business_id")
                            if tenant_id:
                                # Patch back into the issue dict so the description renders correctly.
                                issue["tenant_id"] = tenant_id
                                break
                    except Exception:
                        continue
        if not tenant_id or tenant_id == "unknown":
            tenant_id = "unknown"  # honest fallback
            issue["tenant_id"] = tenant_id

    description = (
        f"AUREM Self-Repair bridged an unfixable issue to you.\n\n"
        f"Customer: {issue.get('label')}  (tenant_id={issue.get('tenant_id')})\n"
        f"Site: {issue.get('site_url')}\n"
        f"Category: {issue.get('category')}  · Severity: {issue.get('severity')}\n"
        f"Issue: {issue.get('issue')}\n"
        f"Details: {issue.get('details') or '(none)'}\n"
        f"Suggested direction: {issue.get('aurem_solution') or '(none)'}\n\n"
        f"Please generate the backend/frontend code patch that actually resolves "
        f"this root-cause for the site above. Follow the standard AUREM builder "
        f"safety rails. If a router/service is added, also register it where the "
        f"platform expects."
    )

    model = aurem_builder.DEFAULT_MODEL
    build_id = aurem_builder.new_build_id()
    now = datetime.now(timezone.utc).isoformat()

    await db.build_log.insert_one({
        "build_id": build_id,
        "description": description,
        "model": model,
        "admin": actor_email,
        "status": "queued",
        "started_at": now,
        "files": [],
        "notes": [f"bridged from {source}: {fingerprint}"],
        "test_command": None,
        "error": None,
        "source": f"self_repair_bridge:{source}",
        "source_fingerprint": fingerprint,
        "source_tenant_id": issue.get("tenant_id"),
    })

    _asyncio.create_task(_run_build_and_log(build_id, description, actor_email, model))

    await db["unfixable_issues_queue"].update_one(
        {"fingerprint": fingerprint},
        {"$set": {
            "status": "sent_to_builder",
            "builder_build_id": build_id,
            "builder_status": "queued",
            "bridged_at": now,
            "bridged_by": actor_email,
            "bridged_source": source,
        }},
    )

    return {
        "success": True,
        "build_id": build_id,
        "builder_url": f"/admin/builder/{build_id}",
        "status": "queued",
        "fingerprint": fingerprint,
    }


@router.post("/unfixable/{fingerprint}/dismiss")
async def dismiss_unfixable(fingerprint: str, request: Request):
    """Mark an unfixable issue as dismissed (won't show in default queue view)."""
    admin_payload = await _require_admin(request)
    if _db is None:
        raise HTTPException(status_code=503, detail="Database not ready")

    result = await _db["unfixable_issues_queue"].update_one(
        {"fingerprint": fingerprint},
        {"$set": {
            "status": "dismissed",
            "dismissed_at": datetime.now(timezone.utc).isoformat(),
            "dismissed_by": admin_payload.get("email", "admin"),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found")
    return {"success": True, "fingerprint": fingerprint, "status": "dismissed"}
