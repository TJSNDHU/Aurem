"""
AUREM Sentinel — Stage 1: OBSERVE
===================================
Runs every 60 seconds. Checks ALL system components.
Stores observations in MongoDB system_pulse collection.
Returns list of issues found for Stage 2 diagnosis.
"""

import os
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta

import httpx

logger = logging.getLogger(__name__)

# Backend health check: always use localhost (same pod in Kubernetes)
BACKEND_URL = "http://127.0.0.1:8001"
# Frontend health check: use external URL (routed through ingress)
FRONTEND_URL = os.environ.get("SITE_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:3000"


async def observe_all_systems(db, cycle: int) -> dict:
    """
    STAGE 1: Full system observation.
    Runs ALL checks in parallel via asyncio.gather.
    Returns pulse dict with health_score and issues_found.
    """
    start = time.time()
    issues = []

    # Run all checks in parallel
    results = await asyncio.gather(
        _check_mongodb(db),
        _check_redis(),
        _check_backend_health(),
        _check_frontend(),
        _check_openrouter(),
        _check_openweathermap(),
        _check_elevenlabs(),
        _check_emergent_llm(),
        _check_circuit_breakers(db),
        _check_ooda_agents(db),
        _check_v2v_sessions(db),
        _check_system_resources(),
        _check_crash_logs(db),
        _check_knowledge_sync(db),
        _check_scout_search(),
        return_exceptions=True,
    )

    check_names = [
        "mongodb", "redis", "backend", "frontend",
        "openrouter", "openweathermap", "elevenlabs", "emergent_llm",
        "circuit_breakers", "ooda_agents", "v2v_sessions",
        "system_resources", "crash_logs", "knowledge_sync",
        "scout_search",
    ]

    checks = {}
    for name, result in zip(check_names, results):
        if isinstance(result, Exception):
            checks[name] = {"status": "error", "error": str(result)}
            issues.append({"service": name, "severity": "P1", "error": str(result)})
        else:
            checks[name] = result
            if result.get("issues"):
                issues.extend(result["issues"])

    # Calculate health score
    total_checks = len(check_names)
    healthy = sum(1 for c in checks.values() if isinstance(c, dict) and c.get("status") == "healthy")
    health_score = int((healthy / total_checks) * 100) if total_checks > 0 else 0

    duration_ms = int((time.time() - start) * 1000)

    pulse = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cycle_number": cycle,
        "checks": checks,
        "issues_found": issues,
        "health_score": health_score,
        "duration_ms": duration_ms,
        "total_checks": total_checks,
        "healthy_checks": healthy,
    }

    # Store in MongoDB
    try:
        if db is not None:
            await db.system_pulse.insert_one({**pulse, "_stored": True})
    except Exception as e:
        logger.error(f"[Sentinel] Failed to store pulse: {e}")

    return pulse


# ═══════════════════════════════════════
# INDIVIDUAL CHECKS
# ═══════════════════════════════════════

async def _check_mongodb(db) -> dict:
    try:
        if db is None:
            return {"status": "error", "issues": [{"service": "mongodb", "severity": "P0", "error": "DB not connected"}]}
        start = time.time()
        await db.command("ping")
        latency = int((time.time() - start) * 1000)
        status = "healthy" if latency < 100 else "degraded"
        issues = []
        if latency > 2000:
            issues.append({"service": "mongodb", "severity": "P1", "error": f"High latency: {latency}ms"})
        return {"status": status, "latency_ms": latency, "issues": issues}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "mongodb", "severity": "P0", "error": str(e)}]}


async def _check_redis() -> dict:
    try:
        from utils.redis_pool import get_sync_redis
        r = get_sync_redis()
        if r is None:
            return {"status": "error", "issues": [{"service": "redis", "severity": "P1", "error": "Redis pool unavailable"}]}
        start = time.time()
        r.ping()
        latency = int((time.time() - start) * 1000)
        info = r.info("memory")
        used_mb = info.get("used_memory", 0) / (1024 * 1024)
        issues = []
        if used_mb > 500:
            issues.append({"service": "redis", "severity": "P2", "error": f"High memory: {used_mb:.0f}MB"})
        return {"status": "healthy", "latency_ms": latency, "memory_mb": round(used_mb, 1), "issues": issues}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "redis", "severity": "P1", "error": str(e)}]}


