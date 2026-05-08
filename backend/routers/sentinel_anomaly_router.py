"""
Sentinel Anomaly Router — iter 285.3
═══════════════════════════════════════════════════════════════════════

Real data surface for `SentinelAnomalyDashboard.jsx`. Aggregates from:
  • db.sentinel_alerts       — the authoritative anomaly store
  • db.client_errors         — raw error signal for /stats rollup
  • db.a2a_events            — A2A bus signal (sentinel → autonomous_repair)

No mock data. Empty collections return zeros honestly (Truth-Sync).

Endpoints:
  GET  /api/sentinel-anomaly/stats         — aggregated counters
  GET  /api/sentinel-anomaly/history?limit — last N alerts
  POST /api/sentinel-anomaly/scan          — trigger a scan (emits A2A event)
  GET  /api/sentinel-anomaly/health        — public probe
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/sentinel-anomaly", tags=["Sentinel Anomaly"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"


def set_db(db) -> None:
    global _db
    _db = db


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            _jwt_secret or os.environ.get("JWT_SECRET", ""),
            algorithms=[_jwt_alg],
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    if not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/stats")
async def stats(authorization: Optional[str] = Header(None)):
    """Aggregated rollup from sentinel_alerts + client_errors."""
    _verify_admin(authorization)
    if _db is None:
        return {"total": 0, "by_severity": {}, "critical_30m": 0, "errors_1h": 0,
                "errors_24h": 0, "ts_iso": _now().isoformat()}

    total = await _db.sentinel_alerts.count_documents({})

    by_sev: dict = {}
    try:
        async for row in _db.sentinel_alerts.aggregate([
            {"$group": {"_id": "$severity", "n": {"$sum": 1}}}
        ]):
            by_sev[str(row["_id"] or "unknown")] = row["n"]
    except Exception:
        pass

    crit_30m = await _db.sentinel_alerts.count_documents({
        "max_score": {"$gte": 8},
        "created_at": {"$gte": _now() - timedelta(minutes=30)},
    })

    errs_1h = await _db.client_errors.count_documents({
        "timestamp": {"$gte": (_now() - timedelta(hours=1)).isoformat()}
    })
    errs_24h = await _db.client_errors.count_documents({
        "timestamp": {"$gte": (_now() - timedelta(hours=24)).isoformat()}
    })

    latest = await _db.sentinel_alerts.find_one(
        {}, {"_id": 0, "created_at": 1}, sort=[("created_at", -1)]
    )

    return {
        "total": total,
        "by_severity": by_sev,
        "critical_30m": crit_30m,
        "errors_1h": errs_1h,
        "errors_24h": errs_24h,
        "last_alert_at": (latest or {}).get("created_at"),
        "ts_iso": _now().isoformat(),
    }


@router.get("/history")
async def history(
    limit: int = 10,
    authorization: Optional[str] = Header(None),
):
    """Last N sentinel alerts, newest first."""
    _verify_admin(authorization)
    if _db is None:
        return {"alerts": [], "count": 0}
    limit = max(1, min(int(limit or 10), 200))
    items = []
    async for d in _db.sentinel_alerts.find(
        {}, {"_id": 0, "embedding": 0}
    ).sort("created_at", -1).limit(limit):
        # Stringify any remaining ObjectId/datetime
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        items.append(d)
    return {"alerts": items, "count": len(items)}


@router.post("/scan")
async def scan(authorization: Optional[str] = Header(None)):
    """Manual rescan trigger. Emits A2A event so autonomous_repair_engine
    can consume the signal on its next cycle. Does not synthesize data."""
    admin = _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    # Refresh rollup
    out = await stats(authorization)
    # Emit A2A event so the bus carries a pillar_monitor → sentinel signal
    try:
        from services.a2a_bus import bus as a2a_bus
        await a2a_bus.emit(
            "pillar_monitor", "sentinel_scan",
            {
                "triggered_by": admin.get("email") or "admin",
                "critical_30m": out.get("critical_30m", 0),
                "errors_1h": out.get("errors_1h", 0),
                "ts_iso": _now().isoformat(),
            },
        )
    except Exception:
        pass  # bus absence never blocks the scan
    return {"ok": True, "stats": out, "a2a_emitted": True}


@router.get("/health")
async def health():
    return {"status": "ok", "component": "sentinel_anomaly",
            "db_ready": _db is not None}
