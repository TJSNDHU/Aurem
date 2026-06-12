"""
Supply-Chain Security Router — iter D-82
═══════════════════════════════════════════════════════════════════════════
Admin-only endpoints to view + trigger AUREM's autonomous supply-chain /
secret / SAST sweep (services.supply_chain_scanner).

    GET  /api/admin/supply-chain/latest    -- current snapshot + findings
    GET  /api/admin/supply-chain/history   -- recent scan summaries
    POST /api/admin/supply-chain/scan      -- trigger an on-demand sweep
═══════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/supply-chain", tags=["admin · supply-chain"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database
    try:
        from services.supply_chain_scanner import set_db as _set
        _set(database)
    except Exception as e:  # noqa: BLE001
        logger.warning("[supply-chain] scanner set_db failed: %s", e)
    try:
        from services.supply_chain_remediation import set_db as _set_rem
        _set_rem(database)
    except Exception as e:  # noqa: BLE001
        logger.warning("[supply-chain] remediation set_db failed: %s", e)


async def _require_admin(request: Request) -> Dict[str, Any]:
    user: Optional[Dict[str, Any]] = None
    try:
        from utils.auth_utils import get_current_user as _auth_get
        user = await _auth_get(request)
    except Exception:
        user = None
    if not user:
        try:
            import jwt as _jwt
            secret = os.environ.get("JWT_SECRET") or ""
            hdr = request.headers.get("Authorization") or ""
            if secret and hdr.lower().startswith("bearer "):
                payload = _jwt.decode(hdr.split(" ", 1)[1].strip(), secret, algorithms=["HS256"])
                user = {
                    "user_id": payload.get("user_id") or payload.get("sub"),
                    "email": payload.get("email"),
                    "is_admin": bool(payload.get("is_admin")),
                    "role": payload.get("role"),
                }
        except Exception:
            user = None
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not (user.get("is_admin") or user.get("role") in ("admin", "super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/latest")
async def latest(request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    from services.supply_chain_scanner import get_latest
    snap = await get_latest()
    if not snap:
        return {"status": "no_scan_yet", "message": "First sweep runs ~35 min after boot, then every 6h."}
    return {"status": "ok", "snapshot": snap}


@router.get("/history")
async def history(request: Request, limit: int = 20) -> Dict[str, Any]:
    await _require_admin(request)
    from services.supply_chain_scanner import get_history
    return {"status": "ok", "scans": await get_history(limit=min(max(limit, 1), 100))}


@router.post("/scan")
async def scan_now(request: Request) -> Dict[str, Any]:
    await _require_admin(request)
    from services.supply_chain_scanner import run_supply_chain_scan
    # The full sweep runs ~60-90s — longer than the ingress timeout. Launch it
    # as a detached background task and return immediately; the admin polls
    # /latest for the result.
    async def _bg():
        try:
            await run_supply_chain_scan(trigger="manual")
        except Exception as e:  # noqa: BLE001
            logger.error("[supply-chain] manual scan failed: %s", e)

    asyncio.create_task(_bg())
    return {
        "status": "started",
        "message": "Sweep running in the background (~60-90s). Poll /api/admin/supply-chain/latest.",
    }


@router.post("/remediate")
async def remediate(request: Request, auto_apply: bool = False) -> Dict[str, Any]:
    """Plan remediations from the latest sweep.
    - auto_apply=false (default): SUGGEST-only — queues findings into the
      Sentinel repair_suggestions review queue. Safe.
    - auto_apply=true: applies safe (same-major) pip upgrades for real
      (backup + install + smoke-import + rollback), queues the rest.
    """
    await _require_admin(request)
    from services.supply_chain_remediation import run_remediation
    try:
        result = await asyncio.wait_for(run_remediation(auto_apply=auto_apply), timeout=280)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Remediation exceeded 4.5 min; check /remediations.")
    return {"status": "ok", "result": result}


@router.post("/autofix")
async def council_autofix(request: Request) -> Dict[str, Any]:
    """MAX autofix — route every remediable finding through the ORA Council
    (CASL + QA) and auto-apply approved pip/yarn upgrades for real. NO human.
    Runs in the background (apply path can take minutes); poll /remediations."""
    await _require_admin(request)
    from services.supply_chain_remediation import run_council_autofix

    async def _bg():
        try:
            await run_council_autofix()
        except Exception as e:  # noqa: BLE001
            logger.error("[supply-chain] council autofix failed: %s", e)

    asyncio.create_task(_bg())
    return {
        "status": "started",
        "message": "Council-gated autofix running in background. Poll /api/admin/supply-chain/remediations.",
    }


@router.get("/remediations")
async def remediations(request: Request, limit: int = 50) -> Dict[str, Any]:
    await _require_admin(request)
    from services.supply_chain_remediation import get_remediation_log
    return {"status": "ok", "log": await get_remediation_log(limit=min(max(limit, 1), 200))}


print("[STARTUP] Supply-Chain Router loaded", flush=True)
