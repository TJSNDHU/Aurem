"""
service_gate.py — `@require_service` decorator + quota check + auto usage log
═══════════════════════════════════════════════════════════════════════════
Single source of route-level gating. Apply to every paid endpoint:

    @router.post("/api/voice/call")
    @require_service("voice_agent_ai", quota_kind="voice_limit")
    async def make_call(request: Request, ...):
        ctx = request.state.bin_ctx
        ...

Behavior:
  1. Pulls BinCtx from request.state.
  2. If service not in services_unlocked → 402 with upgrade_options payload.
  3. If quota_kind given AND usage exceeded → 429 with usage payload.
  4. On success, logs to db.service_usage_log + emits anonymized telemetry
     to admin_ora_brain so Admin ORA learns from every BIN's actions.
"""
from __future__ import annotations

import functools
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from fastapi import HTTPException, Request

from aurem_config.plans import (
    PLANS, SERVICE_TO_LIMIT_KEY, SERVICE_TO_MIN_PLAN, is_service_unlocked
)
from middleware.bin_context import get_bin_ctx

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_bin(business_id: str) -> str:
    """Anonymize BIN for the admin telemetry pool.
    SHA256 truncated. Not reversible, but consistent so per-BIN patterns
    can still be aggregated without leaking the actual BIN identity.
    """
    salt = os.environ.get("ADMIN_ORA_HASH_SALT", "aurem-default-salt")
    return hashlib.sha256(f"{salt}:{business_id}".encode()).hexdigest()[:16]


def _build_upgrade_options(service_id: str) -> list:
    min_plan = SERVICE_TO_MIN_PLAN.get(service_id)
    options = []
    if min_plan and min_plan in PLANS:
        p = PLANS[min_plan]
        options.append({
            "type": "plan_upgrade",
            "plan": min_plan,
            "name": p["name"],
            "price_cad": p["price_cad"],
        })
    options.append({
        "type": "addon",
        "service_id": service_id,
        "label": f"Add {service_id} as add-on",
    })
    return options


async def _log_usage(db, ctx, service_id: str, count: int, request_path: str) -> None:
    """Per-event usage log + anonymized admin ORA learning event."""
    if db is None:
        return
    now = _now_iso()
    try:
        await db.service_usage_log.insert_one({
            "ts": now,
            "business_id": ctx.business_id,
            "user_id": ctx.user_id,
            "email": ctx.email,
            "service": service_id,
            "count": count,
            "path": request_path,
        })
    except Exception as e:
        logger.debug(f"[service_gate] usage_log write failed: {e}")
    # Anonymized telemetry → Admin ORA learning pool
    try:
        await db.admin_ora_brain.insert_one({
            "ts": now,
            "type": "service_usage",
            "service": service_id,
            "bin_hash": _hash_bin(ctx.business_id),
            "plan": ctx.plan or "unknown",
            "path": request_path,
        })
    except Exception as e:
        logger.debug(f"[service_gate] admin_ora_brain write failed: {e}")


async def _quota_check(db, ctx, quota_kind: str) -> Optional[int]:
    """Return remaining quota, or None if no limit configured. Raises 429
    if exceeded."""
    if not quota_kind or db is None:
        return None
    plan_id = ctx.plan or "trial"
    plan = PLANS.get(plan_id) or PLANS["trial"]
    limit = plan["limits"].get(quota_kind, 0)
    if limit == 0 or limit >= 1_000_000:
        return None  # unlimited or zero (zero = blocked separately by plan check)

    # Count this month's usage
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()
    used = await db.service_usage_log.count_documents({
        "business_id": ctx.business_id,
        "ts": {"$gte": month_start},
    })
    if used >= limit:
        raise HTTPException(429, detail={
            "error": "quota_exceeded",
            "quota_kind": quota_kind,
            "used": used,
            "limit": limit,
            "plan": plan_id,
            "upgrade_options": _build_upgrade_options(quota_kind),
        })
    return limit - used


def require_service(service_id: str, *, quota_kind: Optional[str] = None,
                    count: int = 1):
    """Decorator factory. Wraps an async route handler.

    Args:
      service_id: catalog service_id that must be in services_unlocked.
      quota_kind: optional limits key (e.g., "voice_limit") to enforce.
      count: usage units consumed by this call (default 1).
    """
    if quota_kind is None:
        quota_kind = SERVICE_TO_LIMIT_KEY.get(service_id)

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            request: Optional[Request] = kwargs.get("request")
            if request is None:
                # Find Request in positional args by type
                for a in args:
                    if isinstance(a, Request):
                        request = a
                        break
            if request is None:
                # Cannot enforce — let handler run (for non-HTTP test contexts)
                return await fn(*args, **kwargs)

            ctx = get_bin_ctx(request, required=True)
            # Plan / service check
            if not is_service_unlocked(service_id, ctx.services_unlocked):
                raise HTTPException(402, detail={
                    "error": "service_locked",
                    "service": service_id,
                    "plan": ctx.plan,
                    "upgrade_options": _build_upgrade_options(service_id),
                })

            # Quota check (also raises 429 inside)
            db = getattr(request.app.state, "db", None) or _resolve_db_fallback()
            await _quota_check(db, ctx, quota_kind)

            # Execute
            result = await fn(*args, **kwargs)

            # Log usage post-success
            await _log_usage(db, ctx, service_id, count, request.url.path)
            return result

        return wrapper

    return decorator


def _resolve_db_fallback():
    """Fallback DB lookup when app.state.db not set — re-imports the
    server-level handle. Defensive only; routes should rely on
    request.app.state.db whenever possible."""
    try:
        from server import db as _server_db
        return _server_db
    except Exception:
        return None
