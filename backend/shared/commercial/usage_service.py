"""
AUREM Usage Metering Service
Tracks AI actions per tenant per billing period.
Enforces hard limits (429) when monthly cap hit.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Plan limits — aligned with AUREM pricing tiers
PLAN_ACTION_LIMITS = {
    "trial": 50,
    "starter": 500,
    "growth": 5000,
    "enterprise": -1,  # unlimited
}

ACTION_TYPES = [
    "llm_call", "v2v_session", "invoice_sent",
    "webhook_processed", "ghost_action", "geo_check",
    "csv_import", "ucp_negotiation",
]


def _billing_period_key(dt: datetime = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


class UsageMeter:
    COLLECTION = "aurem_usage_meter"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.col = db[self.COLLECTION]

    async def ensure_indexes(self):
        try:
            await self.col.create_index(
                [("tenant_id", 1), ("period", 1)], unique=True
            )
        except Exception:
            pass

    async def increment(
        self,
        tenant_id: str,
        action_type: str,
        count: int = 1,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        period = _billing_period_key()
        result = await self.col.find_one_and_update(
            {"tenant_id": tenant_id, "period": period},
            {
                "$inc": {
                    "total_actions": count,
                    f"breakdown.{action_type}": count,
                },
                "$set": {"updated_at": datetime.now(timezone.utc)},
                "$setOnInsert": {
                    "tenant_id": tenant_id,
                    "period": period,
                    "created_at": datetime.now(timezone.utc),
                },
            },
            upsert=True,
            return_document=True,
        )
        result.pop("_id", None)

        if metadata:
            await self.db["aurem_usage_log"].insert_one({
                "tenant_id": tenant_id,
                "period": period,
                "action_type": action_type,
                "metadata": metadata,
                "ts": datetime.now(timezone.utc),
            })

        return result

    async def get_current(self, tenant_id: str) -> Dict[str, Any]:
        period = _billing_period_key()
        doc = await self.col.find_one(
            {"tenant_id": tenant_id, "period": period}, {"_id": 0}
        )
        if not doc:
            return {
                "tenant_id": tenant_id,
                "period": period,
                "total_actions": 0,
                "breakdown": {},
            }
        return doc

    async def get_history(self, tenant_id: str, months: int = 6):
        cursor = self.col.find(
            {"tenant_id": tenant_id}, {"_id": 0}
        ).sort("period", -1).limit(months)
        return await cursor.to_list(length=months)

    async def check_quota(self, tenant_id: str, plan: str) -> Dict[str, Any]:
        limit = PLAN_ACTION_LIMITS.get(plan, 50)
        if limit == -1:
            return {"allowed": True, "used": 0, "limit": -1, "remaining": -1}
        current = await self.get_current(tenant_id)
        used = current.get("total_actions", 0)
        return {
            "allowed": used < limit,
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "percent": round((used / limit) * 100, 1) if limit > 0 else 0,
        }

    async def get_all_tenants_usage(self):
        period = _billing_period_key()
        cursor = self.col.find({"period": period}, {"_id": 0})
        return await cursor.to_list(length=500)


_meter: Optional[UsageMeter] = None


def get_usage_meter(db: AsyncIOMotorDatabase) -> UsageMeter:
    global _meter
    if _meter is None:
        _meter = UsageMeter(db)
    return _meter
