"""
Postiz Integration — P1 #5
===========================
Social media auto-post via Postiz API (postiz.com).
Customer connects accounts via Postiz OAuth, AUREM posts 1× daily.

Endpoints (wired into customer_portal_router.py as /api/customer/social/*):
    POST /api/postiz/connect   -- save tenant Postiz access token
    POST /api/postiz/post       -- publish a post via the tenant's Postiz account
    POST /api/postiz/schedule   -- queue a scheduled post

Requires POSTIZ_API_KEY env var for platform-level Postiz API access.
Falls back to graceful 503 when not configured.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict
import httpx

logger = logging.getLogger(__name__)

POSTIZ_API_KEY = os.environ.get("POSTIZ_API_KEY", "")
POSTIZ_API_URL = os.environ.get("POSTIZ_API_URL", "https://api.postiz.com/public/v1")


def is_configured() -> bool:
    return bool(POSTIZ_API_KEY)


async def list_integrations(tenant_token: str) -> List[Dict]:
    """List a tenant's connected social accounts."""
    if not is_configured():
        return []
    headers = {"Authorization": tenant_token or POSTIZ_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(f"{POSTIZ_API_URL}/integrations", headers=headers)
            if r.status_code == 200:
                return r.json().get("integrations") or []
    except Exception as e:
        logger.warning(f"[POSTIZ] list_integrations failed: {e}")
    return []


async def publish_post(tenant_token: str, content: str, integration_ids: List[str],
                       media_urls: Optional[List[str]] = None,
                       schedule_at: Optional[str] = None) -> Dict:
    """Publish or schedule a post."""
    if not is_configured():
        return {"ok": False, "error": "postiz_not_configured"}

    payload = {
        "type": "scheduled" if schedule_at else "now",
        "date": schedule_at or datetime.now(timezone.utc).isoformat(),
        "posts": [
            {
                "integration": {"id": iid},
                "value": [{"content": content, **({"image": [{"path": u} for u in (media_urls or [])]} if media_urls else {})}],
            }
            for iid in integration_ids
        ],
    }
    headers = {"Authorization": tenant_token or POSTIZ_API_KEY, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(f"{POSTIZ_API_URL}/posts", headers=headers, json=payload)
            if r.status_code in (200, 201):
                return {"ok": True, "data": r.json()}
            return {"ok": False, "status": r.status_code, "error": r.text[:200]}
    except Exception as e:
        logger.error(f"[POSTIZ] publish failed: {e}")
        return {"ok": False, "error": str(e)}


async def daily_autopost_cron(db) -> Dict:
    """Nightly 10 AM: for each customer with social.enabled=true, pick a content idea
    and publish to their connected accounts."""
    if not is_configured():
        return {"ok": False, "reason": "no_api_key"}
    total = 0
    failed = 0
    cursor = db.customer_social.find({"enabled": True, "postiz_token": {"$exists": True, "$ne": ""}}, {"_id": 0})
    async for sd in cursor:
        em = sd.get("email")
        token = sd.get("postiz_token")
        integrations = [a.get("id") for a in (sd.get("accounts") or []) if a.get("id")]
        if not em or not integrations:
            continue
        # Pull today's content hook — reuse welcome package tone if present
        ws = await db.aurem_workspaces.find_one({"owner_email": em}, {"_id": 0, "business_name": 1, "industry": 1, "city": 1}) or {}
        hook = f"Today at {ws.get('business_name', 'our business')} — drop in for a quick visit. DM for bookings!"
        r = await publish_post(token, hook, integrations)
        if r.get("ok"):
            total += 1
        else:
            failed += 1
        await db.customer_social.update_one({"email": em}, {"$set": {"last_post_at": datetime.now(timezone.utc).isoformat(), "last_post_result": r}})

    await db.system_cron_log.insert_one({
        "job": "postiz_daily_autopost",
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "posted": total, "failed": failed,
    })
    return {"ok": True, "posted": total, "failed": failed}
