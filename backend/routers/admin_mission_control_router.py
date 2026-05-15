"""
AUREM ADMIN MISSION CONTROL
Central control panel for managing ALL services, APIs, subscriptions, and tokens

Endpoints:
- GET /api/admin/mission-control/dashboard - Complete dashboard overview
- GET /api/admin/mission-control/clients - All client business profiles
- GET /api/admin/mission-control/clients/{profile_id} - Single client detail
- GET /api/admin/mission-control/clients/{profile_id}/scans - Scan history for client
- GET /api/admin/mission-control/clients/{profile_id}/repairs - Repair fixes for client
- GET /api/admin/mission-control/services - Service registry
- POST /api/admin/mission-control/services/add-key - Add API key for service
- POST /api/admin/mission-control/services/remove-key - Remove API key
- GET /api/admin/mission-control/subscriptions - All subscriptions
- GET /api/admin/mission-control/usage - Usage analytics
- POST /api/admin/mission-control/recharge - Recharge tokens/credits
- POST /api/admin/mission-control/service/toggle - Start/stop service
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import secrets
import logging

from services.toon_service import get_toon_service
from utils.fix_enrichment import enrich_issues_with_fix_status, enrich_scan_result_issues, build_confirmed_resolved

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/mission-control", tags=["Admin Mission Control"])

# MongoDB reference
_db = None

def set_db(database):
    global _db
    _db = database
    get_toon_service().set_db(database)

def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


def _url_variants(url: str) -> list:
    """Generate URL variants for case-insensitive + trailing-slash matching."""
    if not url:
        return []
    base = url.rstrip("/")
    lower = base.lower()
    # Title case first letter of domain
    from urllib.parse import urlparse
    parsed = urlparse(base)
    title_domain = parsed.netloc.capitalize() if parsed.netloc else ""
    title_url = f"{parsed.scheme}://{title_domain}{parsed.path}" if title_domain else ""
    variants = list({base, base + "/", lower, lower + "/"})
    if title_url:
        variants.extend([title_url, title_url + "/"])
    return list(set(variants))


async def _get_all_scans_for_url(url: str, limit: int = 50) -> list:
    """Fetch scans from both scan_history AND system_scans, merged and sorted."""
    variants = _url_variants(url)
    query = {"website_url": {"$in": variants}}

    # scan_history (saved from frontend scanner UI)
    history_scans = await _get_db().scan_history.find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)

    # system_scans (saved from backend /api/scanner/scan)
    system_scans_raw = await _get_db().system_scans.find(
        query, {"_id": 0}
    ).sort("scan_date", -1).limit(limit).to_list(limit)

    # Normalize system_scans to same shape as scan_history
    for s in system_scans_raw:
        if "created_at" not in s:
            s["created_at"] = s.get("scan_date", "")
        # Build scores dict from category sub-objects
        if "scores" not in s:
            s["scores"] = {}
            for cat in ("performance", "security", "seo", "accessibility"):
                if cat in s and isinstance(s[cat], dict):
                    s["scores"][cat] = s[cat].get("score", 0)
        # Build summary
        if "summary" not in s:
            total_issues = s.get("issues_found", 0)
            critical = s.get("critical_issues", 0)
            s["summary"] = {"issues_found": total_issues, "critical": critical}
        if "repairs" not in s:
            s["repairs"] = []
        s["source"] = "system_scan"

    for h in history_scans:
        h["source"] = "scan_history"

    # Merge + dedupe by scan_id
    seen = set()
    merged = []
    for scan in history_scans + system_scans_raw:
        sid = scan.get("scan_id", "")
        if sid not in seen:
            seen.add(sid)
            merged.append(scan)

    # Sort by created_at desc
    merged.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return merged[:limit]


async def _count_repairs_for_url(url: str) -> int:
    """Count total repairs (collection + inline in scan_history)."""
    variants = _url_variants(url)
    query = {"website_url": {"$in": variants}}

    # repair_fixes collection (from AI repair engine)
    collection_count = await _get_db().repair_fixes.count_documents(query)

    # Also check scan_url field in repair_fixes
    collection_count += await _get_db().repair_fixes.count_documents({"scan_url": {"$in": variants}})

    # Inline repairs from scan_history
    inline_pipeline = [
        {"$match": {**query, "repairs": {"$exists": True, "$ne": []}}},
        {"$project": {"rc": {"$size": "$repairs"}}},
        {"$group": {"_id": None, "total": {"$sum": "$rc"}}}
    ]
    try:
        agg = await _get_db().scan_history.aggregate(inline_pipeline).to_list(1)
        inline_count = agg[0]["total"] if agg else 0
    except Exception:
        inline_count = 0

    return collection_count + inline_count


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class AddAPIKeyRequest(BaseModel):
    service_id: str  # gpt-4o, voxtral-tts, stripe-payments, etc.
    api_key: str  # The actual API key (will be encrypted)
    notes: Optional[str] = None
    monthly_spend_limit: Optional[float] = None  # Optional spending limit


class RemoveAPIKeyRequest(BaseModel):
    key_id: str
    service_id: str


class RechargeRequest(BaseModel):
    service_id: str
    amount_usd: float
    tokens_added: Optional[int] = None
    credits_added: Optional[float] = None
    payment_method: str = "manual"  # stripe, paypal, manual
    notes: Optional[str] = None


class ToggleServiceRequest(BaseModel):
    service_id: str
    action: str  # "start", "stop", "pause"


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN AUTHENTICATION (Simple - enhance later)
# ═══════════════════════════════════════════════════════════════════════════════

async def verify_admin(authorization: Optional[str] = Header(None), x_admin_key: Optional[str] = Header(None)):
    """
    Verify admin authentication via JWT token or X-Admin-Key header.
    """
    # Check JWT token first
    if authorization and authorization.startswith("Bearer "):
        import jwt, os
        token = authorization.split(" ", 1)[1]
        try:
            secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            # Bug-fix #101 — was `payload.get("email")` truthy bypass (every JWT
            # has email). Now require explicit admin claim or whitelist email.
            if payload.get("is_admin") or payload.get("is_super_admin") or payload.get("role") in ("admin", "super_admin"):
                return payload
            from utils.admin_guard import is_admin_email
            if is_admin_email(payload.get("email")):
                payload["is_admin"] = True
                return payload
        except Exception:
            pass
    # Bug-fix #100/105 — was `if x_admin_key: return ...` accepting any
    # non-empty string. Now constant-time compare against AUREM_ADMIN_KEY.
    if x_admin_key:
        import hmac as _hmac
        expected = (os.environ.get("AUREM_ADMIN_KEY") or "").strip()
        if expected and _hmac.compare_digest(x_admin_key, expected):
            return {"admin_key": "valid"}
    raise HTTPException(401, "Admin authentication required")


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD & OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/dashboard")
async def get_mission_control_dashboard(admin=Depends(verify_admin)):
    """
    Complete admin dashboard in TOON format
    
    Returns:
    AdminDashboard:
      metrics:
        total_active_subscriptions: 150
        mrr: $35000.00
        arr: $420000.00
      tiers:
        free: 50
        starter: 60
        professional: 30
        enterprise: 10
      services: Service[15]{id, status, spend}: gpt-4o, active, 1234.56; voxtral, active, 234.50; ...
      top_users: User[5]{id, tokens, cost}: user_abc, 150000, 45.67; ...
    """
    toon_service = get_toon_service()
    
    try:
        dashboard_toon = await toon_service.get_admin_dashboard_toon()
        
        return {
            "format": "TOON",
            "data": dashboard_toon,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] Dashboard error: {e}")
        raise HTTPException(500, f"Failed to load dashboard: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT MANAGEMENT — Business Profiles, Scans, Repairs
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/clients")
async def get_all_clients(admin=Depends(verify_admin)):
    """
    Get all client business profiles with latest scan summary.
    Returns JSON list of clients with aggregated metrics.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        profiles = await _get_db().tenant_customers.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)

        enriched = []
        for p in profiles:
            url = p.get("website_url")
            latest_scan = None
            total_scans = 0
            total_repairs = 0
            if url:
                all_scans = await _get_all_scans_for_url(url, limit=50)
                total_scans = len(all_scans)
                total_repairs = await _count_repairs_for_url(url)

                if all_scans:
                    s = all_scans[0]
                    latest_scan = {
                        "scan_id": s.get("scan_id"),
                        "overall_score": s.get("overall_score"),
                        "scores": s.get("scores", {}),
                        "summary": s.get("summary", {}),
                        "created_at": s.get("created_at"),
                    }

            enriched.append({
                **p,
                "total_scans": total_scans,
                "total_repairs": total_repairs,
                "latest_scan": latest_scan,
            })

        return {
            "clients": enriched,
            "total": len(enriched),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] Clients error: {e}")
        raise HTTPException(500, f"Failed to load clients: {str(e)}")


