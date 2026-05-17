"""
Customer-scoped orchestrator read-only endpoints.
═══════════════════════════════════════════════════════════════════
iter 323d — LuxePages.jsx "Automation" panel was calling
`/api/orchestrator/{queue,workflows}` with a customer JWT and getting
401s because those routes are admin-gated (Bug 134 security fix).

These customer endpoints expose only the data the customer's tenant
needs to see — read-only, tenant-scoped, no LLM-execution side effects.
═══════════════════════════════════════════════════════════════════
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from datetime import datetime, timezone
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customer/orchestrator", tags=["orchestrator-customer"])

_db = None


def set_db(database):
    global _db
    _db = database


async def _current_user(request: Request) -> Dict[str, Any]:
    """Return the decoded JWT user; raise 401 on missing/bad token.

    Tries the canonical `utils.auth_utils.get_current_user` first, then
    falls back to a minimal in-router decode so this endpoint never
    depends on a single import path during incremental boot.
    """
    import os as _os
    user = None
    try:
        from utils.auth_utils import get_current_user as _auth_get
        user = await _auth_get(request)
    except Exception:
        user = None
    if not user:
        try:
            import jwt as _jwt
            secret = _os.environ.get("JWT_SECRET") or ""
            hdr = request.headers.get("Authorization") or ""
            if secret and hdr.lower().startswith("bearer "):
                payload = _jwt.decode(hdr.split(" ", 1)[1].strip(), secret, algorithms=["HS256"])
                user = {
                    "user_id": payload.get("user_id") or payload.get("sub"),
                    "email": payload.get("email"),
                    "is_admin": bool(payload.get("is_admin")),
                    "role": payload.get("role"),
                    "tenant_id": payload.get("tenant_id"),
                    "business_id": payload.get("business_id"),
                }
        except Exception:
            user = None
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/workflows")
async def list_customer_workflows(request: Request) -> Dict[str, Any]:
    """
    Return workflows visible to the calling user.
      - Admins see all workflows.
      - Customers see only workflows scoped to their tenant_id / business_id.
    Read-only — never triggers an execution.
    """
    user = await _current_user(request)
    is_admin = bool(user.get("is_admin") or user.get("role") == "admin")

    workflows: List[Dict[str, Any]] = []
    if _db is None:
        return {"workflows": [], "count": 0, "note": "db_unavailable"}

    try:
        query: Dict[str, Any] = {}
        if not is_admin:
            tid = user.get("tenant_id") or user.get("business_id") or user.get("user_id")
            if tid:
                query["$or"] = [
                    {"tenant_id": tid},
                    {"business_id": tid},
                    {"owner_id": user.get("user_id")},
                ]
        cursor = _db.workflows.find(query, {"_id": 0}).sort("created_at", -1).limit(50)
        async for w in cursor:
            workflows.append({
                "id": w.get("workflow_id") or w.get("id") or "",
                "name": w.get("name", "Untitled"),
                "status": w.get("status", "idle"),
                "last_run": w.get("last_run") or w.get("updated_at"),
                "steps": len(w.get("steps", []) or []),
            })
    except Exception as e:
        logger.warning(f"[orchestrator-customer] workflows lookup failed: {e}")

    return {"workflows": workflows, "count": len(workflows)}


@router.get("/queue")
async def get_customer_queue(request: Request) -> Dict[str, Any]:
    """
    Return queue depth + recent items visible to the caller.
    Admins: full system queue. Customers: their tenant's queue only.
    """
    user = await _current_user(request)
    is_admin = bool(user.get("is_admin") or user.get("role") == "admin")

    items: List[Dict[str, Any]] = []
    depth = 0
    if _db is None:
        return {"depth": 0, "items": [], "note": "db_unavailable"}

    try:
        query: Dict[str, Any] = {"status": {"$in": ["pending", "running", "queued"]}}
        if not is_admin:
            tid = user.get("tenant_id") or user.get("business_id") or user.get("user_id")
            if tid:
                query["$or"] = [
                    {"tenant_id": tid},
                    {"business_id": tid},
                    {"owner_id": user.get("user_id")},
                ]
        depth = await _db.orchestrator_tasks.count_documents(query)
        cursor = _db.orchestrator_tasks.find(query, {"_id": 0}).sort("created_at", -1).limit(20)
        async for t in cursor:
            items.append({
                "id": t.get("task_id") or t.get("id") or "",
                "type": t.get("task_type", "task"),
                "status": t.get("status", "pending"),
                "created_at": t.get("created_at"),
            })
    except Exception as e:
        logger.warning(f"[orchestrator-customer] queue lookup failed: {e}")

    return {"depth": depth, "items": items}


__all__ = ["router", "set_db"]
