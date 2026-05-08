"""
Sovereign Node & Empire HUD Router — iter 285.6
═══════════════════════════════════════════════════════════════════════

Single router that powers:

  1. Sovereign Nodes (Legion = local phone server / edge node)
     - POST /api/sovereign/heartbeat  (called BY the node)
     - GET  /api/sovereign/nodes      (list + status)
     - POST /api/sovereign/queue      (buffer event for offline node)
     - POST /api/sovereign/sync/{node_id} (drain queue when back online)

  2. Empire HUD integrations (Twilio / WHAPI / Resend / Stripe)
     - GET  /api/empire-hud/nodes     (all nodes + integration status)

No mocks. Legion status is derived from real heartbeat timestamps.
Integration status is derived from env vars + circuit breaker state.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api", tags=["Sovereign Node & Empire HUD"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"

# Offline threshold — node is "offline" if last heartbeat older than this
HEARTBEAT_TIMEOUT_SEC = int(os.environ.get("SOVEREIGN_HEARTBEAT_TIMEOUT", "120"))


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


# ═══════════════════════════════════════════════════════════════════════
# Sovereign Node (Legion)
# ═══════════════════════════════════════════════════════════════════════

@router.post("/sovereign/heartbeat")
async def heartbeat(
    payload: dict,
    authorization: Optional[str] = Header(None),
):
    """Called BY the Legion device (or any sovereign node) every 60s.

    Body: {node_id, node_name, ip, version?, metadata?}
    Admin-auth required so random attackers can't pollute the registry.
    """
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    node_id = (payload or {}).get("node_id")
    if not node_id:
        raise HTTPException(400, "node_id required")

    now_iso = _now().isoformat()
    doc = {
        "node_id": node_id,
        "node_name": (payload or {}).get("node_name") or node_id,
        "ip": (payload or {}).get("ip") or "unknown",
        "version": (payload or {}).get("version") or "unknown",
        "metadata": (payload or {}).get("metadata") or {},
        "last_heartbeat_at": now_iso,
        "status": "online",
    }
    await _db.sovereign_nodes.update_one(
        {"node_id": node_id},
        {"$set": doc, "$setOnInsert": {"first_seen_at": now_iso}},
        upsert=True,
    )

    # If there's a queued event backlog, surface count so the node can drain
    queue_count = await _db.sovereign_queue.count_documents(
        {"node_id": node_id, "status": "pending"}
    )

    # Fire A2A event so the bus knows the node is alive
    try:
        from services.a2a_bus import bus as a2a_bus
        await a2a_bus.emit(
            from_agent=f"sovereign:{node_id}",
            event="node_heartbeat",
            payload={"node_id": node_id, "queue_count": queue_count, "ts_iso": now_iso},
        )
    except Exception:
        pass

    return {"ok": True, "node_id": node_id, "queue_count": queue_count,
            "ts_iso": now_iso}


@router.get("/sovereign/nodes")
async def list_nodes(authorization: Optional[str] = Header(None)):
    """Return all registered sovereign nodes with computed status.

    Status = online if last heartbeat within HEARTBEAT_TIMEOUT_SEC, else offline.
    """
    _verify_admin(authorization)
    if _db is None:
        return {"nodes": [], "count": 0}
    now = _now()
    cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT_SEC)
    nodes = []
    async for d in _db.sovereign_nodes.find({}, {"_id": 0}).sort("last_heartbeat_at", -1):
        last_hb = d.get("last_heartbeat_at")
        try:
            last_dt = datetime.fromisoformat(str(last_hb).replace("Z", "+00:00"))
        except Exception:
            last_dt = None
        if last_dt and last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        is_online = bool(last_dt and last_dt >= cutoff)
        age_sec = round((now - last_dt).total_seconds(), 1) if last_dt else None
        # Attach queue count
        queue_count = await _db.sovereign_queue.count_documents(
            {"node_id": d["node_id"], "status": "pending"}
        )
        nodes.append({
            **d,
            "status": "online" if is_online else "offline",
            "seconds_since_heartbeat": age_sec,
            "queue_count": queue_count,
        })
    return {"nodes": nodes, "count": len(nodes), "ts_iso": now.isoformat(),
            "heartbeat_timeout_sec": HEARTBEAT_TIMEOUT_SEC}


@router.post("/sovereign/queue")
async def queue_event(
    payload: dict,
    authorization: Optional[str] = Header(None),
):
    """Buffer an event for an offline sovereign node.

    Body: {node_id, event_type, event_payload}
    """
    admin = _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    node_id = (payload or {}).get("node_id")
    if not node_id:
        raise HTTPException(400, "node_id required")
    now_iso = _now().isoformat()
    doc = {
        "node_id": node_id,
        "event_type": (payload or {}).get("event_type") or "generic",
        "event_payload": (payload or {}).get("event_payload") or {},
        "status": "pending",
        "queued_at": now_iso,
        "queued_by": admin.get("email") or admin.get("sub") or "admin",
    }
    await _db.sovereign_queue.insert_one(dict(doc))
    return {"ok": True, "node_id": node_id, "status": "pending"}


@router.post("/sovereign/sync/{node_id}")
async def drain_queue(
    node_id: str,
    authorization: Optional[str] = Header(None),
):
    """Drain the offline-event queue for a node (called when it reconnects)."""
    _verify_admin(authorization)
    if _db is None:
        raise HTTPException(500, "db_unset")
    # Pull all pending events for this node
    pending = []
    async for d in _db.sovereign_queue.find(
        {"node_id": node_id, "status": "pending"}, {"_id": 0}
    ).sort("queued_at", 1).limit(500):
        pending.append(d)
    # Mark them all delivered in one update
    drained_at = _now().isoformat()
    r = await _db.sovereign_queue.update_many(
        {"node_id": node_id, "status": "pending"},
        {"$set": {"status": "delivered", "drained_at": drained_at}},
    )
    return {"ok": True, "node_id": node_id, "events": pending,
            "drained": r.modified_count, "ts_iso": drained_at}


@router.get("/sovereign/health")
async def sovereign_health():
    return {"status": "ok", "component": "sovereign_node",
            "db_ready": _db is not None}


# ═══════════════════════════════════════════════════════════════════════
# Empire HUD — nodes with real integration status
# ═══════════════════════════════════════════════════════════════════════

def _integration_status(env_key: str, *more_keys: str) -> dict:
    """Check env vars + basic config presence. Returns status + configured bool."""
    keys = (env_key,) + more_keys
    missing = [k for k in keys if not os.environ.get(k)]
    if not missing:
        return {"status": "configured", "configured": True,
                "missing_keys": [], "verdict": "green"}
    if len(missing) == len(keys):
        return {"status": "not_configured", "configured": False,
                "missing_keys": missing, "verdict": "grey"}
    return {"status": "partial", "configured": False,
            "missing_keys": missing, "verdict": "amber"}


@router.get("/empire-hud/nodes")
async def empire_hud_nodes(authorization: Optional[str] = Header(None)):
    """Return all Empire HUD nodes (sovereign + integrations) with live status.

    Consumed by the EmpireHUDMap frontend component. Zero mocks.
    """
    _verify_admin(authorization)
    now = _now()

    # Integration nodes (env-derived + circuit-breaker enhanced)
    integrations = [
        {
            "id": "twilio",
            "name": "Twilio",
            "kind": "integration",
            "role": "SMS / Voice",
            "icon": "phone",
            **_integration_status("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"),
        },
        {
            "id": "whapi",
            "name": "WHAPI",
            "kind": "integration",
            "role": "WhatsApp Business",
            "icon": "message-circle",
            **_integration_status("WHAPI_TOKEN", "WHAPI_CHANNEL_ID"),
        },
        {
            "id": "resend",
            "name": "Resend",
            "kind": "integration",
            "role": "Transactional Email",
            "icon": "mail",
            **_integration_status("RESEND_API_KEY"),
        },
        {
            "id": "stripe",
            "name": "Stripe",
            "kind": "integration",
            "role": "Billing & Subscriptions",
            "icon": "credit-card",
            **_integration_status("STRIPE_SECRET_KEY", "STRIPE_API_KEY"),
        },
    ]

    # Overlay circuit breaker state if we have it
    if _db is not None:
        try:
            async for row in _db.circuit_breakers.find(
                {}, {"_id": 0, "service": 1, "state": 1, "last_failure_at": 1}
            ):
                svc = str(row.get("service", "")).lower()
                for node in integrations:
                    if node["id"] in svc or svc in node["id"]:
                        cb_state = str(row.get("state", "")).lower()
                        if cb_state in ("open", "tripped"):
                            node["verdict"] = "red"
                            node["status"] = "circuit_open"
                            node["circuit_last_failure"] = row.get("last_failure_at")
                        elif cb_state == "half_open":
                            node["verdict"] = "amber"
                            node["status"] = "circuit_half_open"
        except Exception:
            pass

    # Sovereign nodes (Legion + any registered)
    sovereigns = []
    if _db is not None:
        cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT_SEC)
        async for d in _db.sovereign_nodes.find({}, {"_id": 0}).sort("last_heartbeat_at", -1):
            last_hb = d.get("last_heartbeat_at")
            try:
                last_dt = datetime.fromisoformat(str(last_hb).replace("Z", "+00:00"))
            except Exception:
                last_dt = None
            if last_dt and last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            is_online = bool(last_dt and last_dt >= cutoff)
            queue_count = await _db.sovereign_queue.count_documents(
                {"node_id": d["node_id"], "status": "pending"}
            )
            sovereigns.append({
                "id": d["node_id"],
                "name": d.get("node_name") or d["node_id"],
                "kind": "sovereign",
                "role": "Edge / Local Server",
                "icon": "smartphone",
                "ip": d.get("ip", "unknown"),
                "last_seen": last_hb,
                "queue_count": queue_count,
                "version": d.get("version", "unknown"),
                "configured": True,
                "status": "online" if is_online else "offline",
                "verdict": "green" if is_online else "red",
            })
    # If no sovereign registered yet, show a placeholder Legion node so the
    # HUD always has that slot visible (status=not_configured / grey).
    if not sovereigns:
        sovereigns.append({
            "id": "legion",
            "name": "Legion (Sovereign Node)",
            "kind": "sovereign",
            "role": "Edge / Local Server",
            "icon": "smartphone",
            "ip": "—",
            "last_seen": None,
            "queue_count": 0,
            "version": "—",
            "configured": False,
            "status": "not_registered",
            "verdict": "grey",
        })

    nodes = sovereigns + integrations
    total = len(nodes)
    green = sum(1 for n in nodes if n.get("verdict") == "green")
    return {
        "nodes": nodes,
        "total": total,
        "green": green,
        "amber": sum(1 for n in nodes if n.get("verdict") == "amber"),
        "red": sum(1 for n in nodes if n.get("verdict") == "red"),
        "grey": sum(1 for n in nodes if n.get("verdict") == "grey"),
        "ts_iso": now.isoformat(),
    }
