"""
Legion Nodes Health Router — Iteration 215
===========================================
Unified single-call health endpoint for every Legion integration:

  - EvoMap Evolver   (services.evolver_client)
  - SmolMachines     (services.sandbox_client)
  - Carbonyl Browser (services.carbonyl_fetcher)
  - OpenFang Webhook (env + recent imports)

Powers the "Legion Nodes" card on /admin/control-center and
/admin/openfang without forcing the UI to fan-out 4 calls.

GET  /api/admin/legion/health     (admin-only)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/legion", tags=["Legion Nodes"])

from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
_db = None


def set_db(db):
    global _db
    _db = db


async def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = payload.get("role", "")
    if role in ("admin", "super_admin") or payload.get("is_admin") or payload.get("is_super_admin"):
        return payload
    raise HTTPException(403, "Admin only")


def _classify(configured: bool, reachable: bool) -> str:
    if not configured:
        return "offline"       # env not set — node intentionally disabled
    if reachable:
        return "online"
    return "unreachable"       # env set, but can't reach → alert worthy


async def _probe_evolver() -> Dict[str, Any]:
    try:
        from services import evolver_client
        st = await evolver_client.get_status(_db)
        configured = bool(st.get("configured"))
        reachable = bool(st.get("reachable"))
        return {
            "name": "EvoMap Evolver",
            "key": "evolver",
            "configured": configured,
            "reachable": reachable,
            "state": _classify(configured, reachable),
            "url_env": "EVOLVER_URL",
            "detail": {
                "strategy": st.get("strategy"),
                "review_mode": st.get("review_mode"),
                "allow_self_modify": st.get("allow_self_modify"),
                "genes_total": st.get("genes_total"),
                "genes_pending": st.get("genes_pending"),
                "genes_approved": st.get("genes_approved"),
                "last_run": st.get("last_run"),
            },
        }
    except Exception as e:
        logger.warning(f"[LegionHealth] evolver probe failed: {e}")
        return {"name": "EvoMap Evolver", "key": "evolver", "configured": False,
                "reachable": False, "state": "error", "error": str(e)[:200]}


async def _probe_sandbox() -> Dict[str, Any]:
    try:
        from services import sandbox_client
        st = await sandbox_client.get_status()
        return {
            "name": "SmolMachines Sandbox",
            "key": "sandbox",
            "configured": bool(st.get("configured")),
            "reachable": bool(st.get("reachable")),
            "state": _classify(bool(st.get("configured")), bool(st.get("reachable"))),
            "url_env": "SANDBOX_URL",
            "detail": {
                "mode": st.get("mode"),
                "max_bytes": st.get("max_bytes"),
                "remote": st.get("remote"),
            },
        }
    except Exception as e:
        logger.warning(f"[LegionHealth] sandbox probe failed: {e}")
        return {"name": "SmolMachines Sandbox", "key": "sandbox", "configured": False,
                "reachable": False, "state": "error", "error": str(e)[:200]}


async def _probe_carbonyl() -> Dict[str, Any]:
    try:
        from services import carbonyl_fetcher
        st = await carbonyl_fetcher.get_status()
        return {
            "name": "Carbonyl Browser",
            "key": "carbonyl",
            "configured": bool(st.get("configured")),
            "reachable": bool(st.get("reachable")),
            "state": _classify(bool(st.get("configured")), bool(st.get("reachable"))),
            "url_env": "CARBONYL_URL",
            "detail": {},
        }
    except Exception as e:
        logger.warning(f"[LegionHealth] carbonyl probe failed: {e}")
        return {"name": "Carbonyl Browser", "key": "carbonyl", "configured": False,
                "reachable": False, "state": "error", "error": str(e)[:200]}


async def _probe_http_node(
    name: str, key: str, url_env: str, health_path: str = "/health",
) -> Dict[str, Any]:
    """Generic HTTP-health probe for Legion-side Dockerized services.

    Used for Voice / Social / n8n. Node is considered:
      - offline    when its URL env is not set
      - online     when GET <url><health_path> returns 2xx within 3s
      - unreachable otherwise
    """
    url = os.environ.get(url_env, "").rstrip("/")
    if not url:
        return {
            "name": name, "key": key, "configured": False, "reachable": False,
            "state": "offline", "url_env": url_env, "detail": {"hint": f"Set {url_env} in backend/.env"},
        }
    detail: Dict[str, Any] = {"url_base": url, "health_path": health_path}
    reachable = False
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{url}{health_path}")
            detail["status_code"] = r.status_code
            reachable = 200 <= r.status_code < 300
            if reachable:
                # Capture a small slice of the health body for UI display
                try:
                    j = r.json()
                    if isinstance(j, dict):
                        detail["version"] = j.get("version") or j.get("app_version")
                        detail["uptime"] = j.get("uptime") or j.get("uptime_s")
                        detail["mode"] = j.get("mode")
                except Exception:
                    pass
    except Exception as e:
        detail["error"] = str(e)[:200]

    return {
        "name": name, "key": key, "configured": True, "reachable": reachable,
        "state": _classify(True, reachable), "url_env": url_env, "detail": detail,
    }


async def _probe_openfang() -> Dict[str, Any]:
    """OpenFang is inbound-only — 'reachable' means webhook is configured and
    has received at least one import in the last 7 days."""
    configured = bool(os.environ.get("OPENFANG_WEBHOOK_SECRET", ""))
    detail: Dict[str, Any] = {}
    recent_count = 0
    has_recent = False
    if _db is not None:
        try:
            total = await _db.leads.count_documents({"source": "openfang"})
            recent = await _db.openfang_imports.find(
                {}, projection={"_id": 0, "ts": 1, "inserted": 1, "auth_mode": 1},
            ).sort("ts", -1).limit(5).to_list(length=5)
            detail = {
                "total_leads_from_openfang": total,
                "last_imports": recent,
                "plain_token_allowed": (
                    os.environ.get("OPENFANG_ALLOW_PLAIN_TOKEN", "true").lower() == "true"
                ),
            }
            # Count recent imports (last 7 days)
            from datetime import datetime, timedelta, timezone as _tz
            cutoff = (datetime.now(_tz.utc) - timedelta(days=7)).isoformat()
            recent_count = await _db.openfang_imports.count_documents({"ts": {"$gte": cutoff}})
            has_recent = recent_count > 0
        except Exception as e:
            logger.warning(f"[LegionHealth] openfang detail failed: {e}")

    if not configured:
        state = "offline"
    elif has_recent:
        state = "online"
    else:
        state = "idle"       # configured but no recent traffic

    return {
        "name": "OpenFang Lead Hand",
        "key": "openfang",
        "configured": configured,
        "reachable": has_recent,     # reachable == "has recent traffic"
        "state": state,
        "url_env": "OPENFANG_WEBHOOK_SECRET",
        "recent_imports_7d": recent_count,
        "detail": detail,
    }


@router.get("/health")
async def legion_health(request: Request):
    await _require_admin(request)
    nodes = []

    # Legion-side native nodes (already built)
    for probe in (_probe_evolver, _probe_sandbox, _probe_carbonyl, _probe_openfang):
        nodes.append(await probe())

    # Legion Docker subdomain services (Voice / Social / n8n) — Iteration 218
    voice_node = await _probe_http_node(
        "Voice Engine (DIY)", "voice", "VOICE_URL", health_path="/health",
    )
    social_node = await _probe_http_node(
        "Social Scheduler (Postiz)", "social", "SOCIAL_URL", health_path="/health",
    )
    n8n_node = await _probe_http_node(
        "n8n Workflows", "n8n", "N8N_URL", health_path="/healthz",
    )
    nodes.extend([voice_node, social_node, n8n_node])

    online = sum(1 for n in nodes if n.get("state") == "online")
    unreachable = sum(1 for n in nodes if n.get("state") == "unreachable")
    offline = sum(1 for n in nodes if n.get("state") == "offline")
    idle = sum(1 for n in nodes if n.get("state") == "idle")
    errored = sum(1 for n in nodes if n.get("state") == "error")
    total = len(nodes)

    # Truthful verdict:
    #   critical → any node that SHOULD be online is unreachable or errored
    #   degraded → less than half of nodes are online (Legion stack barely up)
    #   offline  → no nodes online AND no error states (everything intentionally off)
    #   healthy  → majority online, no unreachable/errored
    if errored or unreachable:
        verdict = "critical"
    elif online == 0:
        verdict = "offline"
    elif online < (total / 2):
        verdict = "degraded"
    else:
        verdict = "healthy"

    return {
        "verdict": verdict,
        "summary": {
            "total": total,
            "online": online,
            "idle": idle,
            "unreachable": unreachable,
            "offline": offline,
            "error": errored,
        },
        "nodes": nodes,
    }
