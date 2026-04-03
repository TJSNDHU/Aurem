"""
UptimeRobot External Monitoring
═══════════════════════════════════════════════════════════════════
EXTERNAL monitoring that works even when our server is completely down.
UptimeRobot runs independently and alerts via SMS/email if health check fails.

This catches failures that auto-heal cannot detect:
- Emergent credit exhaustion
- Complete server crash
- DNS failures
- SSL certificate expiry

SETUP INSTRUCTIONS:
═══════════════════════════════════════════════════════════════════

1. Sign up free at https://uptimerobot.com

2. Create new monitor:
   - Monitor Type: HTTP(s)
   - Friendly Name: ReRoots Production
   - URL: https://reroots.ca/api/health
   - Monitoring Interval: 5 minutes

3. Add alert contacts:
   - Email: tj@reroots.ca
   - SMS: +1 416 886 9408 (requires Pro plan or use free email)

4. Optional monitors to add:
   - https://reroots.ca/api/ai/chat (AI service health)
   - https://reroots.ca (frontend availability)

ALTERNATIVE FREE SERVICES:
═══════════════════════════════════════════════════════════════════
- BetterUptime.com (generous free tier with SMS)
- Freshping by Freshworks (free, 1-min checks)
- StatusCake (10 free monitors)
- Pingdom (free trial)

═══════════════════════════════════════════════════════════════════
© 2025 Reroots Aesthetics Inc. All rights reserved.
"""

# This file is documentation only - UptimeRobot runs externally
# No code execution needed here

UPTIME_CONFIG = {
    "service": "UptimeRobot",
    "monitors": [
        {
            "name": "ReRoots Production Health",
            "url": "https://reroots.ca/api/health",
            "interval_minutes": 5,
            "alert_contacts": ["tj@reroots.ca", "+14168869408"]
        },
        {
            "name": "ReRoots AI Service",
            "url": "https://reroots.ca/api/ai/chat",
            "interval_minutes": 5,
            "method": "POST",
            "note": "Optional - monitors AI availability"
        },
        {
            "name": "ReRoots Frontend",
            "url": "https://reroots.ca",
            "interval_minutes": 5,
            "note": "Optional - monitors website availability"
        }
    ],
    "why_external": [
        "Works when Emergent credits run out",
        "Works when server is completely crashed", 
        "Works when auto-heal itself fails",
        "Works when MongoDB is down",
        "Independent infrastructure = true redundancy"
    ]
}


def get_health_endpoint_requirements():
    """
    Requirements for /api/health endpoint to work with UptimeRobot.
    Our health endpoint should return:
    - HTTP 200 if healthy
    - HTTP 503 if unhealthy
    - Response time < 30 seconds
    """
    return {
        "endpoint": "/api/health",
        "method": "GET",
        "expected_status": 200,
        "timeout_seconds": 30,
        "response_should_include": {
            "status": "healthy",
            "services": {
                "database": "connected",
                "ai": "ready"
            }
        }
    }
