"""
AUREM Partner Referral Router
Handles referral codes, tracking, and reward management
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/referrals", tags=["AUREM Referrals"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


def _get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


REWARD_TIERS = [
    {"tier": "Bronze", "min": 0, "max": 4, "reward_amount": 25},
    {"tier": "Silver", "min": 5, "max": 14, "reward_amount": 50},
    {"tier": "Gold", "min": 15, "max": 49, "reward_amount": 100},
    {"tier": "Platinum", "min": 50, "max": 999, "reward_amount": 200},
]


def _get_tier(total_referrals):
    for tier in reversed(REWARD_TIERS):
        if total_referrals >= tier["min"]:
            return tier["tier"]
    return "Bronze"


@router.get("/dashboard")
async def get_referral_dashboard(request: Request):
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    # Get or create referral profile
    profile = await db.referral_profiles.find_one({"user_id": user_id}, {"_id": 0})
    if not profile:
        code = f"AUREM-{uuid.uuid4().hex[:6].upper()}"
        profile = {
            "user_id": user_id,
            "referral_code": code,
            "total_referrals": 0,
            "active_referrals": 0,
            "pending_referrals": 0,
            "total_earned": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.referral_profiles.insert_one(profile)
        profile.pop("_id", None)

    # Get referral history
    history = []
    cursor = db.referral_history.find({"referrer_id": user_id}, {"_id": 0}).sort("created_at", -1).limit(50)
    async for ref in cursor:
        history.append(ref)

    total = profile.get("total_referrals", 0)
    current_tier = _get_tier(total)

    return {
        "referral_code": profile.get("referral_code", ""),
        "referral_link": f"https://aurem.live/join?ref={profile.get('referral_code', '')}",
        "total_referrals": total,
        "active_referrals": profile.get("active_referrals", 0),
        "pending_referrals": profile.get("pending_referrals", 0),
        "total_earned": profile.get("total_earned", 0),
        "current_tier": current_tier,
        "referral_history": history
    }
