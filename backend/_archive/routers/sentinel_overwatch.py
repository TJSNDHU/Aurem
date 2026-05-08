"""
Sentinel Overwatch — Sovereign Node Monitoring & Control API
============================================================
Real-time monitoring, auto-failover, and remote kill-switch for the local LLM.
"""
import logging
import asyncio
import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/overwatch", tags=["Sentinel Overwatch"])
logger = logging.getLogger(__name__)

# In-memory metrics ring buffer (last 60 readings)
_metrics_buffer = []
_MAX_BUFFER = 120

# Auto-failover config
_failover_config = {
    "tps_threshold": 1.0,
    "latency_threshold_ms": 8000,
    "auto_failover_enabled": True,
    "failover_active": False,
    "last_failover_trigger": None,
}


class FailoverConfig(BaseModel):
    tps_threshold: Optional[float] = None
    latency_threshold_ms: Optional[int] = None
    auto_failover_enabled: Optional[bool] = None


class KillSwitchRequest(BaseModel):
    action: str  # "kill" or "restore"


class PinAuthRequest(BaseModel):
    pin: str


async def _get_auth(authorization: str = Header(None)):
    """Validate JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    try:
        import jwt, os
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/auth/pin")
async def overwatch_pin_auth(req: PinAuthRequest):
    """
    PIN-based authentication for the Overwatch PWA.
    Returns a JWT token so the PWA can make authenticated API calls
    even when opened as a standalone app (no shared browser session).
    """
    import jwt, os
    from datetime import timedelta

    valid_pin = os.getenv("OVERWATCH_PIN", "1234")
    if req.pin != valid_pin:
        raise HTTPException(status_code=401, detail="Invalid PIN")

    jwt_secret = os.getenv("JWT_SECRET")
    if not jwt_secret:
        raise HTTPException(status_code=500, detail="Server misconfigured")

    payload = {
        "sub": "overwatch-admin",
        "email": "overwatch@aurem.local",
        "is_admin": True,
        "source": "overwatch_pin",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return {"token": token, "expires_in": 604800}


@router.get("/pulse")
async def overwatch_pulse(authorization: str = Header(None)):
    """
    Full system pulse — returns Sovereign Node status, TPS metrics,
    tunnel health, and failover state. Called every 5s by the Overwatch UI.
    """
    await _get_auth(authorization)

    from services.local_llm_service import get_config, check_ollama_status, is_available

    config = get_config()
    status = await check_ollama_status()

    # Quick latency probe
    latency_ms = None
    tps_estimate = None
    probe_ok = False

    if status["online"] and config["enabled"] and not _failover_config["failover_active"]:
        try:
            import httpx
            t0 = time.time()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{config['ollama_url']}/v1/chat/completions",
                    headers={},
                    json={
                        "model": config["model"],
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 5,
                        "stream": False,
                    }
                )
                elapsed = time.time() - t0
                latency_ms = int(elapsed * 1000)
                if resp.status_code == 200:
                    data = resp.json()
                    tokens = data.get("usage", {}).get("completion_tokens", 3)
                    tps_estimate = round(tokens / elapsed, 1) if elapsed > 0 else 0
                    probe_ok = True
        except Exception as e:
            logger.debug(f"[Overwatch] Probe failed: {e}")
            latency_ms = None

    # Store metric
    metric = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "online": status["online"],
        "latency_ms": latency_ms,
        "tps": tps_estimate,
        "model": config["model"],
        "enabled": config["enabled"],
        "failover_active": _failover_config["failover_active"],
    }
    _metrics_buffer.append(metric)
    if len(_metrics_buffer) > _MAX_BUFFER:
        _metrics_buffer.pop(0)

    # Auto-failover check
    auto_triggered = False
    if (
        _failover_config["auto_failover_enabled"]
        and not _failover_config["failover_active"]
        and probe_ok
        and tps_estimate is not None
    ):
        if tps_estimate < _failover_config["tps_threshold"]:
            logger.warning(f"[Overwatch] AUTO-FAILOVER: TPS {tps_estimate} < threshold {_failover_config['tps_threshold']}")
            _failover_config["failover_active"] = True
            _failover_config["last_failover_trigger"] = datetime.now(timezone.utc).isoformat()
            from services.local_llm_service import _config
            _config["enabled"] = False
            auto_triggered = True

            # Log to sentinel traces
            try:
                import server
                if hasattr(server, "db") and server.db is not None:
                    await server.db.agent_traces.insert_one({
                        "agent": "sentinel_overwatch",
                        "action": "auto_failover",
                        "detail": f"TPS dropped to {tps_estimate} (threshold: {_failover_config['tps_threshold']}). Switched to Cloud.",
                        "severity": "critical",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception:
                pass

    # Get recent request log from DB
    request_log = []
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            cursor = server.db.local_llm_usage.find(
                {}, {"_id": 0}
            ).sort("timestamp", -1).limit(10)
            request_log = await cursor.to_list(length=10)
    except Exception:
        pass

    # Get sales/leads metrics
    sales_metrics = {"daily_leads": 0, "total_scans": 0, "repairs_deployed": 0, "total_aurem_leads": 0, "chat_sessions": 0, "whatsapp_chats": 0}
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            db = server.db
            sales_metrics["total_scans"] = await db.system_scans.count_documents({})
            sales_metrics["repairs_deployed"] = await db.customer_website_fixes.count_documents({"status": "deployed"})
            sales_metrics["daily_leads"] = await db.tenant_customers.count_documents({})
            # Total Aurem Leads = tenant_customers + comm_leads (deduplicated concept)
            comm_leads = await db.comm_leads.count_documents({})
            sales_metrics["total_aurem_leads"] = sales_metrics["daily_leads"] + comm_leads
            # Omnichannel activity
            try:
                sales_metrics["chat_sessions"] = len(await db.live_chat_messages.distinct("session_id"))
            except Exception:
                pass
            try:
                sales_metrics["whatsapp_chats"] = len(await db.whatsapp_messages.distinct("chat_id"))
            except Exception:
                pass
    except Exception:
        pass

    # Get retrieval quality metrics
    retrieval_quality = {}
    try:
        from services.hybrid_search import get_retrieval_metrics
        retrieval_quality = get_retrieval_metrics()
    except Exception:
        pass

    # Get knowledge graph stats
    graph_stats = {}
    try:
        from services.graphify_service import get_graph_stats
        graph_stats = get_graph_stats()
    except Exception:
        pass

    # Get sharded cache stats
    cache_stats = {}
    try:
        from services.sharded_cache import get_lane_stats
        cache_stats = await get_lane_stats()
    except Exception:
        pass

    # Get BitNet worker stats
    worker_stats = {}
    try:
        from services.bitnet_worker import get_worker_stats
        worker_stats = get_worker_stats()
    except Exception:
        pass

    # Get swarm stats
    swarm_stats = {}
    try:
        from services.agent_cards import get_swarm_stats
        swarm_stats = get_swarm_stats()
    except Exception:
        pass

    # Get CRAG metrics
    crag_stats = {}
    try:
        from services.crag_service import get_crag_metrics
        crag_stats = get_crag_metrics()
    except Exception:
        pass

    # Get voice stats
    voice_stats = {}
    try:
        from services.sovereign_voice import get_voice_stats
        voice_stats = get_voice_stats()
    except Exception:
        pass

    # Get Shannon security posture
    security_posture = {}
    try:
        from services.shannon_security import get_security_posture
        security_posture = get_security_posture()
    except Exception:
        pass

    # Get DB health summary (cached — full report is expensive)
    db_health = {}
    try:
        from services.db_optimizer import _cached_db_summary
        db_health = _cached_db_summary()
    except Exception:
        pass

    return {
        "sovereign": {
            "online": status["online"] and not _failover_config["failover_active"],
            "model": config["model"],
            "url": config["ollama_url"],
            "enabled": config["enabled"],
            "models_available": status.get("models", []),
            "model_loaded": status.get("model_available", False),
        },
        "performance": {
            "latency_ms": latency_ms,
            "tps": tps_estimate,
            "probe_ok": probe_ok,
        },
        "failover": {
            **_failover_config,
            "auto_triggered": auto_triggered,
            "mode": "CLOUD" if _failover_config["failover_active"] or not config["enabled"] else "SOVEREIGN",
        },
        "metrics_history": _metrics_buffer[-30:],
        "request_log": request_log,
        "sales": sales_metrics,
        "retrieval": retrieval_quality,
        "knowledge_graph": graph_stats,
        "cache": cache_stats,
        "worker": worker_stats,
        "swarm": swarm_stats,
        "crag": crag_stats,
        "voice": voice_stats,
        "security": security_posture,
        "database": db_health,
    }


@router.post("/kill-switch")
async def kill_switch(req: KillSwitchRequest, authorization: str = Header(None)):
    """Remote kill-switch: instantly toggle between Sovereign and Cloud mode."""
    await _get_auth(authorization)

    from services.local_llm_service import _config, save_config

    if req.action == "kill":
        _config["enabled"] = False
        _failover_config["failover_active"] = True
        _failover_config["last_failover_trigger"] = datetime.now(timezone.utc).isoformat()
        await save_config()
        logger.warning("[Overwatch] KILL SWITCH ACTIVATED — Switched to Cloud mode")

        try:
            import server
            if hasattr(server, "db") and server.db is not None:
                await server.db.agent_traces.insert_one({
                    "agent": "sentinel_overwatch",
                    "action": "kill_switch",
                    "detail": "Manual kill-switch activated. All traffic routed to Cloud.",
                    "severity": "warning",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass

        return {"success": True, "mode": "CLOUD", "message": "Kill switch activated. All traffic routed to Cloud GPT-4o."}

    elif req.action == "restore":
        _config["enabled"] = True
        _failover_config["failover_active"] = False
        await save_config()
        logger.info("[Overwatch] Sovereign Node RESTORED")

        try:
            import server
            if hasattr(server, "db") and server.db is not None:
                await server.db.agent_traces.insert_one({
                    "agent": "sentinel_overwatch",
                    "action": "restore",
                    "detail": "Sovereign Node restored. Traffic routing back to local Ollama.",
                    "severity": "info",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass

        return {"success": True, "mode": "SOVEREIGN", "message": "Sovereign Node restored. Local inference active."}

    raise HTTPException(status_code=400, detail="action must be 'kill' or 'restore'")


@router.post("/failover-config")
async def update_failover_config(cfg: FailoverConfig, authorization: str = Header(None)):
    """Update auto-failover thresholds."""
    await _get_auth(authorization)

    if cfg.tps_threshold is not None:
        _failover_config["tps_threshold"] = max(1.0, cfg.tps_threshold)
    if cfg.latency_threshold_ms is not None:
        _failover_config["latency_threshold_ms"] = max(1000, cfg.latency_threshold_ms)
    if cfg.auto_failover_enabled is not None:
        _failover_config["auto_failover_enabled"] = cfg.auto_failover_enabled

    return {"success": True, "config": _failover_config}


@router.get("/failover-config")
async def get_failover_config(authorization: str = Header(None)):
    """Get current auto-failover thresholds."""
    await _get_auth(authorization)
    return _failover_config


@router.get("/stress-report")
async def get_stress_report(authorization: str = Header(None)):
    """Return the latest stress test metrics from the buffer."""
    await _get_auth(authorization)

    if not _metrics_buffer:
        return {"message": "No metrics collected yet. Open the Overwatch dashboard to start collecting."}

    tps_values = [m["tps"] for m in _metrics_buffer if m.get("tps") is not None]
    latencies = [m["latency_ms"] for m in _metrics_buffer if m.get("latency_ms") is not None]

    import statistics
    return {
        "total_readings": len(_metrics_buffer),
        "avg_tps": round(statistics.mean(tps_values), 1) if tps_values else None,
        "min_tps": min(tps_values) if tps_values else None,
        "max_tps": max(tps_values) if tps_values else None,
        "avg_latency_ms": round(statistics.mean(latencies)) if latencies else None,
        "uptime_pct": round(sum(1 for m in _metrics_buffer if m["online"]) / len(_metrics_buffer) * 100, 1),
        "failover_config": _failover_config,
    }
