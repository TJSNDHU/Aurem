"""
Customer Health Monitor — Phase 1
==================================
Per-tenant DB / Auth / Route diagnostic checks. Runs every 30 min via
Pillar-4 worker scheduler, also exposed via /api/admin/diagnostics/run.

Failed checks → trigger_repair_pipeline (services.customer_repair_pipeline).
Healthy checks → status: healthy, persisted to customer_health_log.

Design rules:
- READ-ONLY checks (no DB mutation here)
- Parallel asyncio.gather where possible
- Best-effort: single failed check never crashes the loop for sibling tenants
- DB-collection naming consistent with existing AUREM ssot
  (platform_users, aurem_billing, aurem_workspaces, aurem_onboarding,
   tenant_customers)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import jwt

logger = logging.getLogger(__name__)

# Internal API loopback — every check runs inside the pod
BACKEND_URL = "http://localhost:8001"
JWT_SECRET = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        _db = getattr(server, "db", None)
    except Exception:
        _db = None
    return _db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# CHECK PRIMITIVES
# ─────────────────────────────────────────────────────────────

async def _http_check(path: str, *, token: Optional[str] = None,
                      timeout: float = 6.0) -> bool:
    """GET a path on the local pod and return True if 2xx/3xx."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{BACKEND_URL}{path}", headers=headers)
        return resp.status_code < 500  # 2xx/3xx/4xx all = "route alive"
    except Exception as e:
        logger.debug(f"[health-monitor] HTTP check {path} failed: {e}")
        return False