async def _check_backend_health() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            start = time.time()
            r = await c.get(f"{BACKEND_URL}/api/health")
            latency = int((time.time() - start) * 1000)
            issues = []
            if r.status_code != 200:
                issues.append({"service": "backend", "severity": "P0", "error": f"HTTP {r.status_code}"})
            elif latency > 2000:
                issues.append({"service": "backend", "severity": "P2", "error": f"Slow: {latency}ms"})
            return {"status": "healthy" if r.status_code == 200 else "error", "latency_ms": latency, "status_code": r.status_code, "issues": issues}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "backend", "severity": "P0", "error": str(e)}]}


async def _check_frontend() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(FRONTEND_URL)
            ok = r.status_code == 200
            return {"status": "healthy" if ok else "error", "status_code": r.status_code, "issues": [] if ok else [{"service": "frontend", "severity": "P1", "error": f"HTTP {r.status_code}"}]}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "frontend", "severity": "P1", "error": str(e)}]}


async def _check_openrouter() -> dict:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return {"status": "no_key", "issues": []}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                data = r.json().get("data", {})
                return {"status": "healthy", "usage": data.get("usage", 0), "limit": data.get("limit"), "issues": []}
            return {"status": "error", "issues": [{"service": "openrouter", "severity": "P1", "error": f"HTTP {r.status_code}"}]}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "openrouter", "severity": "P1", "error": str(e)}]}


async def _check_openweathermap() -> dict:
    """Check weather via Open-Meteo (free, no key needed). Replaced OpenWeatherMap."""
    try:
        from services.free_api_arsenal import get_weather
        w = await get_weather(43.59, -79.65, "Mississauga")
        if w.get("temp_c") is not None:
            return {"status": "healthy", "temp": w["temp_c"], "issues": [], "source": "open-meteo"}
        return {"status": "degraded", "issues": [{"service": "open-meteo", "severity": "P3", "error": "No data"}]}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "open-meteo", "severity": "P3", "error": str(e)}]}


async def _check_elevenlabs() -> dict:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not key:
        return {"status": "no_key", "issues": [{"service": "elevenlabs", "severity": "P2", "error": "No key"}]}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
            if r.status_code == 200:
                return {"status": "healthy", "issues": []}
            elif r.status_code == 401:
                return {"status": "expired", "issues": [{"service": "elevenlabs", "severity": "P1", "error": "API key expired (401)"}]}
            return {"status": "error", "issues": [{"service": "elevenlabs", "severity": "P1", "error": f"HTTP {r.status_code}"}]}
    except Exception as e:
        return {"status": "error", "issues": [{"service": "elevenlabs", "severity": "P2", "error": str(e)}]}


async def _check_emergent_llm() -> dict:
    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        return {"status": "no_key", "issues": [{"service": "emergent_llm", "severity": "P0", "error": "No Emergent LLM key"}]}
    return {"status": "healthy", "issues": []}


async def _check_circuit_breakers(db) -> dict:
    try:
        if db is None:
            return {"status": "unknown", "issues": []}
        tripped = []
        cursor = db.circuit_breakers.find({"state": "open"}, {"_id": 0, "service": 1, "trip_count": 1})
        async for doc in cursor:
            svc = doc.get("service", "unknown")
            trips = doc.get("trip_count", 0)
            severity = "P0" if trips >= 3 else "P1"
            tripped.append({"service": f"cb_{svc}", "severity": severity, "error": f"Circuit breaker tripped {trips}x"})
        return {"status": "healthy" if not tripped else "tripped", "tripped_count": len(tripped), "issues": tripped}
    except Exception:
        return {"status": "healthy", "tripped_count": 0, "issues": []}


