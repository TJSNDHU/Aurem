"""
AUREM Kill Switch Service — SOC 2 Operational Control
======================================================
Provides global emergency controls:
  1. Disable all Live-Patch injections globally
  2. Revoke all active V2V sessions
  3. Put system into Maintenance Mode

All actions are audit-logged for SOC 2 evidence.
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_db: Optional[AsyncIOMotorDatabase] = None

# In-memory kill switch state (also persisted to DB)
_kill_switch_state = {
    "live_patches_disabled": False,
    "v2v_sessions_revoked": False,
    "maintenance_mode": False,
    "activated_by": None,
    "activated_at": None,
}


def set_db(database):
    global _db
    _db = database


def get_kill_switch_state() -> Dict[str, Any]:
    """Return current kill switch state (read by other services)."""
    return dict(_kill_switch_state)


def is_live_patches_disabled() -> bool:
    return _kill_switch_state["live_patches_disabled"]


def is_maintenance_mode() -> bool:
    return _kill_switch_state["maintenance_mode"]


async def load_state_from_db():
    """Load persisted kill switch state on startup."""
    global _kill_switch_state
    if _db is None:
        return
    doc = await _db["system_config"].find_one({"config_key": "kill_switch"}, {"_id": 0})
    if doc and doc.get("state"):
        _kill_switch_state.update(doc["state"])
        logger.info(f"[KillSwitch] Loaded state from DB: {_kill_switch_state}")


async def _persist_state():
    """Persist current state to DB."""
    if _db is None:
        return
    await _db["system_config"].update_one(
        {"config_key": "kill_switch"},
        {"$set": {"state": _kill_switch_state, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )


async def _audit_log(action: str, actor_id: str, details: Dict):
    """Write audit entry for kill switch action."""
    if _db is None:
        return
    await _db["aurem_audit_logs"].insert_one({
        "action": action,
        "business_id": "platform",
        "actor_id": actor_id,
        "actor_type": "admin",
        "resource_type": "kill_switch",
        "resource_id": "global",
        "details": details,
        "ip_address": details.get("ip_address"),
        "user_agent": details.get("user_agent"),
        "success": True,
        "timestamp": datetime.now(timezone.utc),
        "_immutable": True,
    })


async def disable_live_patches(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """Globally disable all Live-Patch injections."""
    _kill_switch_state["live_patches_disabled"] = True
    _kill_switch_state["activated_by"] = actor_id
    _kill_switch_state["activated_at"] = datetime.now(timezone.utc).isoformat()
    await _persist_state()
    await _audit_log("live_patches_disabled", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
        "reason": "Admin manually disabled live patches"
    })
    logger.warning(f"[KillSwitch] Live patches DISABLED by {actor_id}")
    return {"status": "disabled", "component": "live_patches"}


async def enable_live_patches(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """Re-enable Live-Patch injections."""
    _kill_switch_state["live_patches_disabled"] = False
    await _persist_state()
    await _audit_log("live_patches_enabled", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
    })
    logger.info(f"[KillSwitch] Live patches RE-ENABLED by {actor_id}")
    return {"status": "enabled", "component": "live_patches"}


async def revoke_v2v_sessions(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """Revoke all active V2V WebRTC sessions."""
    revoked_count = 0
    if _db is not None:
        result = await _db["v2v_sessions"].update_many(
            {"status": "active"},
            {"$set": {"status": "revoked", "revoked_at": datetime.now(timezone.utc).isoformat(), "revoked_by": actor_id}},
        )
        revoked_count = result.modified_count
    _kill_switch_state["v2v_sessions_revoked"] = True
    await _persist_state()
    await _audit_log("v2v_sessions_revoked", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
        "revoked_count": revoked_count,
    })
    logger.warning(f"[KillSwitch] V2V sessions REVOKED ({revoked_count}) by {actor_id}")
    return {"status": "revoked", "component": "v2v_sessions", "revoked_count": revoked_count}


async def enable_maintenance_mode(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """Put entire system into Maintenance Mode."""
    _kill_switch_state["maintenance_mode"] = True
    _kill_switch_state["activated_by"] = actor_id
    _kill_switch_state["activated_at"] = datetime.now(timezone.utc).isoformat()
    await _persist_state()
    await _audit_log("maintenance_mode_on", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
    })
    logger.warning(f"[KillSwitch] MAINTENANCE MODE activated by {actor_id}")
    return {"status": "active", "component": "maintenance_mode"}


async def disable_maintenance_mode(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """Exit Maintenance Mode."""
    _kill_switch_state["maintenance_mode"] = False
    _kill_switch_state["v2v_sessions_revoked"] = False
    await _persist_state()
    await _audit_log("maintenance_mode_off", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
    })
    logger.info(f"[KillSwitch] Maintenance mode DEACTIVATED by {actor_id}")
    return {"status": "inactive", "component": "maintenance_mode"}


async def activate_full_kill_switch(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """EMERGENCY: Activate all kill switch controls at once."""
    results = []
    results.append(await disable_live_patches(actor_id, ip_address, user_agent))
    results.append(await revoke_v2v_sessions(actor_id, ip_address, user_agent))
    results.append(await enable_maintenance_mode(actor_id, ip_address, user_agent))
    await _audit_log("kill_switch_activated", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
        "scope": "full",
    })
    logger.critical(f"[KillSwitch] FULL KILL SWITCH activated by {actor_id}")
    return {"status": "activated", "scope": "full", "results": results}


async def deactivate_full_kill_switch(actor_id: str, ip_address: str = "", user_agent: str = "") -> Dict:
    """Deactivate all kill switch controls."""
    results = []
    results.append(await enable_live_patches(actor_id, ip_address, user_agent))
    results.append(await disable_maintenance_mode(actor_id, ip_address, user_agent))
    await _audit_log("kill_switch_deactivated", actor_id, {
        "ip_address": ip_address, "user_agent": user_agent,
        "scope": "full",
    })
    logger.info(f"[KillSwitch] Full kill switch DEACTIVATED by {actor_id}")
    return {"status": "deactivated", "scope": "full", "results": results}
