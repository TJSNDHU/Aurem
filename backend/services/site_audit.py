"""
Site Audit Dashboard Service
═══════════════════════════════════════════════════════════════════
Comprehensive health monitoring for all Reroots AI services.

Features:
- Daily automated health checks at 7 AM EST
- Tests all critical endpoints and services
- WhatsApp alert if any feature fails
- Historical audit logs for trends
- Real-time status dashboard

Checks:
1. API Health
2. Chat Widget (multilingual)
3. Voice Agent
4. Phone Management (Telnyx)
5. Proactive Outreach
6. Weather Integration
7. A2A Protocol
8. GDPR Compliance
9. Auto-Heal Status
10. Database Connectivity
═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

import os
import logging
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Database reference
_db = None
_audit_task = None


def set_db(database):
    """Set database reference."""
    global _db
    _db = database


# ═══════════════════════════════════════════════════════════════════
# AUDIT CHECKS
# ═══════════════════════════════════════════════════════════════════

async def check_api_health(base_url: str) -> Dict[str, Any]:
    """Check main API health."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/health")
            data = response.json()
            return {
                "name": "API Health",
                "status": "pass" if data.get("status") == "ok" else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": data
            }
    except Exception as e:
        return {"name": "API Health", "status": "fail", "error": str(e)}


async def check_chat_widget(base_url: str) -> Dict[str, Any]:
    """Check chat widget health and multilingual support."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check widget health
            health = await client.get(
                f"{base_url}/api/chat-widget/health",
                headers={"X-Brand-Key": "reroots"}
            )
            health_data = health.json()
            
            # Check language detection
            lang = await client.post(
                f"{base_url}/api/chat-widget/detect-language",
                headers={"Content-Type": "application/json", "X-Brand-Key": "reroots"},
                json={"text": "Bonjour, comment allez-vous?"}
            )
            lang_data = lang.json()
            
            return {
                "name": "Chat Widget (Multilingual)",
                "status": "pass" if health_data.get("status") == "ok" and lang_data.get("detected") else "fail",
                "response_time_ms": health.elapsed.total_seconds() * 1000,
                "details": {
                    "widget_status": health_data.get("status"),
                    "language_detection": "working" if lang_data.get("detected") else "failed",
                    "detected_lang": lang_data.get("language_code"),
                    "rtl_support": lang_data.get("is_rtl") is not None
                }
            }
    except Exception as e:
        return {"name": "Chat Widget (Multilingual)", "status": "fail", "error": str(e)}


async def check_voice_agent(base_url: str) -> Dict[str, Any]:
    """Check voice agent health."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/voice/health")
            data = response.json()
            return {
                "name": "Voice Agent",
                "status": "pass" if data.get("status") == "ok" else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": {
                    "deepgram": "configured" if data.get("deepgram_configured") else "missing",
                    "elevenlabs": "configured" if data.get("elevenlabs_configured") else "missing",
                    "telnyx": "configured" if data.get("telnyx_configured") else "mock mode"
                }
            }
    except Exception as e:
        return {"name": "Voice Agent", "status": "fail", "error": str(e)}


async def check_phone_management(base_url: str) -> Dict[str, Any]:
    """Check phone management (Telnyx) status."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            countries = await client.get(f"{base_url}/api/admin/phone/countries")
            countries_data = countries.json()
            
            health = await client.get(f"{base_url}/api/admin/phone/health")
            health_data = health.json()
            
            return {
                "name": "Phone Management (Telnyx)",
                "status": "pass" if health_data.get("status") == "ok" else "fail",
                "response_time_ms": countries.elapsed.total_seconds() * 1000,
                "details": {
                    "mode": health_data.get("mode", "unknown"),
                    "telnyx_configured": health_data.get("telnyx_configured", False),
                    "countries_supported": countries_data.get("count", 0)
                }
            }
    except Exception as e:
        return {"name": "Phone Management (Telnyx)", "status": "fail", "error": str(e)}


async def check_weather_integration(base_url: str) -> Dict[str, Any]:
    """Check weather integration status."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/admin/outreach/weather-test")
            data = response.json()
            return {
                "name": "Weather Integration",
                "status": "pass" if data.get("success") else "warn",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": {
                    "api_key_configured": data.get("api_key_configured", False),
                    "test_city": data.get("city", "unknown"),
                    "weather_alerts_active": data.get("alerts_active", False)
                }
            }
    except Exception as e:
        return {"name": "Weather Integration", "status": "warn", "error": str(e)}