@router.get("/clients/{profile_id}")
async def get_client_detail(profile_id: str, admin=Depends(verify_admin)):
    """Get single client detail with full history."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        profile = await _get_db().tenant_customers.find_one(
            {"profile_id": profile_id}, {"_id": 0}
        )
        if not profile:
            raise HTTPException(404, "Client not found")

        url = profile.get("website_url")
        scans = []
        repairs = []
        if url:
            scans = await _get_all_scans_for_url(url, limit=20)
            variants = _url_variants(url)
            repairs = await _get_db().repair_fixes.find(
                {"$or": [{"website_url": {"$in": variants}}, {"scan_url": {"$in": variants}}]},
                {"_id": 0}
            ).sort("created_at", -1).limit(50).to_list(50)

        return {
            "client": profile,
            "scans": scans,
            "repairs": repairs,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Client detail error: {e}")
        raise HTTPException(500, f"Failed to load client: {str(e)}")


@router.get("/clients/{profile_id}/scans")
async def get_client_scans(
    profile_id: str,
    limit: int = Query(20, ge=1, le=100),
    admin=Depends(verify_admin)
):
    """Get scan history for a specific client."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        profile = await _get_db().tenant_customers.find_one(
            {"profile_id": profile_id}, {"_id": 0, "website_url": 1}
        )
        if not profile:
            raise HTTPException(404, "Client not found")

        url = profile.get("website_url")
        if not url:
            return {"scans": [], "total": 0}

        scans = await _get_all_scans_for_url(url, limit=limit)

        return {
            "scans": scans,
            "total": len(scans),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Client scans error: {e}")
        raise HTTPException(500, f"Failed to load scans: {str(e)}")


@router.get("/clients/{profile_id}/repairs")
async def get_client_repairs(
    profile_id: str,
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(verify_admin)
):
    """Get repair fixes for a specific client."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        profile = await _get_db().tenant_customers.find_one(
            {"profile_id": profile_id}, {"_id": 0, "website_url": 1}
        )
        if not profile:
            raise HTTPException(404, "Client not found")

        url = profile.get("website_url")
        if not url:
            return {"repairs": [], "total": 0}

        variants = _url_variants(url)
        repairs = await _get_db().repair_fixes.find(
            {"$or": [{"website_url": {"$in": variants}}, {"scan_url": {"$in": variants}}]},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit).to_list(limit)

        # Also gather inline repairs from scan_history
        scans_with_repairs = await _get_db().scan_history.find(
            {"website_url": {"$in": variants}, "repairs": {"$exists": True, "$ne": []}},
            {"_id": 0, "scan_id": 1, "repairs": 1, "created_at": 1, "overall_score": 1}
        ).sort("created_at", -1).limit(10).to_list(10)

        inline_repairs = []
        for scan in scans_with_repairs:
            for r in scan.get("repairs", []):
                inline_repairs.append({
                    "source": "scan_inline",
                    "scan_id": scan.get("scan_id"),
                    "scan_score": scan.get("overall_score"),
                    "scan_date": scan.get("created_at"),
                    **r
                })

        return {
            "repairs": repairs,
            "inline_repairs": inline_repairs,
            "total": len(repairs) + len(inline_repairs),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Client repairs error: {e}")
        raise HTTPException(500, f"Failed to load repairs: {str(e)}")


@router.post("/clients/{profile_id}/rescan")
async def trigger_client_rescan(profile_id: str, admin=Depends(verify_admin)):
    """
    Trigger a fresh live scan on a client's website.
    Runs the full scanner pipeline and saves to system_scans.
    Returns the new scan result immediately.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        profile = await _get_db().tenant_customers.find_one(
            {"profile_id": profile_id}, {"_id": 0}
        )
        if not profile:
            raise HTTPException(404, "Client not found")

        url = profile.get("website_url")
        if not url:
            raise HTTPException(400, "Client has no website URL")

        logger.info(f"[Mission Control] Triggering rescan for {profile.get('business_name')} ({url})")

        # Import scanner functions
        from routers.customer_scanner import (
            scan_performance, scan_security,
            scan_seo, scan_accessibility, calculate_aurem_impact
        )
        from utils.deep_scanner import deep_scan_website
        import httpx
        import asyncio

        scan_id = f"scan_{secrets.token_urlsafe(16)}"

        # Fetch website HTML (rendered via Playwright for SPA support)
        html_content = ""
        try:
            from utils.rendered_fetch import fetch_rendered_html
            html_content, _ = await fetch_rendered_html(url)
        except Exception as e:
            logger.warning(f"[Mission Control] Rendered fetch failed, falling back to raw: {e}")
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url)
                    html_content = response.text
            except Exception as e2:
                logger.warning(f"[Mission Control] Raw fetch also failed: {e2}")

        # Run deep scan + traditional scans in parallel
        deep_scan_results = await deep_scan_website(url)

        results = await asyncio.gather(
            scan_performance(url),
            scan_security(url, html_content),
            scan_seo(url, html_content),
            scan_accessibility(html_content),
        )
        perf_result, sec_result, seo_result, acc_result = results

        # Collect issues
        all_issues = []
        for r in results:
            all_issues.extend(r.get("issues", []))

        critical_count = len([i for i in all_issues if i.get("severity") == "critical"])
        scores = [perf_result["score"], sec_result["score"], seo_result["score"], acc_result["score"]]
        overall_score = int(sum(scores) / len(scores))

        aurem_impact = calculate_aurem_impact(all_issues)

        # Build recommendations
        recommendations = []
        critical_issues = [i for i in all_issues if i.get("severity") == "critical"]
        warning_issues = [i for i in all_issues if i.get("severity") == "warning"]
        for issue in (critical_issues + warning_issues)[:5]:
            recommendations.append({
                "priority": "high" if issue["severity"] == "critical" else "medium",
                "category": issue.get("category", "general"),
                "title": issue["issue"],
                "description": issue.get("details", ""),
                "solution": issue.get("aurem_solution", "")
            })

        scan_result = {
            "scan_id": scan_id,
            "website_url": url,
            "tenant_id": profile.get("tenant_id", "unknown"),
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "overall_score": overall_score,
            "issues_found": len(all_issues),
            "critical_issues": critical_count,
            "performance": perf_result,
            "security": sec_result,
            "seo": seo_result,
            "accessibility": acc_result,
            "recommendations": recommendations,
            "aurem_impact": aurem_impact,
            "deep_scan": deep_scan_results,
            "triggered_from": "mission_control",
        }

        # Enrich issues with fix status before saving (admin mode — no user_id scoping)
        result = await enrich_issues_with_fix_status(_db, all_issues, url)
        confirmed_resolved = []
        if result:
            detected_keys, fix_keys = result
            confirmed_resolved = build_confirmed_resolved(detected_keys, fix_keys)
        enrich_scan_result_issues(scan_result, all_issues, confirmed_resolved)

        # Save to system_scans
        scan_doc = {**scan_result, "scanned_by": "admin", "_id": scan_id}
        await _get_db().system_scans.insert_one(scan_doc)

        logger.info(f"[Mission Control] Rescan complete: {profile.get('business_name')} score={overall_score}")

        return {
            "scan": scan_result,
            "client": {
                "business_name": profile.get("business_name"),
                "website_url": url,
                "profile_id": profile_id,
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Rescan error: {e}")
        raise HTTPException(500, f"Rescan failed: {str(e)}")


@router.get("/overview")
async def get_overview_stats(admin=Depends(verify_admin)):
    """Get real-time overview statistics for the dashboard."""
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    try:
        total_clients = await _get_db().tenant_customers.count_documents({"is_self_client": {"$ne": True}})
        active_clients = await _get_db().tenant_customers.count_documents({"is_active": True, "is_self_client": {"$ne": True}})
        scan_history_count = await _get_db().scan_history.count_documents({})
        system_scans_count = await _get_db().system_scans.count_documents({})
        total_scans = scan_history_count + system_scans_count
        deployed_fixes = await _get_db().repair_fixes.count_documents({"status": "deployed"})
        total_repairs_collection = await _get_db().repair_fixes.count_documents({})
        total_users = await _get_db().users.count_documents({}) + await _get_db().platform_users.count_documents({})

        total_repairs = deployed_fixes or total_repairs_collection

        # Count inline repairs from scan_history
        pipeline = [
            {"$match": {"repairs": {"$exists": True, "$ne": []}}},
            {"$project": {"repair_count": {"$size": "$repairs"}}},
            {"$group": {"_id": None, "total": {"$sum": "$repair_count"}}}
        ]
        try:
            agg = await _get_db().scan_history.aggregate(pipeline).to_list(1)
            inline_repair_count = agg[0]["total"] if agg else 0
        except Exception:
            inline_repair_count = 0

        total_repairs = total_repairs_collection + inline_repair_count

        # Average scan score from both collections
        avg_scores = []
        for coll_name in ("scan_history", "system_scans"):
            coll = _db[coll_name]
            score_pipeline = [
                {"$match": {"overall_score": {"$exists": True}}},
                {"$group": {"_id": None, "avg": {"$avg": "$overall_score"}, "count": {"$sum": 1}}}
            ]
            try:
                agg = await coll.aggregate(score_pipeline).to_list(1)
                if agg:
                    avg_scores.append((agg[0]["avg"], agg[0]["count"]))
            except Exception:
                pass

        if avg_scores:
            weighted_sum = sum(a * c for a, c in avg_scores)
            total_count = sum(c for _, c in avg_scores)
            avg_score = round(weighted_sum / total_count) if total_count else 0
        else:
            avg_score = 0

        return {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "total_scans": total_scans,
            "total_repairs": total_repairs,
            "total_users": total_users,
            "avg_scan_score": avg_score,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] Overview error: {e}")
        raise HTTPException(500, f"Failed to load overview: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL HEALTH — onboarding gate visibility (P0)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/pixel-health")
async def get_pixel_health(admin=Depends(verify_admin)):
    """
    Founder-visible pixel deployment health.
    - pixel_installed: distinct sites with detected=true in last 24h via heartbeat
    - pending_patches: auto_fix_patches.status in (pending, queued)
    - applied_patches: patch_reports.status='applied'
    - failed_patches:  patch_reports.status='failed'
    - avg_install_time_minutes: signup -> first verified pixel detection

    Cached for 30s (iter 322e) — these aggregates run 4-6 distinct/count
    queries each call; founder dashboard polls this every few seconds, so
    a tiny TTL eliminates ~95% of the load.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")

    # Cache hit fast-path
    try:
        from utils.ttl_cache import cache_get, cache_set
        _cached = await cache_get("mc_pixel_health", "v1")
        if _cached is not None:
            return _cached
    except Exception:
        cache_get = cache_set = None  # type: ignore

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    # distinct verified sites in last 24h
    verified_urls = await db.pixel_verification_log.distinct(
        "url", {"detected": True, "verified_at": {"$gte": cutoff}}
    )
    pixel_installed = len(verified_urls)

    # all-time distinct verified sites
    pixel_installed_all_time = len(
        await db.pixel_verification_log.distinct("url", {"detected": True})
    )

    # patch counters (customer scope only — exclude aurem_self)
    pending_patches = await db.auto_fix_patches.count_documents(
        {"status": {"$in": ["pending", "queued", "generated"]}}
    )
    applied_patches = await db.patch_reports.count_documents({"status": "applied"})
    failed_patches = await db.patch_reports.count_documents({"status": "failed"})

    # avg install time: per user_id, first verification - earliest signup
    avg_install_minutes = None
    try:
        first_verifs = await db.pixel_verification_log.aggregate([
            {"$match": {"detected": True, "user_id": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": "$user_id", "first_verified": {"$min": "$verified_at"}}},
        ]).to_list(500)
        if first_verifs:
            deltas = []
            for v in first_verifs:
                user = await db.platform_users.find_one(
                    {"id": v["_id"]}, {"_id": 0, "created_at": 1}
                ) or await db.users.find_one(
                    {"id": v["_id"]}, {"_id": 0, "created_at": 1}
                )
                if not user or not user.get("created_at"):
                    continue
                try:
                    created = user["created_at"]
                    if isinstance(created, str):
                        created = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    fv = v["first_verified"]
                    if isinstance(fv, str):
                        fv = datetime.fromisoformat(fv.replace("Z", "+00:00"))
                    delta_min = (fv - created).total_seconds() / 60.0
                    if 0 < delta_min < 60 * 24 * 30:  # discard outliers
                        deltas.append(delta_min)
                except Exception:
                    continue
            if deltas:
                avg_install_minutes = round(sum(deltas) / len(deltas), 1)
    except Exception as e:
        logger.warning(f"[pixel-health] avg install time calc failed: {e}")

    # newly signed-up workspaces still missing pixel (gap funnel)
    total_workspaces = await db.workspaces.count_documents({}) + await db.tenant_customers.count_documents({})
    pixel_install_pct = round((pixel_installed_all_time / total_workspaces * 100), 1) if total_workspaces else 0.0

    payload = {
        "pixel_installed_24h": pixel_installed,
        "pixel_installed_all_time": pixel_installed_all_time,
        "total_workspaces": total_workspaces,
        "pixel_install_pct": pixel_install_pct,
        "pending_patches": pending_patches,
        "applied_patches": applied_patches,
        "failed_patches": failed_patches,
        "avg_install_time_minutes": avg_install_minutes,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if cache_set is not None:
            await cache_set("mc_pixel_health", "v1", payload, ttl=30)
    except Exception:
        pass
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE REGISTRY & API KEY MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/services")
async def get_service_registry(admin=Depends(verify_admin)):
    """
    Get all available services in TOON format
    
    Returns:
    Service[15]{id, cat, provider, cost, status, tiers}:
      gpt-4o, llm, OpenAI, 0.005/1k, active, [sta|pro|ent]
      gpt-4o-mini, llm, OpenAI, 0.00015/1k, active, [free|sta|pro|ent]
      voxtral-tts, voice, Mistral, 0.002/min, no_keys, [pro|ent]
      ...
    """
    toon_service = get_toon_service()
    
    try:
        services_toon = await toon_service.get_service_registry_toon()
        
        return {
            "format": "TOON",
            "data": services_toon,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] Services error: {e}")
        raise HTTPException(500, f"Failed to load services: {str(e)}")


@router.get("/api-keys")
async def get_api_keys(admin=Depends(verify_admin)):
    """
    Get all API keys in TOON format (encrypted keys not shown)
    
    Returns:
    APIKey[5]{service, preview, status, calls, spend, last_used}:
      gpt-4o, sk-proj-...ABC, active, 15000, 45.67, 2026-01-15T10:30
      voxtral-tts, sk-mist-...XYZ, active, 500, 12.34, 2026-01-14T15:20
      ...
    """
    toon_service = get_toon_service()
    
    try:
        keys_toon = await toon_service.get_api_keys_toon(admin)
        
        return {
            "format": "TOON",
            "data": keys_toon,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"[Mission Control] API keys error: {e}")
        raise HTTPException(500, f"Failed to load API keys: {str(e)}")


@router.post("/services/add-key")
async def add_api_key(request: AddAPIKeyRequest, admin=Depends(verify_admin)):
    """
    Add API key for a service
    This enables the service for all subscriptions that include it
    
    Request:
    {
      "service_id": "gpt-4o",
      "api_key": "sk-proj-...",
      "notes": "Production key - purchased 2026-01-15",
      "monthly_spend_limit": 1000.00
    }
    
    Response (TOON):
    APIKey[key_xxxxx]:
      service_id: gpt-4o
      preview: sk-proj-...ABC
      status: active
      added_at: 2026-01-15T10:30:00Z
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Generate key ID
        key_id = f"key_{secrets.token_hex(12)}"
        
        # Encrypt API key
        try:
            from utils.aurem_encryption import encrypt_api_key
            encrypted_key = encrypt_api_key(request.api_key)
        except ImportError:
            encrypted_key = request.api_key  # Fallback: store as-is
        
        # Create preview (first 8 + last 4 chars)
        preview = f"{request.api_key[:8]}...{request.api_key[-4:]}"
        
        # Store in database
        key_record = {
            "key_id": key_id,
            "service_id": request.service_id,
            "encrypted_key": encrypted_key,
            "key_preview": preview,
            "added_by": admin,  # Admin ID from header
            "added_at": datetime.now(timezone.utc),
            "status": "active",
            "total_calls": 0,
            "total_spend_usd": 0.0,
            "last_used": None,
            "monthly_spend_limit": request.monthly_spend_limit,
            "notes": request.notes
        }
        
        await _get_db().api_keys_registry.insert_one(key_record)
        
        # Update service status to 'active'
        await _get_db().service_registry.update_one(
            {"service_id": request.service_id},
            {"$set": {"status": "active", "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        logger.info(f"[Mission Control] Added API key for {request.service_id}")
        
        # Return TOON format
        response_toon = f"""APIKey[{key_id}]:
  service_id: {request.service_id}
  preview: {preview}
  status: active
  added_at: {key_record['added_at'].isoformat()}
  monthly_spend_limit: {request.monthly_spend_limit or 'unlimited'}"""
        
        return {
            "success": True,
            "format": "TOON",
            "data": response_toon,
            "key_id": key_id
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Add API key error: {e}")
        raise HTTPException(500, f"Failed to add API key: {str(e)}")


@router.post("/services/remove-key")
async def remove_api_key(request: RemoveAPIKeyRequest, admin=Depends(verify_admin)):
    """
    Remove/revoke an API key
    
    Response:
    {
      "success": true,
      "message": "API key revoked for gpt-4o"
    }
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Update key status to 'revoked'
        result = await _get_db().api_keys_registry.update_one(
            {"key_id": request.key_id, "service_id": request.service_id},
            {
                "$set": {
                    "status": "revoked",
                    "revoked_by": admin,
                    "revoked_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, "API key not found")
        
        # Check if service has other active keys
        active_keys = await _get_db().api_keys_registry.count_documents({
            "service_id": request.service_id,
            "status": "active"
        })
        
        # If no active keys, update service status
        if active_keys == 0:
            await _get_db().service_registry.update_one(
                {"service_id": request.service_id},
                {"$set": {"status": "no_keys"}}
            )
        
        logger.info(f"[Mission Control] Removed API key {request.key_id} for {request.service_id}")
        
        return {
            "success": True,
            "message": f"API key revoked for {request.service_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Remove API key error: {e}")
        raise HTTPException(500, f"Failed to remove API key: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTIONS MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/subscriptions")
async def get_all_subscriptions(
    tier: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    admin=Depends(verify_admin)
):
    """
    Get all subscriptions in TOON format
    
    Query params:
    - tier: Filter by tier (free, starter, professional, enterprise)
    - status: Filter by status (active, cancelled, past_due)
    - limit: Max results (default 100)
    
    Returns:
    Subscription[150]{id, user, tier, status, amount, period_end, usage}:
      sub_001, user_abc, professional, active, 399, 2026-02-01, {tokens:15k/200k}
      sub_002, user_def, starter, active, 99, 2026-02-05, {tokens:8k/50k}
      ...
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Build query
        query = {}
        if tier:
            query['tier'] = tier
        if status:
            query['status'] = status
        
        # Fetch subscriptions
        subs = await _get_db().subscriptions.find(
            query,
            {"_id": 0}
        ).limit(limit).to_list(limit)
        
        if not subs:
            return {
                "format": "TOON",
                "data": "Subscription[0]:",
                "count": 0
            }
        
        # Convert to TOON tabular format
        header = f"Subscription[{len(subs)}]{{id, user, tier, status, amount, period_end, usage}}"
        
        rows = []
        for sub in subs:
            sub_id = sub.get('id', sub.get('subscription_id', 'unknown'))[:12]
            user_id = sub.get('user_id', 'unknown')[:12]
            tier_val = sub.get('tier', 'free')
            status_val = sub.get('status', 'active')
            amount = sub.get('amount', 0)
            period_end = sub.get('current_period_end', 'N/A')
            if isinstance(period_end, datetime):
                period_end = period_end.strftime('%Y-%m-%d')
            
            # Compress usage
            usage = sub.get('usage', {})
            tokens_used = usage.get('ai_tokens_used', 0)
            tokens_limit = usage.get('ai_tokens_limit', 0)
            usage_str = f"{{tokens:{tokens_used}/{tokens_limit}}}"
            
            rows.append(f"{sub_id}, {user_id}, {tier_val}, {status_val}, {amount}, {period_end}, {usage_str}")
        
        toon_data = f"{header}:\n  " + "\n  ".join(rows)
        
        return {
            "format": "TOON",
            "data": toon_data,
            "count": len(subs)
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Subscriptions error: {e}")
        raise HTTPException(500, f"Failed to load subscriptions: {str(e)}")


@router.get("/subscriptions/{user_id}")
async def get_user_subscription(user_id: str, admin=Depends(verify_admin)):
    """
    Get specific user's subscription in TOON format
    
    Returns:
    Subscription[sub_xxxxx]:
      user_id: user_12345
      tier: professional
      status: active
      amount: 399
      usage: {tokens:15k/200k, formulas:5/50}
      services: Service[3]{id, status, tokens}: gpt-4o, active, 15000; ...
    """
    toon_service = get_toon_service()
    
    try:
        sub_toon = await toon_service.get_user_subscription_toon(user_id)
        
        return {
            "format": "TOON",
            "data": sub_toon
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] User subscription error: {e}")
        raise HTTPException(500, f"Failed to load user subscription: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# USAGE ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/usage")
async def get_usage_analytics(
    user_id: Optional[str] = None,
    service_id: Optional[str] = None,
    limit: int = 100,
    admin=Depends(verify_admin)
):
    """
    Get usage logs in TOON format
    
    Query params:
    - user_id: Filter by user
    - service_id: Filter by service
    - limit: Max results
    
    Returns:
    UsageLog[150]{user, service, tokens, cost, endpoint, time}:
      user_123, gpt-4o, 1500, 0.0075, /api/aurem/chat, 2026-01-15T10:30
      user_123, voxtral-tts, 0, 0.0020, /api/voice/tts, 2026-01-15T10:31
      ...
    """
    toon_service = get_toon_service()
    
    try:
        usage_toon = await toon_service.get_usage_analytics_toon(user_id, service_id, limit)
        
        return {
            "format": "TOON",
            "data": usage_toon,
            "filters": {
                "user_id": user_id,
                "service_id": service_id,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Usage analytics error: {e}")
        raise HTTPException(500, f"Failed to load usage analytics: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN/CREDIT RECHARGE
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/recharge")
async def recharge_service(request: RechargeRequest, admin=Depends(verify_admin)):
    """
    Recharge tokens/credits for a service
    
    Request:
    {
      "service_id": "openai-credits",
      "amount_usd": 100.00,
      "tokens_added": 20000000,
      "payment_method": "stripe",
      "notes": "Monthly recharge - Jan 2026"
    }
    
    Response (TOON):
    Recharge[rech_xxxxx]:
      service_id: openai-credits
      amount_usd: 100.00
      tokens_added: 20000000
      purchased_by: admin_123
      purchase_date: 2026-01-15T10:30:00Z
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Generate recharge ID
        recharge_id = f"rech_{secrets.token_hex(12)}"
        
        # Store recharge record
        recharge_record = {
            "recharge_id": recharge_id,
            "service_id": request.service_id,
            "amount_usd": request.amount_usd,
            "tokens_added": request.tokens_added,
            "credits_added": request.credits_added,
            "purchased_by": admin,
            "purchase_date": datetime.now(timezone.utc),
            "payment_method": request.payment_method,
            "notes": request.notes
        }
        
        await _get_db().token_recharges.insert_one(recharge_record)
        
        logger.info(f"[Mission Control] Recharged {request.service_id}: ${request.amount_usd}")
        
        # Return TOON format
        response_toon = f"""Recharge[{recharge_id}]:
  service_id: {request.service_id}
  amount_usd: {request.amount_usd}
  tokens_added: {request.tokens_added or 'N/A'}
  credits_added: {request.credits_added or 'N/A'}
  purchased_by: {admin}
  purchase_date: {recharge_record['purchase_date'].isoformat()}"""
        
        return {
            "success": True,
            "format": "TOON",
            "data": response_toon,
            "recharge_id": recharge_id
        }
        
    except Exception as e:
        logger.error(f"[Mission Control] Recharge error: {e}")
        raise HTTPException(500, f"Failed to process recharge: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE CONTROL (START/STOP)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/service/toggle")
async def toggle_service(request: ToggleServiceRequest, admin=Depends(verify_admin)):
    """
    Start, stop, or pause a service
    
    Request:
    {
      "service_id": "gpt-4o",
      "action": "pause"  # start, stop, pause
    }
    
    Response:
    {
      "success": true,
      "service_id": "gpt-4o",
      "new_status": "paused",
      "message": "Service gpt-4o paused"
    }
    """
    db = _get_db()
    if db is None:
        raise HTTPException(500, "Database not initialized")
    
    if request.action not in ["start", "stop", "pause"]:
        raise HTTPException(400, "Invalid action. Must be: start, stop, or pause")
    
    try:
        # Map action to status
        status_map = {
            "start": "active",
            "stop": "suspended",
            "pause": "paused"
        }
        new_status = status_map[request.action]
        
        # Update service status
        result = await _get_db().service_registry.update_one(
            {"service_id": request.service_id},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.now(timezone.utc),
                    "updated_by": admin
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(404, f"Service {request.service_id} not found")
        
        logger.info(f"[Mission Control] Service {request.service_id} {request.action}ed by {admin}")
        
        return {
            "success": True,
            "service_id": request.service_id,
            "new_status": new_status,
            "message": f"Service {request.service_id} {request.action}ed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Mission Control] Toggle service error: {e}")
        raise HTTPException(500, f"Failed to toggle service: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "admin-mission-control",
        "format": "TOON",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TENANTS SUMMARY — the 3 live numbers the founder watches
# Iter 320: Customer onboarding fix (scope: AUREM-as-tenant records only)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tenants-summary")
async def tenants_summary(admin=Depends(verify_admin)):
    """Live 3-number summary for the founder's Mission Control widget.

    Scoped to `tenant_customers` rows with `record_type == "aurem_tenant"` so
    existing CRM contact rows are never double-counted.

    Cached for 30s (iter 322e).
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    try:
        from utils.ttl_cache import cache_get, cache_set
        _cached = await cache_get("mc_tenants_summary", "v1")
        if _cached is not None:
            return _cached
    except Exception:
        cache_set = None  # type: ignore

    base = {"record_type": "aurem_tenant"}
    try:
        total = await db.tenant_customers.count_documents(base)
        pixel_ok = await db.tenant_customers.count_documents(
            {**base, "pixel_installed": True}
        )
        pending = await db.tenant_customers.count_documents(
            {**base, "pixel_installed": False, "status": "onboarding"}
        )
    except Exception as e:
        logger.warning(f"[mission-control] tenants-summary count error: {e}")
        raise HTTPException(500, f"count_error: {e}")

    payload = {
        "total_tenants": total,
        "pixel_installed_count": pixel_ok,
        "pending_onboarding_count": pending,
        "install_rate_pct": round((pixel_ok / total) * 100, 1) if total else 0.0,
        "healthy": total > 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if cache_set is not None:
            await cache_set("mc_tenants_summary", "v1", payload, ttl=30)
    except Exception:
        pass
    return payload


@router.get("/tenants-list")
async def tenants_list(limit: int = 50, admin=Depends(verify_admin)):
    """Paged list of AUREM tenants for Control Center drill-down."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    rows = await db.tenant_customers.find(
        {"record_type": "aurem_tenant"},
        {
            "_id": 0,
            "tenant_id": 1, "business_id": 1, "business_name": 1,
            "email": 1, "plan": 1, "status": 1,
            "pixel_installed": 1, "pixel_reminder_sent_at": 1,
            "pixel_nudge_count": 1, "channels_enabled": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1).to_list(max(1, min(limit, 200)))
    return {"count": len(rows), "tenants": rows}


# ═══════════════════════════════════════════════════════════════════════════════
# Iter 3: Hot Replies feed from the A2A chain (Closer stage)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/hot-replies")
async def hot_replies(
    hours: int = 48,
    limit: int = 20,
    admin=Depends(verify_admin),
):
    """Recent priority='hot' entries from `activity_feed` written by Closer."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    from datetime import timedelta
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(hours=max(1, min(hours, 168)))).isoformat()

    rows = await db.activity_feed.find(
        {
            "priority": "hot",
            "source": "closer",
            "timestamp": {"$gte": cutoff_iso},
        },
        {
            "_id": 0,
            "event_id": 1, "lead_id": 1, "business_name": 1,
            "score": 1, "intent": 1, "reason": 1,
            "channel": 1, "source": 1, "event": 1, "timestamp": 1,
        },
    ).sort("timestamp", -1).to_list(max(1, min(limit, 100)))
    return {
        "count": len(rows),
        "window_hours": hours,
        "replies": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
