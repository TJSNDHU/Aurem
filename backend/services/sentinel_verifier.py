"""
AUREM Sentinel — Stage 4: VERIFY + LEARN
==========================================
After every fix:
1. Wait 30 seconds
2. Re-run the exact check that triggered the fix
3. If resolved: log success, update known_fixes
4. If NOT resolved: escalate, try next fix
5. After 3 failed attempts: alert human, pause
"""

import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def verify_fixes(db, fix_results: list, observer_fn) -> list:
    """
    STAGE 4: Verify each applied fix, then learn from results.
    observer_fn: function to re-check a specific service.
    """
    # Services that are external and cannot be fixed by Sentinel
    EXTERNAL_SERVICES = {"mongodb", "frontend", "redis"}

    verified = []

    for fix in fix_results:
        if not fix.get("success"):
            # Fix wasn't applied (human required) — skip verification
            verified.append({**fix, "verified": False, "verification": "skipped"})
            continue

        service = fix.get("service", "unknown")
        fix_type = fix.get("fix_type", "unknown")

        # External services — Sentinel cannot fix these, only alert
        if service in EXTERNAL_SERVICES:
            logger.info(f"[Sentinel] {service} is external — alert only, no fix attempted")
            verified.append({**fix, "verified": False, "verification": "external_service_alert_only"})
            continue

        # Wait 30 seconds before re-checking
        await asyncio.sleep(30)

        # Re-run the check
        try:
            recheck = await observer_fn(service)
            new_issues = recheck.get("issues", [])
            resolved = len(new_issues) == 0

            if resolved:
                # Success — log and update known_fixes
                logger.info(f"[Sentinel] Fix VERIFIED: {fix_type} on {service}")
                await _learn_successful_fix(db, fix)
                verified.append({**fix, "verified": True, "verification": "resolved"})
            else:
                # Not resolved — check retry count
                retry_count = await _get_retry_count(db, service, fix_type)

                if retry_count >= 3:
                    # 3 failed attempts — escalate to human
                    logger.warning(f"[Sentinel] Fix FAILED after 3 attempts: {service}")
                    await _escalate_to_human(db, fix, retry_count)
                    verified.append({**fix, "verified": False, "verification": "escalated_after_3_failures"})
                else:
                    # Increment retry counter
                    await _increment_retry(db, service, fix_type)
                    verified.append({**fix, "verified": False, "verification": f"retry_{retry_count + 1}_of_3"})

        except Exception as e:
            logger.error(f"[Sentinel] Verification error for {service}: {e}")
            verified.append({**fix, "verified": False, "verification": f"error: {e}"})

    # Log verification results
    try:
        if db is not None:
            for v in verified:
                await db.sentinel_verifications.insert_one({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": v.get("service"),
                    "fix_type": v.get("fix_type"),
                    "verified": v.get("verified", False),
                    "verification": v.get("verification", ""),
                })
    except Exception as e:
        logger.warning(f"[Sentinel] Failed to log verification: {e}")

    return verified


async def _learn_successful_fix(db, fix: dict):
    """Add or update known_fixes database with successful fix."""
    try:
        if db is None:
            return

        service = fix.get("service", "")
        fix_type = fix.get("fix_type", "")
        pattern = f"{service}_{fix_type}"

        existing = await db.known_fixes.find_one(
            {"issue_pattern": pattern}, {"_id": 0}
        )

        if existing:
            # Update success rate
            times = existing.get("times_applied", 0) + 1
            old_rate = existing.get("success_rate", 0.5)
            new_rate = ((old_rate * (times - 1)) + 1.0) / times
            await db.known_fixes.update_one(
                {"issue_pattern": pattern},
                {"$set": {
                    "success_rate": round(new_rate, 3),
                    "times_applied": times,
                    "last_applied": datetime.now(timezone.utc).isoformat(),
                    "fix_type": fix_type,
                    "diagnosis": fix.get("diagnosis", ""),
                }},
            )
        else:
            # New known fix
            await db.known_fixes.insert_one({
                "issue_pattern": pattern,
                "fix_type": fix_type,
                "fix_applied": fix.get("message", ""),
                "diagnosis": fix.get("diagnosis", ""),
                "success_rate": 1.0,
                "times_applied": 1,
                "last_applied": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(f"[Sentinel] Learned fix: {pattern}")
    except Exception as e:
        logger.warning(f"[Sentinel] Failed to learn fix: {e}")


async def _get_retry_count(db, service: str, fix_type: str) -> int:
    """Get how many times this fix has been retried recently."""
    try:
        if db is None:
            return 0
        count = await db.sentinel_retries.count_documents({
            "service": service,
            "fix_type": fix_type,
            "resolved": False,
        })
        return count
    except Exception:
        return 0


async def _increment_retry(db, service: str, fix_type: str):
    """Log a retry attempt."""
    try:
        if db is not None:
            await db.sentinel_retries.insert_one({
                "service": service,
                "fix_type": fix_type,
                "resolved": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass


async def _escalate_to_human(db, fix: dict, retry_count: int):
    """Escalate after 3 failed fix attempts."""
    try:
        if db is not None:
            await db.sentinel_alerts.insert_one({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "escalation",
                "service": fix.get("service"),
                "severity": "P0",
                "error": f"Auto-fix failed after {retry_count} attempts",
                "diagnosis": fix.get("diagnosis", ""),
                "fix_type": fix.get("fix_type", ""),
                "status": "pending_human",
            })

        # Try WhatsApp alert
        try:
            from services.auto_heal import send_alert_whatsapp
            await send_alert_whatsapp(
                f"AUREM SENTINEL ESCALATION\n"
                f"Service: {fix.get('service')}\n"
                f"Fix type: {fix.get('fix_type')} failed {retry_count}x\n"
                f"Auto-fix paused for this service.\n"
                f"Manual intervention required."
            )
        except Exception:
            pass

        # Clear retry counter (paused)
        if db is not None:
            await db.sentinel_retries.delete_many({
                "service": fix.get("service"),
                "fix_type": fix.get("fix_type"),
            })

    except Exception as e:
        logger.error(f"[Sentinel] Escalation failed: {e}")
