"""
Dogfood Pulse — health snapshot for the dogfood BIN (AUR-FNDR-001).

Single endpoint:
  GET /api/admin/dogfood/pulse

Returns per-service rollup over the last 14 days:
  - service_id / service_name
  - total_calls
  - success_rate (0.0–1.0)
  - last_used (ISO timestamp or null)
  - status: "active" | "dead_zone" (zero calls in 14 days)

UI use: AdminBrainPage tile "Dogfood Health" — show RED badge
if any service is in dead_zone status.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/dogfood", tags=["Dogfood Pulse"])

_db = None
DOGFOOD_BIN = os.environ.get("DOGFOOD_BIN", "AUR-FNDR-001")
DOGFOOD_EMAIL = os.environ.get("DOGFOOD_EMAIL", "teji.ss1986+dogfood@gmail.com")
WINDOW_DAYS = 14


def set_db(database) -> None:
    global _db
    _db = database


async def _verify_admin(request: Request) -> dict:
    """Admin-only — reads JWT, checks `users` collection for is_admin."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    token = auth[7:]
    secret = (
        os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    )
    if not secret:
        raise HTTPException(500, "JWT secret not configured")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "Token missing email")
    if _db is None:
        raise HTTPException(503, "Service not ready")
    user = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1, "email": 1},
    )
    if not user or not (
        user.get("is_admin")
        or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return user


@router.get("/pulse")
async def dogfood_pulse(_admin: dict = __import__("fastapi").Depends(_verify_admin)):
    """14-day health rollup for the dogfood BIN."""
    if _db is None:
        raise HTTPException(503, "DB not ready")

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)
    since_iso = since.isoformat()

    # 1) All catalog services (so dead zones show up even with zero rows)
    catalog = await _db.service_catalog.find(
        {}, {"_id": 0, "service_id": 1, "name": 1, "status": 1, "cluster": 1}
    ).to_list(length=200)
    service_by_id: Dict[str, dict] = {s["service_id"]: s for s in catalog if s.get("service_id")}

    # 2) Aggregate usage from `service_usage_log` keyed by BIN.
    #    Fields stored by service_gate: business_id, service, ts (iso str), count, path
    pipeline: List[dict] = [
        {"$match": {
            "business_id": DOGFOOD_BIN,
            "ts": {"$gte": since_iso},
        }},
        {"$group": {
            "_id": "$service",
            "total_calls": {"$sum": {"$ifNull": ["$count", 1]}},
            "last_used": {"$max": "$ts"},
            "events": {"$sum": 1},
        }},
    ]
    usage_rows: List[dict] = []
    try:
        async for row in _db.service_usage_log.aggregate(pipeline):
            usage_rows.append(row)
    except Exception as e:
        logger.warning(f"[DogfoodPulse] usage_log aggregate failed: {e}")
    usage_by_service: Dict[str, dict] = {r["_id"]: r for r in usage_rows if r.get("_id")}

    # 3) Success-rate proxy from `service_call_log` (if present).
    #    Optional collection — many gated handlers log here with status="ok"/"error".
    success_by_service: Dict[str, dict] = {}
    try:
        pipe2 = [
            {"$match": {
                "business_id": DOGFOOD_BIN,
                "ts": {"$gte": since_iso},
            }},
            {"$group": {
                "_id": "$service",
                "ok": {"$sum": {"$cond": [{"$eq": ["$status", "ok"]}, 1, 0]}},
                "err": {"$sum": {"$cond": [{"$eq": ["$status", "error"]}, 1, 0]}},
                "total": {"$sum": 1},
            }},
        ]
        async for row in _db.service_call_log.aggregate(pipe2):
            success_by_service[row["_id"]] = row
    except Exception:
        pass  # Optional table

    # 4) Build per-service rollup — every catalog service, even with zero usage.
    services: List[Dict[str, Any]] = []
    dead_zone_count = 0
    active_count = 0
    total_calls = 0
    seen_services: set = set()
    for sid, meta in sorted(service_by_id.items(), key=lambda kv: kv[0]):
        seen_services.add(sid)
        u = usage_by_service.get(sid)
        calls = int(u["total_calls"]) if u else 0
        last_used = u.get("last_used") if u else None
        sc = success_by_service.get(sid)
        if sc and sc.get("total"):
            success_rate = round(sc["ok"] / sc["total"], 3)
        else:
            # No call-log → assume the bare invoke succeeded if any usage exists
            success_rate = 1.0 if calls > 0 else 0.0
        is_dead = calls == 0
        if is_dead:
            dead_zone_count += 1
        else:
            active_count += 1
        total_calls += calls
        services.append({
            "service_id": sid,
            "service_name": meta.get("name") or sid,
            "cluster": meta.get("cluster") or "",
            "catalog_status": meta.get("status") or "unknown",
            "total_calls": calls,
            "success_rate": success_rate,
            "last_used": last_used,
            "status": "dead_zone" if is_dead else "active",
        })

    # 4b) Surface any usage-tracked services NOT in the catalog (e.g. `total_scout`).
    #     These are still real customer touch-points worth monitoring.
    for sid, u in sorted(usage_by_service.items()):
        if sid in seen_services or not sid:
            continue
        calls = int(u.get("total_calls") or 0)
        sc = success_by_service.get(sid)
        if sc and sc.get("total"):
            success_rate = round(sc["ok"] / sc["total"], 3)
        else:
            success_rate = 1.0 if calls > 0 else 0.0
        if calls == 0:
            dead_zone_count += 1
        else:
            active_count += 1
        total_calls += calls
        services.append({
            "service_id": sid,
            "service_name": sid.replace("_", " ").title(),
            "cluster": "off-catalog",
            "catalog_status": "off-catalog",
            "total_calls": calls,
            "success_rate": success_rate,
            "last_used": u.get("last_used"),
            "status": "dead_zone" if calls == 0 else "active",
        })

    return {
        "ok": True,
        "bin": DOGFOOD_BIN,
        "email": DOGFOOD_EMAIL,
        "window_days": WINDOW_DAYS,
        "generated_at": now.isoformat(),
        "summary": {
            "total_services": len(services),
            "active": active_count,
            "dead_zone": dead_zone_count,
            "total_calls": total_calls,
            "has_dead_zones": dead_zone_count > 0,
        },
        "services": services,
    }