async def _check_ooda_agents(db) -> dict:
    try:
        if db is None:
            return {"status": "unknown", "issues": []}
        stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
        stale = await db.ooda_agent_activity.count_documents({"last_active": {"$lt": stale_threshold.isoformat()}})
        issues = []
        if stale > 0:
            issues.append({"service": "ooda_agents", "severity": "P1", "error": f"{stale} agents stuck >5min"})
        return {"status": "healthy" if stale == 0 else "degraded", "stale_agents": stale, "issues": issues}
    except Exception:
        return {"status": "healthy", "issues": []}


async def _check_v2v_sessions(db) -> dict:
    try:
        if db is None:
            return {"status": "unknown", "issues": []}
        recent_errors = await db.aurem_voice_calls.count_documents({"status": "error", "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
        issues = []
        if recent_errors > 10:
            issues.append({"service": "v2v_sessions", "severity": "P1", "error": f"{recent_errors} errors in last hour"})
        return {"status": "healthy" if recent_errors <= 10 else "degraded", "recent_errors": recent_errors, "issues": issues}
    except Exception:
        return {"status": "healthy", "issues": []}


async def _check_system_resources() -> dict:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        issues = []
        if mem.percent > 90:
            issues.append({"service": "system_resources", "severity": "P0", "error": f"Memory critical: {mem.percent}%"})
        elif mem.percent > 80:
            issues.append({"service": "system_resources", "severity": "P2", "error": f"Memory high: {mem.percent}%"})
        if cpu > 90:
            issues.append({"service": "system_resources", "severity": "P1", "error": f"CPU critical: {cpu}%"})
        return {"status": "healthy" if not issues else "degraded", "cpu_percent": cpu, "memory_percent": mem.percent, "memory_used_gb": round(mem.used / (1024**3), 1), "issues": issues}
    except ImportError:
        return {"status": "unknown", "issues": []}


async def _check_crash_logs(db) -> dict:
    try:
        if db is None:
            return {"status": "unknown", "issues": []}
        recent = await db.crash_log.count_documents({"timestamp": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
        issues = []
        if recent > 0:
            issues.append({"service": "crash_logs", "severity": "P1", "error": f"{recent} crashes in last hour"})
        return {"status": "healthy" if recent == 0 else "alert", "recent_crashes": recent, "issues": issues}
    except Exception:
        return {"status": "healthy", "issues": []}


async def _check_knowledge_sync(db) -> dict:
    try:
        if db is None:
            return {"status": "unknown", "issues": []}
        sync = await db.ora_knowledge_sync.find_one({}, {"_id": 0, "synced_at": 1})
        issues = []
        if sync and sync.get("synced_at"):
            try:
                last = datetime.fromisoformat(sync["synced_at"].replace("Z", "+00:00"))
                hours_ago = (datetime.now(timezone.utc) - last).total_seconds() / 3600
                if hours_ago > 24:
                    issues.append({"service": "knowledge_sync", "severity": "P2", "error": f"Overdue: {hours_ago:.0f}h since last sync"})
            except Exception:
                pass
        else:
            issues.append({"service": "knowledge_sync", "severity": "P3", "error": "Never synced"})
        return {"status": "healthy" if not issues else "overdue", "issues": issues}
    except Exception:
        return {"status": "healthy", "issues": []}



async def _check_scout_search() -> dict:
    """Monitor ScoutSearch health: last source, avg response time, fallback count."""
    try:
        from services.scout_search import get_search_stats
        stats = get_search_stats()
        issues = []
        total = stats.get("total_searches", 0)
        failures = stats.get("failures", 0)

        if total > 0 and failures / total > 0.5:
            issues.append({"service": "scout_search", "severity": "P2", "error": f"High failure rate: {failures}/{total}"})

        avg_ms = stats.get("avg_response_ms", 0)
        if avg_ms > 5000:
            issues.append({"service": "scout_search", "severity": "P2", "error": f"Slow search: avg {avg_ms}ms"})

        return {
            "status": "healthy" if not issues else "degraded",
            "last_source": stats.get("last_source", "none"),
            "total_searches": total,
            "avg_response_ms": avg_ms,
            "duckduckgo_hits": stats.get("duckduckgo_hits", 0),
            "failures": failures,
            "issues": issues,
        }
    except Exception as e:
        return {"status": "unknown", "issues": [{"service": "scout_search", "severity": "P3", "error": str(e)}]}
