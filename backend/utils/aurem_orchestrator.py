"""
AUREM Central Orchestrator
Company: Polaris Built Inc.

Sits between Envoy and Closer agents to prevent:
1. Duplicate outreach (same prospect contacted in 7 days)
2. Channel overuse (daily limits per channel)
3. Channel failures (circuit breaker routing)

The Orchestrator approves or blocks each send before the Closer executes.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/aurem/orchestrator", tags=["aurem-orchestrator"])

# MongoDB reference
_db: AsyncIOMotorDatabase = None

def set_db(database: AsyncIOMotorDatabase):
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LIMITS CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CHANNEL_DAILY_LIMITS = {
    "email": 50,
    "whatsapp": 30,
    "voice": 20,
}

DEDUP_WINDOW_DAYS = 7  # Don't contact same prospect within this window

# Circuit breaker state (in-memory, synced with bug engine)
_circuit_breakers: Dict[str, datetime] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR CORE LOGIC
# ═══════════════════════════════════════════════════════════════════════════════

async def check_dedup(
    prospect_email: Optional[str],
    prospect_phone: Optional[str],
    user_id: str
) -> Dict[str, Any]:
    """
    Check if this prospect was contacted recently.
    Returns: {blocked: bool, reason: str, last_contact: datetime}
    """
    if _db is None:
        return {"blocked": False, "reason": "db_unavailable"}
    
    since = datetime.now(timezone.utc) - timedelta(days=DEDUP_WINDOW_DAYS)
    
    # Build query for email or phone match
    or_conditions = []
    if prospect_email:
        or_conditions.append({"data.envoy_result.outreach_plans.prospect_email": prospect_email})
        or_conditions.append({"data.outreach_log.email": prospect_email})
    if prospect_phone:
        or_conditions.append({"data.envoy_result.outreach_plans.phone": prospect_phone})
        or_conditions.append({"data.outreach_log.phone": prospect_phone})
    
    if not or_conditions:
        return {"blocked": False, "reason": "no_identifier"}
    
    # Find recent missions with this prospect
    recent = await _db.aurem_missions.find_one({
        "platform_user_id": user_id,
        "status": "completed",
        "completed_at": {"$gte": since},
        "$or": or_conditions
    }, {"_id": 0, "mission_id": 1, "completed_at": 1})
    
    if recent:
        return {
            "blocked": True,
            "reason": "DEDUP_BLOCKED",
            "last_mission_id": recent.get("mission_id"),
            "last_contact": recent.get("completed_at"),
            "window_days": DEDUP_WINDOW_DAYS
        }
    
    return {"blocked": False}


async def check_daily_limit(channel: str, user_id: str) -> Dict[str, Any]:
    """
    Check if daily channel limit has been reached.
    Returns: {blocked: bool, reason: str, current: int, limit: int}
    """
    if _db is None:
        return {"blocked": False, "reason": "db_unavailable"}
    
    limit = CHANNEL_DAILY_LIMITS.get(channel, 100)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Get or create today's counter document
    counter = await _db.aurem_send_counters.find_one({
        "user_id": user_id,
        "date": today
    })
    
    if not counter:
        # Create new counter for today
        await _db.aurem_send_counters.insert_one({
            "user_id": user_id,
            "date": today,
            "channels": {"email": 0, "whatsapp": 0, "voice": 0},
            "created_at": datetime.now(timezone.utc)
        })
        return {"blocked": False, "current": 0, "limit": limit}
    
    current = counter.get("channels", {}).get(channel, 0)
    
    if current >= limit:
        return {
            "blocked": True,
            "reason": "DAILY_LIMIT_REACHED",
            "channel": channel,
            "current": current,
            "limit": limit,
            "resets_at": f"{today}T00:00:00Z (tomorrow)"
        }
    
    return {"blocked": False, "current": current, "limit": limit}


def check_circuit_breaker(channel: str) -> Dict[str, Any]:
    """
    Check if channel circuit breaker is tripped.
    Returns: {blocked: bool, reason: str, until: datetime}
    """
    if channel in _circuit_breakers:
        until = _circuit_breakers[channel]
        if datetime.now(timezone.utc) < until:
            return {
                "blocked": True,
                "reason": "CIRCUIT_BREAKER_OPEN",
                "channel": channel,
                "until": until.isoformat(),
                "remaining_minutes": int((until - datetime.now(timezone.utc)).seconds / 60)
            }
        else:
            # Breaker has cooled down
            del _circuit_breakers[channel]
    
    return {"blocked": False}


def get_fallback_channel(original_channel: str) -> Optional[str]:
    """
    Get fallback channel when original is unavailable.
    Priority: email → whatsapp → None (skip)
    """
    fallback_order = ["email", "whatsapp"]
    
    try:
        idx = fallback_order.index(original_channel)
        # Try next channel in order
        for alt in fallback_order[idx + 1:]:
            if alt not in _circuit_breakers:
                return alt
    except ValueError:
        pass
    
    return None


async def increment_channel_counter(channel: str, user_id: str):
    """Increment the daily send counter for a channel"""
    if _db is None:
        return
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    await _db.aurem_send_counters.update_one(
        {"user_id": user_id, "date": today},
        {
            "$inc": {f"channels.{channel}": 1},
            "$set": {"last_updated": datetime.now(timezone.utc)}
        },
        upsert=True
    )


def trip_circuit_breaker(channel: str, cooldown_hours: float = 1.0):
    """Trip circuit breaker for a channel"""
    _circuit_breakers[channel] = datetime.now(timezone.utc) + timedelta(hours=cooldown_hours)
    logger.warning(f"[ORCHESTRATOR] Circuit breaker tripped for {channel} ({cooldown_hours}h)")


def reset_circuit_breaker(channel: str):
    """Manually reset a circuit breaker"""
    if channel in _circuit_breakers:
        del _circuit_breakers[channel]
        logger.info(f"[ORCHESTRATOR] Circuit breaker reset for {channel}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPROVAL FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

async def approve_outreach(
    prospect_email: Optional[str],
    prospect_phone: Optional[str],
    channel: str,
    user_id: str
) -> Dict[str, Any]:
    """
    Main orchestrator function - approves or blocks outreach.
    
    Returns:
        {
            approved: bool,
            channel: str (may be fallback),
            reason: str (if blocked),
            checks: {dedup: {...}, limit: {...}, breaker: {...}}
        }
    """
    checks = {}
    
    # 1. Dedup check
    dedup_result = await check_dedup(prospect_email, prospect_phone, user_id)
    checks["dedup"] = dedup_result
    if dedup_result.get("blocked"):
        return {
            "approved": False,
            "channel": channel,
            "reason": dedup_result.get("reason"),
            "checks": checks
        }
    
    # 2. Circuit breaker check
    breaker_result = check_circuit_breaker(channel)
    checks["circuit_breaker"] = breaker_result
    if breaker_result.get("blocked"):
        # Try fallback channel
        fallback = get_fallback_channel(channel)
        if fallback:
            logger.info(f"[ORCHESTRATOR] Routing from {channel} to fallback {fallback}")
            channel = fallback
            # Re-check breaker for fallback
            breaker_result = check_circuit_breaker(fallback)
            checks["circuit_breaker_fallback"] = breaker_result
            if breaker_result.get("blocked"):
                return {
                    "approved": False,
                    "channel": channel,
                    "reason": "ALL_CHANNELS_BLOCKED",
                    "checks": checks
                }
        else:
            return {
                "approved": False,
                "channel": channel,
                "reason": breaker_result.get("reason"),
                "checks": checks
            }
    
    # 3. Daily limit check
    limit_result = await check_daily_limit(channel, user_id)
    checks["daily_limit"] = limit_result
    if limit_result.get("blocked"):
        # Try fallback channel
        fallback = get_fallback_channel(channel)
        if fallback:
            limit_fallback = await check_daily_limit(fallback, user_id)
            if not limit_fallback.get("blocked"):
                logger.info(f"[ORCHESTRATOR] Daily limit hit for {channel}, using {fallback}")
                channel = fallback
                checks["daily_limit_fallback"] = limit_fallback
            else:
                return {
                    "approved": False,
                    "channel": channel,
                    "reason": "ALL_CHANNELS_AT_LIMIT",
                    "checks": checks
                }
        else:
            return {
                "approved": False,
                "channel": channel,
                "reason": limit_result.get("reason"),
                "checks": checks
            }
    
    # All checks passed
    return {
        "approved": True,
        "channel": channel,
        "reason": "APPROVED",
        "checks": checks
    }


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/status")
async def get_orchestrator_status():
    """Get orchestrator status and circuit breaker states"""
    return {
        "circuit_breakers": {
            ch: {"tripped": ch in _circuit_breakers, "until": _circuit_breakers.get(ch, {}).isoformat() if ch in _circuit_breakers else None}
            for ch in CHANNEL_DAILY_LIMITS.keys()
        },
        "channel_limits": CHANNEL_DAILY_LIMITS,
        "dedup_window_days": DEDUP_WINDOW_DAYS
    }


@router.post("/check")
async def check_approval(
    prospect_email: Optional[str] = None,
    prospect_phone: Optional[str] = None,
    channel: str = "email",
    user_id: str = "test_user"
):
    """Check if outreach would be approved (without incrementing counters)"""
    return await approve_outreach(prospect_email, prospect_phone, channel, user_id)


@router.get("/counters/{user_id}")
async def get_user_counters(user_id: str):
    """Get today's send counters for a user"""
    if _db is None:
        return {"error": "Database not available"}
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    counter = await _db.aurem_send_counters.find_one(
        {"user_id": user_id, "date": today},
        {"_id": 0}
    )
    
    return {
        "date": today,
        "channels": counter.get("channels", {}) if counter else {"email": 0, "whatsapp": 0, "voice": 0},
        "limits": CHANNEL_DAILY_LIMITS
    }


@router.post("/reset-breaker/{channel}")
async def reset_breaker_endpoint(channel: str):
    """Reset a circuit breaker (admin action)"""
    reset_circuit_breaker(channel)
    return {"success": True, "channel": channel, "status": "reset"}


@router.post("/trip-breaker/{channel}")
async def trip_breaker_endpoint(channel: str, cooldown_hours: float = 1.0):
    """Manually trip a circuit breaker (for testing)"""
    trip_circuit_breaker(channel, cooldown_hours)
    return {"success": True, "channel": channel, "until": _circuit_breakers[channel].isoformat()}
