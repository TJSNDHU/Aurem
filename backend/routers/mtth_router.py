"""
MTTH & Transparency Wall Router — iter 285.4
═══════════════════════════════════════════════════════════════════════

Two new live endpoints:

1. MTTH (Mean Time To Heal) metric card
   GET /api/admin/mtth/summary
   GET /api/admin/mtth/history?limit

   Sources:
     • db.autonomous_repair_events — cycle_started_at + verify_outcome
     • db.sentinel_alerts          — sentinel alert created_at
   Output: median / p95 / last heal, count 7d / 30d, longest outage.

2. Transparency Wall (public-ish + admin rollup)
   GET /api/admin/transparency/wall
   Source of truth: A2A audit connectivity + widget audit + truth_logs.
   Output: widget greens, a2a pipelines, auto_heals_24h, open_criticals,
            last_truth_failure, platform_uptime_days.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import List, Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/admin", tags=["MTTH & Transparency"])

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


def _parse_ts(v) -> Optional[datetime]:
    if not v:
        return None
    try:
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
    except Exception:
        return None
    return None


# ──────────────────────────────────────────────────────────────────────
# MTTH — Mean Time To Heal
# ──────────────────────────────────────────────────────────────────────

async def _collect_heal_durations(since: datetime) -> List[float]:
    """Return list of heal-duration seconds for the window.

    Heal duration = verify_outcome.recovered_at - cycle.ts_iso
    from db.autonomous_repair_events (kind='verify', ok=True).
    """
    if _db is None:
        return []
    durations: List[float] = []
    try:
        cursor = _db.autonomous_repair_events.find(
            {"kind": "verify", "ok": True, "ts_iso": {"$gte": since.isoformat()}},
            {"_id": 0, "ts_iso": 1, "evidence": 1, "cycle_ts_iso": 1},
        ).sort("ts_iso", -1).limit(500)
        async for d in cursor:
            verify_at = _parse_ts(d.get("ts_iso"))
            cycle_at = _parse_ts(d.get("cycle_ts_iso") or (d.get("evidence") or {}).get("cycle_started_at"))
            if verify_at and cycle_at and verify_at >= cycle_at:
                durations.append((verify_at - cycle_at).total_seconds())
    except Exception:
        pass
    return durations


# iter 285.5 — classification → tier mapping
TIER_MAP = {
    "stale_preview_pod":          1,
    "rate_limited_429":           1,
    "auth_token_expired":         1,
    "chunk_load_error":           2,
    "backend_5xx":                2,
    "sentinel_anomaly_critical":  2,
    "unknown":                    3,
}


def _tier_for(classification: str) -> int:
    return TIER_MAP.get((classification or "unknown").lower(), 3)


async def _collect_heals_with_tier(since: datetime) -> list:
    """Return [{duration_seconds, tier, classification}] for window."""
    if _db is None:
        return []
    rows = []
    try:
        cursor = _db.autonomous_repair_events.find(
            {"kind": "verify", "ok": True, "ts_iso": {"$gte": since.isoformat()}},
            {"_id": 0, "ts_iso": 1, "evidence": 1, "cycle_ts_iso": 1, "classification": 1},
        ).sort("ts_iso", -1).limit(500)
        async for d in cursor:
            verify_at = _parse_ts(d.get("ts_iso"))
            cycle_at = _parse_ts(d.get("cycle_ts_iso") or (d.get("evidence") or {}).get("cycle_started_at"))
            if verify_at and cycle_at and verify_at >= cycle_at:
                cls = d.get("classification") or (d.get("evidence") or {}).get("classification") or "unknown"
                rows.append({
                    "duration_seconds": (verify_at - cycle_at).total_seconds(),
                    "tier": _tier_for(cls),
                    "classification": cls,
                })
    except Exception:
        pass
    return rows


@router.get("/mtth/summary")
async def mtth_summary(authorization: Optional[str] = Header(None)):
    """Median / p95 / count / last heal over 24h · 7d · 30d windows."""
    _verify_admin(authorization)

    now = _now()
    out: dict = {
        "windows": {},
        "last_heal_at": None,
        "ts_iso": now.isoformat(),
    }

    for label, delta in (("24h", timedelta(hours=24)),
                          ("7d", timedelta(days=7)),
                          ("30d", timedelta(days=30))):
        durations = await _collect_heal_durations(now - delta)
        durations.sort()
        if durations:
            med = median(durations)
            p95 = durations[max(0, int(len(durations) * 0.95) - 1)]
            longest = durations[-1]
        else:
            med = p95 = longest = 0.0
        out["windows"][label] = {
            "count": len(durations),
            "median_seconds": round(med, 1),
            "p95_seconds": round(p95, 1),
            "longest_seconds": round(longest, 1),
            "median_human": _humanize_seconds(med),
            "p95_human": _humanize_seconds(p95),
        }

    # Last healed
    if _db is not None:
        try:
            latest = await _db.autonomous_repair_events.find_one(
                {"kind": "verify", "ok": True},
                {"_id": 0, "ts_iso": 1},
                sort=[("ts_iso", -1)],
            )
            if latest:
                out["last_heal_at"] = latest.get("ts_iso")
        except Exception:
            pass

    # Verdict pill — <10 min median = green, <30 min = amber, else red
    med_24h = out["windows"]["24h"]["median_seconds"]
    if out["windows"]["24h"]["count"] == 0:
        out["verdict"] = "idle"
    elif med_24h < 600:
        out["verdict"] = "green"
    elif med_24h < 1800:
        out["verdict"] = "amber"
    else:
        out["verdict"] = "red"

    return out


def _humanize_seconds(s: float) -> str:
    if s <= 0:
        return "—"
    if s < 60:
        return f"{int(s)}s"
    if s < 3600:
        return f"{int(s // 60)}m {int(s % 60)}s"
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    return f"{h}h {m}m"


@router.get("/mtth/history")
async def mtth_history(
    limit: int = 30,
    authorization: Optional[str] = Header(None),
):
    """Recent heal cycles for charting. Each row = {ts, duration_sec, classification}."""
    _verify_admin(authorization)
    if _db is None:
        return {"heals": [], "count": 0}
    limit = max(1, min(int(limit or 30), 200))
    heals = []
    try:
        cursor = _db.autonomous_repair_events.find(
            {"kind": "verify", "ok": True},
            {"_id": 0, "ts_iso": 1, "evidence": 1, "classification": 1, "cycle_ts_iso": 1},
        ).sort("ts_iso", -1).limit(limit)
        async for d in cursor:
            va = _parse_ts(d.get("ts_iso"))
            ca = _parse_ts(d.get("cycle_ts_iso") or (d.get("evidence") or {}).get("cycle_started_at"))
            dur = None
            if va and ca and va >= ca:
                dur = round((va - ca).total_seconds(), 1)
            cls = d.get("classification") or (d.get("evidence") or {}).get("classification") or "unknown"
            heals.append({
                "ts": d.get("ts_iso"),
                "duration_seconds": dur,
                "duration_human": _humanize_seconds(dur or 0),
                "classification": cls,
                "tier": _tier_for(cls),
            })
    except Exception as e:
        return {"heals": [], "count": 0, "error": str(e)[:200]}
    return {"heals": heals, "count": len(heals)}


@router.get("/mtth/by-tier")
async def mtth_by_tier(authorization: Optional[str] = Header(None)):
    """Tier breakdown for 24h·7d·30d windows.

    Tier 1 (cache/rate-limit purge) — should be <2min median
    Tier 2 (pixel patch / backend 5xx) — should be <10min median
    Tier 3 (unknown / staged code fix) — typically 30m+
    """
    _verify_admin(authorization)
    now = _now()
    out = {"tiers": {}, "ts_iso": now.isoformat()}

    TIER_NAMES = {1: "Tier 1 · Cache/Rate", 2: "Tier 2 · Pixel/5xx", 3: "Tier 3 · Code Fix"}

    for label, delta in (("24h", timedelta(hours=24)),
                          ("7d", timedelta(days=7)),
                          ("30d", timedelta(days=30))):
        rows = await _collect_heals_with_tier(now - delta)
        per_tier = {1: [], 2: [], 3: []}
        for r in rows:
            per_tier[r["tier"]].append(r["duration_seconds"])

        tier_out = {}
        for tier, durations in per_tier.items():
            durations.sort()
            if durations:
                med = median(durations)
                p95 = durations[max(0, int(len(durations) * 0.95) - 1)]
            else:
                med = p95 = 0.0
            tier_out[f"tier_{tier}"] = {
                "name": TIER_NAMES[tier],
                "count": len(durations),
                "median_seconds": round(med, 1),
                "p95_seconds": round(p95, 1),
                "median_human": _humanize_seconds(med),
                "p95_human": _humanize_seconds(p95),
            }
        out["tiers"][label] = tier_out

    return out


# ──────────────────────────────────────────────────────────────────────
# Transparency Wall — single-source trust dashboard
# ──────────────────────────────────────────────────────────────────────

@router.get("/transparency/wall")
async def transparency_wall(authorization: Optional[str] = Header(None)):
    """Live trust metrics — consumed by SystemOverview Transparency Wall."""
    _verify_admin(authorization)
    now = _now()
    out: dict = {"ts_iso": now.isoformat()}

    # 1. Widget audit — use the shared WIDGET_REGISTRY directly
    try:
        from routers.a2a_audit_router import WIDGET_REGISTRY
        out["widgets"] = {"registered": len(WIDGET_REGISTRY)}
    except Exception as e:
        out["widgets"] = {"registered": 0, "error": str(e)[:120]}

    # 2. A2A subsystems (reuse connectivity logic)
    try:
        from routers.a2a_audit_router import (
            _check_a2a_events, _check_a2a_handoffs, _check_learning_bus,
            _check_hermes_memory, _check_pillar_heartbeat,
            _check_autonomous_repair, _check_truth_ledger,
        )
        subs = []
        for fn in (_check_a2a_events, _check_a2a_handoffs, _check_learning_bus,
                    _check_hermes_memory, _check_pillar_heartbeat,
                    _check_autonomous_repair, _check_truth_ledger):
            try:
                subs.append(await fn())
            except Exception:
                subs.append({"name": fn.__name__, "ok": False})
        out["a2a"] = {
            "total": len(subs),
            "green": sum(1 for s in subs if s.get("ok")),
        }
    except Exception:
        out["a2a"] = {"total": 7, "green": 0}

    # 3. Auto-heals 24h
    if _db is not None:
        try:
            cutoff = (now - timedelta(hours=24)).isoformat()
            auto_heals = await _db.autonomous_repair_events.count_documents(
                {"kind": "verify", "ok": True, "ts_iso": {"$gte": cutoff}}
            )
            out["auto_heals_24h"] = auto_heals
        except Exception:
            out["auto_heals_24h"] = 0
    else:
        out["auto_heals_24h"] = 0

    # 4. Open critical alerts
    if _db is not None:
        try:
            cutoff = now - timedelta(hours=24)
            open_crit = await _db.sentinel_alerts.count_documents({
                "max_score": {"$gte": 8},
                "created_at": {"$gte": cutoff},
            })
            out["open_criticals_24h"] = open_crit
        except Exception:
            out["open_criticals_24h"] = 0
    else:
        out["open_criticals_24h"] = 0

    # 5. Last truth-ledger failure
    if _db is not None:
        try:
            latest = await _db.truth_logs.find_one(
                {"event": "failure"},
                {"_id": 0, "ts_iso": 1, "description": 1, "actor": 1},
                sort=[("ts_iso", -1)],
            )
            if latest:
                out["last_truth_failure"] = latest
            else:
                out["last_truth_failure"] = None
        except Exception:
            out["last_truth_failure"] = None
    else:
        out["last_truth_failure"] = None

    # 6. Errors 1h (as current pulse)
    if _db is not None:
        try:
            cutoff_iso = (now - timedelta(hours=1)).isoformat()
            out["errors_1h"] = await _db.client_errors.count_documents(
                {"timestamp": {"$gte": cutoff_iso}}
            )
        except Exception:
            out["errors_1h"] = 0

    # 7. Verdict — green if auto-heals ok and no open criticals and low errors
    critical = out.get("open_criticals_24h", 0)
    errs = out.get("errors_1h", 0)
    a2a_green = out.get("a2a", {}).get("green", 0) == out.get("a2a", {}).get("total", 7)
    if critical == 0 and errs < 5 and a2a_green:
        out["verdict"] = "green"
    elif critical > 0 or errs >= 20:
        out["verdict"] = "red"
    else:
        out["verdict"] = "amber"

    return out


@router.get("/mtth/health")
async def mtth_health():
    return {"status": "ok", "component": "mtth_and_transparency",
            "db_ready": _db is not None}
