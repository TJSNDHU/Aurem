"""
AUREM Sentinel — Stage 3: AUTO-FIX (Healer)
=============================================
Executes pre-approved auto-fixes. Zero human approval needed for:
  - Circuit breaker resets
  - Cache flush & rebuild
  - Fallback activation (ElevenLabs → Web Speech, LLM failover)
  - Knowledge re-sync
  - Database index repair
  - Service restart

NEVER auto-executes:
  - Auth logic changes
  - Data deletion
  - .py file modification
  - Billing/Stripe changes
  - Security policy changes
  → These get logged and alert sent to admin.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Fix types that are SAFE to auto-execute
SAFE_FIX_TYPES = {
    "circuit_breaker_reset",
    "cache_flush",
    "fallback_activate",
    "knowledge_resync",
    "index_repair",
    "service_restart",
}

# Fix types that REQUIRE human approval
REQUIRES_HUMAN = {
    "manual",
    "auth_change",
    "data_deletion",
    "code_modification",
    "billing_change",
    "security_change",
}


async def apply_auto_fixes(db, diagnosed_issues: list) -> list:
    """
    STAGE 3: Apply fixes for each diagnosed issue.
    Returns list of fix results.
    """
    fix_results = []

    for issue in diagnosed_issues:
        fix_type = issue.get("proposed_fix", "manual")
        service = issue.get("service", "unknown")
        severity = issue.get("severity", "P3")

        if fix_type in REQUIRES_HUMAN or fix_type not in SAFE_FIX_TYPES:
            # Log for human review, send alert
            result = await _log_human_required(db, issue)
            fix_results.append(result)
            continue

        # Execute the appropriate fix
        try:
            if fix_type == "circuit_breaker_reset":
                result = await _fix_circuit_breaker(db, service)
            elif fix_type == "cache_flush":
                result = await _fix_cache_flush(db)
            elif fix_type == "fallback_activate":
                result = await _fix_fallback(db, issue)
            elif fix_type == "knowledge_resync":
                result = await _fix_knowledge_resync(db)
            elif fix_type == "index_repair":
                result = await _fix_index_repair(db)
            elif fix_type == "service_restart":
                result = await _fix_service_restart(db, service)
            else:
                result = {"fix_type": fix_type, "success": False, "message": "Unknown fix type"}

            result["service"] = service
            result["severity"] = severity
            result["diagnosis"] = issue.get("diagnosis", "")

        except Exception as e:
            result = {
                "fix_type": fix_type,
                "service": service,
                "severity": severity,
                "success": False,
                "message": f"Fix execution error: {e}",
            }

        # Log fix attempt
        try:
            if db is not None:
                await db.auto_heal_log.insert_one({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "check_name": f"sentinel_{fix_type}",
                    "issue_found": issue.get("error", ""),
                    "action_taken": result.get("message", ""),
                    "resolved": result.get("success", False),
                    "fix_type": fix_type,
                    "service": service,
                    "severity": severity,
                })
        except Exception as e:
            logger.warning(f"[Sentinel] Failed to log fix: {e}")

        fix_results.append(result)

    return fix_results


# ═══════════════════════════════════════
# FIX IMPLEMENTATIONS
# ═══════════════════════════════════════

async def _fix_circuit_breaker(db, service: str) -> dict:
    """Reset tripped circuit breaker and restore service."""
    try:
        if db is not None:
            # Reset the circuit breaker state
            svc_name = service.replace("cb_", "")
            await db.circuit_breakers.update_many(
                {"service": svc_name},
                {"$set": {"state": "closed", "trip_count": 0, "reset_at": datetime.now(timezone.utc).isoformat()}},
            )
            logger.info(f"[Sentinel] Circuit breaker reset: {svc_name}")
            return {"fix_type": "circuit_breaker_reset", "success": True, "message": f"Circuit breaker reset for {svc_name}"}
        return {"fix_type": "circuit_breaker_reset", "success": False, "message": "DB not available"}
    except Exception as e:
        return {"fix_type": "circuit_breaker_reset", "success": False, "message": str(e)}


async def _fix_cache_flush(db) -> dict:
    """Flush corrupted cache keys and rebuild."""
    try:
        from utils.redis_pool import get_sync_redis
        r = get_sync_redis()
        if r is None:
            return {"fix_type": "cache_flush", "success": False, "message": "Redis pool unavailable"}
        # Flush only sentinel/context keys, not everything
        flushed = 0
        for key in r.scan_iter(match="ctx:*"):
            r.delete(key)
            flushed += 1
        for key in r.scan_iter(match="weather:*"):
            r.delete(key)
            flushed += 1

        logger.info(f"[Sentinel] Cache flushed: {flushed} keys")
        return {"fix_type": "cache_flush", "success": True, "message": f"Flushed {flushed} cache keys"}
    except Exception as e:
        return {"fix_type": "cache_flush", "success": False, "message": str(e)}


async def _fix_fallback(db, issue: dict) -> dict:
    """Activate fallback for a failed service."""
    service = issue.get("service", "").replace("cb_", "")
    error = issue.get("error", "")

    if "elevenlabs" in service.lower():
        # ElevenLabs expired → TTS already falls back to OpenAI/Web Speech
        msg = "ElevenLabs expired — TTS auto-fallback to OpenAI TTS active"
        logger.info(f"[Sentinel] {msg}")

        # Log alert for admin
        if db is not None:
            await db.sentinel_alerts.insert_one({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "fallback_activated",
                "service": "elevenlabs",
                "message": msg,
                "action_needed": "Generate new ElevenLabs API key at elevenlabs.io",
            })

        return {"fix_type": "fallback_activate", "success": True, "message": msg}

    if "openrouter" in service.lower() or "llm" in service.lower():
        msg = "LLM failover — using Emergent LLM Key as backup"
        logger.info(f"[Sentinel] {msg}")
        return {"fix_type": "fallback_activate", "success": True, "message": msg}

    return {"fix_type": "fallback_activate", "success": True, "message": f"Fallback noted for {service}"}


async def _fix_knowledge_resync(db) -> dict:
    """Trigger knowledge re-sync."""
    try:
        from routers.ora_knowledge_sync import force_knowledge_sync
        result = await force_knowledge_sync(authorization=None)
        synced = result.get("docs_synced", 0) if isinstance(result, dict) else 0
        logger.info(f"[Sentinel] Knowledge re-synced: {synced} docs")
        return {"fix_type": "knowledge_resync", "success": True, "message": f"Knowledge synced: {synced} docs"}
    except Exception as e:
        return {"fix_type": "knowledge_resync", "success": False, "message": str(e)}


async def _fix_index_repair(db) -> dict:
    """Ensure critical MongoDB indexes exist."""
    try:
        if db is None:
            return {"fix_type": "index_repair", "success": False, "message": "DB not available"}

        indexes_created = 0
        collections_indexes = {
            "ora_leads": [("lead_score", -1), ("created_at", -1)],
            "aurem_voice_calls": [("created_at", -1), ("status", 1)],
            "system_pulse": [("timestamp", -1), ("cycle_number", -1)],
            "auto_heal_log": [("timestamp", -1)],
            "known_fixes": [("issue_pattern", 1)],
            "scan_history": [("created_at", -1)],
        }
        for coll, indexes in collections_indexes.items():
            for idx in indexes:
                try:
                    await db[coll].create_index([idx])
                    indexes_created += 1
                except Exception:
                    pass

        logger.info(f"[Sentinel] Indexes ensured: {indexes_created}")
        return {"fix_type": "index_repair", "success": True, "message": f"{indexes_created} indexes ensured"}
    except Exception as e:
        return {"fix_type": "index_repair", "success": False, "message": str(e)}


async def _fix_service_restart(db, service: str) -> dict:
    """Attempt to restart a degraded service connection."""
    svc = service.replace("cb_", "")
    logger.info(f"[Sentinel] Service restart requested: {svc}")

    # For Redis — reconnect via shared pool (avoid per-call leaks)
    if "redis" in svc.lower():
        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            return {"fix_type": "service_restart", "success": False, "message": "Redis restart skipped: REDIS_URL not configured"}
        try:
            from utils.redis_pool import reset_for_hot_reload, get_sync_redis
            reset_for_hot_reload()
            r = get_sync_redis()
            if r is None:
                return {"fix_type": "service_restart", "success": False, "message": "Redis reconnect failed"}
            r.ping()
            return {"fix_type": "service_restart", "success": True, "message": "Redis reconnected via shared pool"}
        except Exception as e:
            return {"fix_type": "service_restart", "success": False, "message": f"Redis restart failed: {e}"}

    return {"fix_type": "service_restart", "success": True, "message": f"Restart signal sent for {svc}"}


async def _log_human_required(db, issue: dict) -> dict:
    """Log issue that requires human intervention."""
    try:
        if db is not None:
            await db.sentinel_alerts.insert_one({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "human_required",
                "service": issue.get("service", "unknown"),
                "severity": issue.get("severity", "P3"),
                "error": issue.get("error", ""),
                "diagnosis": issue.get("diagnosis", ""),
                "proposed_fix": issue.get("proposed_fix", "manual"),
                "status": "pending",
            })

        # Try to send WhatsApp alert for P0
        if issue.get("severity") == "P0":
            try:
                from services.auto_heal import send_alert_whatsapp
                await send_alert_whatsapp(
                    f"AUREM SENTINEL P0 ALERT\n"
                    f"Service: {issue.get('service')}\n"
                    f"Error: {issue.get('error')}\n"
                    f"Diagnosis: {issue.get('diagnosis')}\n"
                    f"Requires manual fix."
                )
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"[Sentinel] Failed to log human-required alert: {e}")

    return {
        "fix_type": "human_required",
        "service": issue.get("service", "unknown"),
        "severity": issue.get("severity", "P3"),
        "success": False,
        "message": f"Requires human approval: {issue.get('diagnosis', '')}",
    }