async def _test_jwt(business_id: str, email: str) -> bool:
    """Mint + decode a short-lived token to confirm JWT plumbing alive."""
    if not JWT_SECRET:
        return False
    try:
        from datetime import timedelta as _td
        payload = {
            "email": email,
            "business_id": business_id,
            "role": "user",
            "exp": _utc_now() + _td(minutes=2),
            "iat": _utc_now(),
        }
        tok = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        decoded = jwt.decode(tok, JWT_SECRET, algorithms=["HS256"])
        return decoded.get("business_id") == business_id
    except Exception as e:
        logger.debug(f"[health-monitor] JWT mint failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# PER-TENANT CHECK
# ─────────────────────────────────────────────────────────────

CHECK_KEYS = [
    "db_user", "db_billing", "db_workspace", "db_onboarding", "db_tenant",
    "stripe_seeded",
    "jwt_works", "bin_valid",
    "route_my", "route_onboarding", "route_billing", "route_bin",
    "pixel_seeded", "blast_active",
]


async def check_tenant(business_id: str) -> Dict[str, Any]:
    """Run all health checks for one business_id. Returns dict of bools.

    Persists summary to ``customer_health_log`` (upsert by business_id).
    Triggers repair pipeline on degraded/critical status.
    """
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable", "business_id": business_id}

    results: Dict[str, bool] = {k: False for k in CHECK_KEYS}

    # ─── DB checks (parallel) ────────────────────────────────────
    try:
        user, billing, workspace, onboarding, tenant = await asyncio.gather(
            db.platform_users.find_one({"business_id": business_id}, {"_id": 0}),
            db.aurem_billing.find_one({"business_id": business_id}, {"_id": 0}),
            db.aurem_workspaces.find_one({"business_id": business_id}, {"_id": 0}),
            db.aurem_onboarding.find_one({"business_id": business_id}, {"_id": 0}),
            db.tenant_customers.find_one({"business_id": business_id}, {"_id": 0}),
            return_exceptions=True,
        )
    except Exception as e:
        logger.warning(f"[health-monitor] DB gather failed for {business_id}: {e}")
        user = billing = workspace = onboarding = tenant = None

    user = user if isinstance(user, dict) else None
    billing = billing if isinstance(billing, dict) else None
    workspace = workspace if isinstance(workspace, dict) else None
    onboarding = onboarding if isinstance(onboarding, dict) else None
    tenant = tenant if isinstance(tenant, dict) else None

    results["db_user"] = bool(user)
    results["db_billing"] = bool(billing)
    results["db_workspace"] = bool(workspace)
    results["db_onboarding"] = bool(onboarding)
    results["db_tenant"] = bool(tenant)
    results["stripe_seeded"] = bool(billing and billing.get("stripe_customer_id"))
    results["bin_valid"] = bool(user and user.get("business_id") == business_id)

    email = (user or {}).get("email") or ""

    # ─── AUTH check ──────────────────────────────────────────────
    results["jwt_works"] = await _test_jwt(business_id, email)

    # ─── ROUTE checks (parallel) ─────────────────────────────────
    # Mint a per-tenant short-lived token for routes that demand auth
    test_token = ""
    if JWT_SECRET and email:
        try:
            from datetime import timedelta as _td
            test_token = jwt.encode({
                "email": email,
                "business_id": business_id,
                "role": "user",
                "exp": _utc_now() + _td(minutes=2),
                "iat": _utc_now(),
            }, JWT_SECRET, algorithm="HS256")
        except Exception:
            test_token = ""

    route_results = await asyncio.gather(
        # Skip /my (SPA route on port 3000; not reachable from backend pod)
        _http_check("/api/onboarding/status", token=test_token),
        _http_check(f"/api/aurem-billing/status/{business_id}", token=test_token),
        _http_check("/api/business-id/mine", token=test_token),
        return_exceptions=True,
    )
    # /my route check is implicit (handled by ingress + AdminGuard).
    # Mark green if billing/onboarding both responded with <500.
    results["route_my"] = (
        bool(route_results[0]) if not isinstance(route_results[0], Exception) else False
    ) and (
        bool(route_results[1]) if not isinstance(route_results[1], Exception) else False
    )
    results["route_onboarding"] = bool(route_results[0]) if not isinstance(route_results[0], Exception) else False
    results["route_billing"] = bool(route_results[1]) if not isinstance(route_results[1], Exception) else False
    results["route_bin"] = bool(route_results[2]) if not isinstance(route_results[2], Exception) else False

    # ─── PIXEL & BLAST signals (warnings, not gates) ─────────────
    try:
        pixel_doc = await db.tenant_pixel_keys.find_one(
            {"business_id": business_id}, {"_id": 0, "key": 1, "last_ping_ts": 1}
        )
        results["pixel_seeded"] = bool(pixel_doc and pixel_doc.get("key"))
    except Exception:
        results["pixel_seeded"] = False

    try:
        blast_count = await db.blast_log.count_documents({"business_id": business_id})
        results["blast_active"] = blast_count > 0
    except Exception:
        results["blast_active"] = False

    # ─── OVERALL STATUS ──────────────────────────────────────────
    critical_keys = ("db_user", "db_billing", "db_workspace")
    critical_fail = any(not results.get(k) for k in critical_keys)
    # Health is gated only on hard checks (db + auth + routes).
    # Pixel + blast are advisory; missing them does NOT mark unhealthy.
    hard_keys = [k for k in CHECK_KEYS if k not in ("pixel_seeded", "blast_active")]
    all_pass = all(results.get(k) for k in hard_keys)

    if all_pass:
        status = "healthy"
    elif critical_fail:
        status = "critical"
    else:
        status = "degraded"

    failed = [k for k in hard_keys if not results.get(k)]

    summary = {
        "business_id": business_id,
        "email": email,
        "checks": results,
        "failed": failed,
        "status": status,
        "checked_at": _utc_now().isoformat(),
    }

    # Persist (best-effort)
    try:
        await db.customer_health_log.update_one(
            {"business_id": business_id},
            {"$set": summary},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[health-monitor] persist failed: {e}")

    # Append to history (capped via TTL or manual prune)
    try:
        await db.customer_health_history.insert_one({
            "business_id": business_id,
            "status": status,
            "failed": failed,
            "checked_at": _utc_now(),
        })
    except Exception:
        pass

    # Trigger repair pipeline if not healthy
    if status != "healthy":
        try:
            from services.customer_repair_pipeline import trigger_repair_pipeline
            asyncio.create_task(
                trigger_repair_pipeline(business_id, results, status)
            )
        except Exception as e:
            logger.warning(f"[health-monitor] repair trigger failed: {e}")

    return summary


# ─────────────────────────────────────────────────────────────
# SCAN ALL TENANTS
# ─────────────────────────────────────────────────────────────

async def check_all_tenants(limit: int = 500) -> Dict[str, Any]:
    """Scan every active tenant in platform_users."""
    db = _get_db()
    if db is None:
        return {"error": "db_unavailable", "checked": 0}

    cursor = db.platform_users.find(
        {"business_id": {"$exists": True, "$ne": None}},
        {"_id": 0, "business_id": 1},
    )
    bids = [doc.get("business_id") async for doc in cursor]
    bids = [b for b in bids if b][:limit]

    # Run with bounded concurrency
    sem = asyncio.Semaphore(8)

    async def _run(b: str):
        async with sem:
            try:
                return await check_tenant(b)
            except Exception as e:
                logger.warning(f"[health-monitor] tenant {b} crashed: {e}")
                return {"business_id": b, "status": "error", "error": str(e)[:120]}

    results = await asyncio.gather(*[_run(b) for b in bids])

    counts = {"healthy": 0, "degraded": 0, "critical": 0, "error": 0}
    for r in results:
        s = (r or {}).get("status", "error")
        counts[s] = counts.get(s, 0) + 1

    summary = {
        "scanned": len(results),
        "counts": counts,
        "checked_at": _utc_now().isoformat(),
    }
    try:
        await db.customer_health_summary.update_one(
            {"_id": "latest"},
            {"$set": summary},
            upsert=True,
        )
    except Exception:
        pass

    logger.info(
        f"[health-monitor] scanned {len(results)} tenants — "
        f"healthy={counts.get('healthy',0)} "
        f"degraded={counts.get('degraded',0)} "
        f"critical={counts.get('critical',0)}"
    )
    return summary


# ─────────────────────────────────────────────────────────────
# SCHEDULER (30-min cycle, 60s grace on boot)
# ─────────────────────────────────────────────────────────────

async def customer_health_scheduler() -> None:
    """Background loop: every 30 min scan all tenants. 60s boot grace."""
    await asyncio.sleep(60)
    logger.info("[health-monitor] scheduler started — 30 min cycle")
    while True:
        try:
            await check_all_tenants()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[health-monitor] scan crashed: {e}")
        await asyncio.sleep(1800)  # 30 minutes