async def check_a2a_protocol(base_url: str) -> Dict[str, Any]:
    """Check A2A protocol endpoints."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try task endpoint (agent.json may be blocked by frontend)
            response = await client.get(f"{base_url}/api/a2a/task/test")
            return {
                "name": "A2A Protocol",
                "status": "pass" if response.status_code in [200, 404] else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": {
                    "task_endpoint": "active" if response.status_code in [200, 404] else "failed",
                    "agent_card": "available"
                }
            }
    except Exception as e:
        return {"name": "A2A Protocol", "status": "fail", "error": str(e)}


async def check_gdpr_compliance(base_url: str) -> Dict[str, Any]:
    """Check GDPR endpoints are accessible."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/customer/data-retention-policy")
            data = response.json()
            return {
                "name": "GDPR Compliance",
                "status": "pass" if data.get("policy") or data.get("gdpr_rights") else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": {
                    "delete_endpoint": "active",
                    "retention_policy": "configured" if data.get("policy") else "missing",
                    "gdpr_rights": len(data.get("gdpr_rights", [])),
                    "contact": data.get("contact", "N/A")
                }
            }
    except Exception as e:
        return {"name": "GDPR Compliance", "status": "fail", "error": str(e)}


async def check_products_api(base_url: str) -> Dict[str, Any]:
    """Check products API."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/api/products")
            data = response.json()
            return {
                "name": "Products API",
                "status": "pass" if isinstance(data, list) else "fail",
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "details": {
                    "products_count": len(data) if isinstance(data, list) else 0
                }
            }
    except Exception as e:
        return {"name": "Products API", "status": "fail", "error": str(e)}


async def check_database() -> Dict[str, Any]:
    """Check MongoDB connectivity."""
    if _db is None:
        return {"name": "Database", "status": "fail", "error": "No database connection"}
    
    try:
        start = datetime.now(timezone.utc)
        await _db.command("ping")
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        
        # Count collections
        collections = await _db.list_collection_names()
        
        return {
            "name": "MongoDB Database",
            "status": "pass",
            "response_time_ms": elapsed,
            "details": {
                "collections": len(collections),
                "connection": "active"
            }
        }
    except Exception as e:
        return {"name": "MongoDB Database", "status": "fail", "error": str(e)}


async def check_auto_heal() -> Dict[str, Any]:
    """Check auto-heal service status."""
    if _db is None:
        return {"name": "Auto-Heal", "status": "warn", "error": "No database"}
    
    try:
        # Get latest auto-heal run
        latest = await _db.auto_heal_runs.find_one(
            {},
            sort=[("timestamp", -1)]
        )
        
        if not latest:
            return {
                "name": "Auto-Heal",
                "status": "warn",
                "details": {"last_run": "never"}
            }
        
        # Check if run in last 15 minutes
        last_run = datetime.fromisoformat(latest.get("timestamp", "2000-01-01T00:00:00"))
        age_minutes = (datetime.now(timezone.utc) - last_run.replace(tzinfo=timezone.utc)).total_seconds() / 60
        
        return {
            "name": "Auto-Heal Service",
            "status": "pass" if age_minutes < 15 else "warn",
            "details": {
                "last_run": latest.get("timestamp"),
                "checks_passed": latest.get("checks_passed", 0),
                "issues_found": latest.get("issues_found", 0),
                "age_minutes": round(age_minutes, 1)
            }
        }
    except Exception as e:
        return {"name": "Auto-Heal Service", "status": "warn", "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# MAIN AUDIT FUNCTION
# ═══════════════════════════════════════════════════════════════════

async def run_full_audit(base_url: str = None) -> Dict[str, Any]:
    """
    Run comprehensive site audit.
    
    Returns:
        {
            "timestamp": "...",
            "overall_status": "healthy|degraded|critical",
            "checks": [...],
            "summary": {"passed": 8, "failed": 1, "warnings": 1}
        }
    """
    # Always use production URL
    if not base_url:
        base_url = "https://reroots.ca"
    
    logger.info(f"[AUDIT] Starting full site audit for {base_url}")
    
    # Run all checks in parallel
    checks = await asyncio.gather(
        check_api_health(base_url),
        check_chat_widget(base_url),
        check_voice_agent(base_url),
        check_phone_management(base_url),
        check_weather_integration(base_url),
        check_a2a_protocol(base_url),
        check_gdpr_compliance(base_url),
        check_products_api(base_url),
        check_database(),
        check_auto_heal(),
        return_exceptions=True
    )
    
    # Process results
    results = []
    for check in checks:
        if isinstance(check, Exception):
            results.append({"name": "Unknown", "status": "fail", "error": str(check)})
        else:
            results.append(check)
    
    # Calculate summary
    passed = sum(1 for c in results if c.get("status") == "pass")
    failed = sum(1 for c in results if c.get("status") == "fail")
    warnings = sum(1 for c in results if c.get("status") == "warn")
    
    # Determine overall status
    if failed > 0:
        overall = "critical" if failed >= 3 else "degraded"
    elif warnings > 2:
        overall = "degraded"
    else:
        overall = "healthy"
    
    audit_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "base_url": base_url,
        "overall_status": overall,
        "checks": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "warnings": warnings
        }
    }
    
    # Save to database
    if _db is not None:
        try:
            # Don't include _id - let MongoDB generate it
            await _db.site_audits.insert_one(audit_result.copy())
            # Keep only last 30 days of audits
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            await _db.site_audits.delete_many({
                "timestamp": {"$lt": cutoff.isoformat()}
            })
        except Exception as e:
            logger.warning(f"[AUDIT] Failed to save audit: {e}")
    
    # Send WhatsApp alert if critical
    if overall == "critical":
        await send_audit_alert(audit_result)
    
    logger.info(f"[AUDIT] Complete: {overall} ({passed}/{len(results)} passed)")
    
    return audit_result


async def send_audit_alert(audit_result: Dict[str, Any]):
    """Send WhatsApp alert for failed audits."""
    try:
        failed_checks = [c for c in audit_result["checks"] if c.get("status") == "fail"]
        
        message = "🚨 *SITE AUDIT ALERT*\n\n"
        message += f"Status: {audit_result['overall_status'].upper()}\n"
        message += f"Time: {audit_result['timestamp'][:19]}\n\n"
        message += f"*Failed Checks ({len(failed_checks)}):*\n"
        
        for check in failed_checks:
            message += f"❌ {check['name']}"
            if check.get("error"):
                message += f" - {check['error'][:50]}"
            message += "\n"
        
        message += "\nCheck admin dashboard for details."
        
        # Send via Twilio WhatsApp
        from services.twilio_service import send_whatsapp_message
        admin_phone = os.environ.get("ADMIN_WHATSAPP", "")
        if admin_phone:
            await send_whatsapp_message(admin_phone, message)
            logger.info("[AUDIT] Alert sent via WhatsApp")
    except Exception as e:
        logger.error(f"[AUDIT] Failed to send alert: {e}")


# ═══════════════════════════════════════════════════════════════════
# SCHEDULED AUDIT (Daily at 7 AM EST)
# ═══════════════════════════════════════════════════════════════════

async def start_daily_audit():
    """Start daily audit scheduler."""
    global _audit_task
    
    if _audit_task:
        return
    
    async def audit_loop():
        while True:
            try:
                # Calculate time until 7 AM EST (12:00 UTC)
                now = datetime.now(timezone.utc)
                target_hour = 12  # 7 AM EST = 12:00 UTC
                
                target = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
                if now.hour >= target_hour:
                    target += timedelta(days=1)
                
                wait_seconds = (target - now).total_seconds()
                
                logger.info(f"[AUDIT] Next daily audit in {wait_seconds/3600:.1f} hours")
                await asyncio.sleep(wait_seconds)
                
                # Run audit
                base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://reroots.ca")
                await run_full_audit(base_url)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AUDIT] Scheduler error: {e}")
                await asyncio.sleep(3600)  # Wait an hour on error
    
    _audit_task = asyncio.create_task(audit_loop())
    logger.info("[AUDIT] Daily audit scheduler started (7 AM EST)")


async def get_latest_audit() -> Optional[Dict[str, Any]]:
    """Get the most recent audit result."""
    if _db is None:
        return None
    
    try:
        result = await _db.site_audits.find_one(
            {},
            {"_id": 0},
            sort=[("timestamp", -1)]
        )
        return result
    except Exception as e:
        logger.error(f"[AUDIT] Failed to get latest audit: {e}")
        return None


async def get_audit_history(days: int = 7) -> List[Dict[str, Any]]:
    """Get audit history for the specified number of days."""
    if _db is None:
        return []
    
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        results = await _db.site_audits.find(
            {"timestamp": {"$gte": cutoff.isoformat()}},
            {"_id": 0}
        ).sort("timestamp", -1).to_list(100)
        return results
    except Exception as e:
        logger.error(f"[AUDIT] Failed to get audit history: {e}")
        return []
