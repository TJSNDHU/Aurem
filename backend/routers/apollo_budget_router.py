"""
Apollo monthly budget alert.

Reads cumulative spend from `apollo_call_log`, compares against a
tenant-set monthly budget (`apollo_budget_settings` collection), and
emails the founder once spend crosses 80% of the budget.

Endpoints:
    GET  /api/admin/apollo-cost/budget          current settings + status
    POST /api/admin/apollo-cost/budget          update settings

Cron-friendly:
    services.apollo_budget_alert.check_and_notify()
"""

import logging
import os
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, Body, Header, HTTPException

router = APIRouter(prefix="/api/admin/apollo-cost", tags=["apollo-cost-budget"])
logger = logging.getLogger(__name__)
JWT_SECRET = os.environ.get("JWT_SECRET")

_db = None
_COST_PER_CALL_USD = 0.03
_DEFAULT_BUDGET_USD = 50.0
_ALERT_THRESHOLD = 0.80      # 80%


def set_db(database):
    global _db
    _db = database


async def _require_admin(authorization):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    try:
        p = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET,
                        algorithms=["HS256"])
        if (p.get("is_admin") or p.get("is_super_admin") or
                p.get("role") in ("admin", "super_admin", "founder")):
            return p.get("email") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


def _current_month_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def _current_month_spend() -> tuple[float, int]:
    if _db is None:
        return 0.0, 0
    month_prefix = _current_month_id()
    pipeline = [
        {"$match": {"day": {"$regex": f"^{month_prefix}"}}},
        {"$group": {"_id": None,
                      "calls": {"$sum": 1},
                      "usd":   {"$sum": "$estimated_usd"}}},
    ]
    async for row in _db.apollo_call_log.aggregate(pipeline):
        return float(row.get("usd", 0)), int(row.get("calls", 0))
    return 0.0, 0


async def _get_settings() -> dict:
    if _db is None:
        return {"monthly_budget_usd": _DEFAULT_BUDGET_USD,
                 "alert_email": "",
                 "alert_threshold": _ALERT_THRESHOLD}
    row = await _db.apollo_budget_settings.find_one(
        {"_id": "singleton"}, {"_id": 0},
    )
    return row or {"monthly_budget_usd": _DEFAULT_BUDGET_USD,
                    "alert_email": os.environ.get(
                        "ADMIN_DAILY_BRIEF_EMAIL", ""),
                    "alert_threshold": _ALERT_THRESHOLD}


@router.get("/budget")
async def get_budget(authorization: str = Header(None)):
    await _require_admin(authorization)
    settings = await _get_settings()
    spend_usd, calls = await _current_month_spend()
    budget = float(settings.get("monthly_budget_usd") or _DEFAULT_BUDGET_USD)
    pct = (spend_usd / budget * 100) if budget > 0 else 0
    return {
        "ok":               True,
        "month":            _current_month_id(),
        "monthly_budget_usd": budget,
        "alert_threshold":    float(settings.get("alert_threshold",
                                                   _ALERT_THRESHOLD)),
        "alert_email":      settings.get("alert_email", ""),
        "spend_usd":        round(spend_usd, 2),
        "calls":            calls,
        "percent_used":     round(pct, 1),
        "remaining_usd":    round(max(0, budget - spend_usd), 2),
        "over_threshold":   pct >= (float(settings.get(
                                    "alert_threshold",
                                    _ALERT_THRESHOLD)) * 100),
    }


@router.post("/budget")
async def update_budget(body: dict = Body(...),
                          authorization: str = Header(None)):
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "Database unavailable")
    update: dict = {}
    if "monthly_budget_usd" in body:
        update["monthly_budget_usd"] = float(body["monthly_budget_usd"])
    if "alert_email" in body:
        update["alert_email"] = str(body["alert_email"])[:200]
    if "alert_threshold" in body:
        t = float(body["alert_threshold"])
        if not (0 < t <= 1):
            raise HTTPException(400, "alert_threshold must be in (0, 1]")
        update["alert_threshold"] = t
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await _db.apollo_budget_settings.update_one(
        {"_id": "singleton"}, {"$set": update}, upsert=True,
    )
    return await get_budget(authorization)


async def check_and_notify() -> dict:
    """Cron hook. Fires founder email when month spend ≥ threshold.

    Idempotent — uses `apollo_budget_alerts_sent` to avoid resending
    the same month's alert.
    """
    if _db is None:
        return {"ok": False, "error": "db_unavailable"}
    settings = await _get_settings()
    budget = float(settings.get("monthly_budget_usd") or _DEFAULT_BUDGET_USD)
    threshold = float(settings.get("alert_threshold", _ALERT_THRESHOLD))
    spend, calls = await _current_month_spend()
    pct = (spend / budget) if budget > 0 else 0
    if pct < threshold:
        return {"ok": True, "fired": False, "pct": round(pct * 100, 1)}

    month = _current_month_id()
    already = await _db.apollo_budget_alerts_sent.find_one(
        {"month": month}, {"_id": 0},
    )
    if already:
        return {"ok": True, "fired": False, "reason": "already_alerted"}

    to = settings.get("alert_email") or os.environ.get(
        "ADMIN_DAILY_BRIEF_EMAIL", "")
    if not to:
        return {"ok": True, "fired": False, "reason": "no_alert_email"}

    try:
        from services.email_service_resend import send_email
        await send_email(
            to=to,
            subject=f"🚨 Apollo budget alert · {round(pct * 100)}% used",
            html=(
                f"<h2>Apollo Monthly Spend Alert</h2>"
                f"<p>Month <strong>{month}</strong> usage has crossed "
                f"<strong>{round(pct * 100)}%</strong> of your "
                f"${budget:.2f} budget.</p>"
                f"<ul>"
                f"<li>Spent: <strong>${spend:.2f}</strong></li>"
                f"<li>Calls: <strong>{calls}</strong></li>"
                f"<li>Remaining: <strong>${max(0, budget - spend):.2f}</strong></li>"
                f"</ul>"
                f"<p><a href='https://aurem.live/admin/apollo-cost'>"
                f"View dashboard →</a></p>"
            ),
        )
        await _db.apollo_budget_alerts_sent.insert_one({
            "month":      month,
            "sent_at":    datetime.now(timezone.utc).isoformat(),
            "spend_usd":  spend,
            "budget_usd": budget,
            "pct":        round(pct * 100, 1),
            "to":         to,
        })
        return {"ok": True, "fired": True, "to": to, "pct": round(pct * 100, 1)}
    except Exception as e:
        logger.error(f"[apollo-budget] alert email failed: {e}")
        return {"ok": False, "error": str(e)}
