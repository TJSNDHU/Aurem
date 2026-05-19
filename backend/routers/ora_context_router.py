"""
ORA Context & Notifications Router
Provides ORA context loading and notification endpoints.
"""
import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora", tags=["ORA Context"])

_db = None
from config import JWT_SECRET  # safe 3-tier resolver (env -> file -> ephemeral)
JWT_ALGORITHM = "HS256"


def set_db(db):
    global _db
    _db = db


@router.get("/health")
async def ora_health():
    """Lightweight unauthenticated health probe used by Pillars Map flow check.

    Returns 200 whenever the ORA router is loaded and DB handle exists.
    Does not touch Mongo or LLM — purely presence check.
    """
    return {
        "status": "ok",
        "component": "ora",
        "db_ready": _db is not None,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    try:
        return jwt.decode(auth.split(" ")[1], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


def _get_user_identifiers(payload: dict):
    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    return email, user_id, tenant_id


@router.get("/context")
async def get_ora_context(request: Request):
    """Load full business context for ORA session."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    payload = _decode_jwt(request)
    email, user_id, tenant_id = _get_user_identifiers(payload)

    user = None
    if email:
        user = await _db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            user = await _db.platform_users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    tid = tenant_id or user.get("tenant_id") or user.get("id") or user.get("email")

    from services.ora_context import load_business_context
    context = await load_business_context(_db, tid, user)

    # Add founder flag if user is admin
    is_admin = payload.get("is_admin", False) or user.get("is_admin", False)
    context["is_founder"] = is_admin

    return context


@router.get("/founder-briefing")
async def get_founder_briefing(request: Request):
    """Full AUREM platform overview for the Founder. Requires is_admin JWT."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    payload = _decode_jwt(request)
    is_admin = payload.get("is_admin", False)
    if not is_admin:
        raise HTTPException(403, "Founder access required")

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    briefing = {
        "role": "founder",
        "platform_name": "AUREM AI",
        "generated_at": now.isoformat(),
    }

    try:
        # Platform-wide tenant stats
        total_tenants = await _db.users.count_documents({"is_admin": {"$ne": True}})
        total_admins = await _db.users.count_documents({"is_admin": True})
        active_today = await _db.users.count_documents({
            "last_login": {"$gte": today_start.isoformat()}
        })
        briefing["tenants"] = {
            "total": total_tenants,
            "admins": total_admins,
            "active_today": active_today,
        }

        # Platform-wide lead stats
        total_leads = await _db.leads.count_documents({})
        leads_today = await _db.leads.count_documents({
            "created_at": {"$gte": today_start.isoformat()}
        })
        leads_month = await _db.leads.count_documents({
            "created_at": {"$gte": month_start.isoformat()}
        })
        briefing["leads"] = {
            "total": total_leads,
            "today": leads_today,
            "this_month": leads_month,
        }

        # API keys stats
        total_keys = await _db.api_keys.count_documents({})
        active_keys = await _db.api_keys.count_documents({"active": True})
        briefing["api_keys"] = {
            "total": total_keys,
            "active": active_keys,
        }

        # Platform invoices / revenue
        paid_invoices = _db.invoices.find(
            {"status": "paid", "paid_at": {"$gte": month_start.isoformat()}},
            {"_id": 0, "amount": 1}
        )
        paid_list = await paid_invoices.to_list(1000)
        revenue_month = sum(i.get("amount", 0) for i in paid_list)

        pending_invoices = await _db.invoices.count_documents({
            "status": {"$in": ["pending", "overdue"]}
        })
        briefing["revenue"] = {
            "this_month": revenue_month,
            "pending_invoices": pending_invoices,
        }

        # Pending approvals across all tenants
        total_approvals = await _db.approval_queue.count_documents({"status": "pending"})
        briefing["approvals_pending"] = total_approvals

        # System health
        health_docs = _db.site_health.find({}, {"_id": 0, "score": 1, "tenant_id": 1}).limit(100)
        health_list = await health_docs.to_list(100)
        avg_health = (sum(h.get("score", 0) for h in health_list) / len(health_list)) if health_list else 0
        briefing["system_health"] = {
            "avg_score": round(avg_health, 1),
            "sites_monitored": len(health_list),
        }

        # Recent pipeline runs
        last_runs = _db.pipeline_runs.find(
            {}, {"_id": 0, "tenant_id": 1, "status": 1, "completed_at": 1, "actions_taken": 1}
        ).sort("completed_at", -1).limit(5)
        runs = await last_runs.to_list(5)
        briefing["recent_pipelines"] = runs

        # Team connections via Business IDs
        total_connections = await _db.team_connections.count_documents({})
        briefing["team_connections"] = total_connections

        # Voice calls
        total_calls = await _db.aurem_voice_calls.count_documents({})
        briefing["voice_calls_total"] = total_calls

        # Economic context
        econ = await _db.global_pulse_shadow.find_one({"type": "latest"}, {"_id": 0})
        if econ:
            briefing["economic_context"] = {
                "cad_usd": econ.get("cad_usd"),
                "boc_rate": econ.get("boc_rate"),
                "next_decision": econ.get("next_decision"),
            }

    except Exception as e:
        logger.warning(f"[FOUNDER-BRIEFING] Error loading briefing: {e}")

    return briefing


@router.get("/notifications")
async def get_notifications(request: Request, limit: int = 20):
    """Get notification history for the current user."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    payload = _decode_jwt(request)
    email, user_id, tenant_id = _get_user_identifiers(payload)

    user = None
    if email:
        user = await _db.users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return {"notifications": [], "unread_count": 0}

    tid = tenant_id or user.get("tenant_id") or user.get("id")

    cursor = _db.notifications.find(
        {"tenant_id": tid},
        {"_id": 0}
    ).sort("sent_at", -1).limit(limit)
    notifs = await cursor.to_list(limit)

    unread = await _db.notifications.count_documents({"tenant_id": tid, "read": False})

    return {"notifications": notifs, "unread_count": unread}


@router.post("/notifications/read")
async def mark_notifications_read(request: Request):
    """Mark all notifications as read."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    payload = _decode_jwt(request)
    email, user_id, tenant_id = _get_user_identifiers(payload)

    user = None
    if email:
        user = await _db.users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return {"updated": 0}

    tid = tenant_id or user.get("tenant_id") or user.get("id")

    result = await _db.notifications.update_many(
        {"tenant_id": tid, "read": False},
        {"$set": {"read": True, "read_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"updated": result.modified_count}


@router.post("/notifications/test")
async def test_notification(request: Request):
    """Fire a test notification (for development)."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    payload = _decode_jwt(request)
    email, user_id, tenant_id = _get_user_identifiers(payload)

    user = None
    if email:
        user = await _db.users.find_one({"email": email}, {"_id": 0})
    if not user and user_id:
        user = await _db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    tid = tenant_id or user.get("tenant_id") or user.get("id")

    from services.notification_triggers import trigger_notification
    await trigger_notification(
        tid, "pipeline_completed",
        actions_taken=5, revenue_impact="$1,200"
    )
    return {"message": "Test notification sent"}


from pydantic import BaseModel as _NActionModel

class NotificationActionRequest(_NActionModel):
    notification_id: str = ""
    action: str
    tenant_id: str = ""


@router.post("/notifications/action")
async def handle_notification_action(data: NotificationActionRequest, request: Request):
    """Handle action from push notification (approve/reject/view)."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    action = data.action
    tid = data.tenant_id

    # Try to get tenant from JWT if available
    try:
        payload = _decode_jwt(request)
        email, user_id, tenant_id_jwt = _get_user_identifiers(payload)
        if tenant_id_jwt:
            tid = tenant_id_jwt
    except Exception:
        pass

    if not tid:
        raise HTTPException(400, "tenant_id required")

    # Mark notification as read if id provided
    if data.notification_id:
        from bson import ObjectId
        try:
            await _db.notifications.update_one(
                {"_id": ObjectId(data.notification_id)},
                {"$set": {"read": True, "actioned": action, "actioned_at": datetime.now(timezone.utc).isoformat()}}
            )
        except Exception:
            pass

    # Route action
    deep_link = None
    result_msg = "Action recorded"

    if action in ("approve", "approve_outreach"):
        result_msg = "Approval recorded"
        deep_link = "/ora"
    elif action == "reject":
        result_msg = "Rejection recorded"
        deep_link = "/ora"
    elif action == "skip":
        result_msg = "Skipped"
    elif action == "view_invoice":
        deep_link = "/dashboard"
    elif action == "view_health":
        deep_link = "/dashboard"
    elif action == "view_sentinel":
        deep_link = "/dashboard"
    elif action == "view_pipeline":
        deep_link = "/dashboard"
    elif action == "open_brief":
        deep_link = "/ora#brief"
    else:
        deep_link = "/ora"

    return {"message": result_msg, "action": action, "deep_link": deep_link}
