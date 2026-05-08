"""
LinkedIn Social Publisher — iter 282aj (Prompt 7, Task C).

Publishes LLM-composed posts to LinkedIn via the ugcPosts API. Reuses
`services.outreach_composer.compose_outreach(channel="linkedin")` for
content generation so tone/cache/CASL rules all flow through the same
pipeline as email/SMS/whatsapp drips.

Public surface:
  • publish_linkedin_post(db, post_type, context)
  • queue_post_if_offline(db, post_type, context)
  • drain_queue(db)                — called after user connects LinkedIn
  • weekly_linkedin_tip(db)        — scheduler entrypoint
  • linkedin_publisher_status(db)  — pillar chip probe
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

_UGCPOSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
VALID_TYPES = {"case_study", "repair_win", "weekly_tip"}


def _shape_context_for_composer(context: dict, post_type: str) -> dict:
    """Massage an onboarding/repair/tip payload into a composer-friendly lead."""
    ctx = dict(context or {})
    ctx.setdefault("business_name", ctx.get("business_name") or "a local business")
    ctx.setdefault("city", ctx.get("city") or "")
    ctx.setdefault("province", ctx.get("province") or "")
    ctx.setdefault("category", ctx.get("category") or "general")
    ctx.setdefault("lead_id", f"linkedin-{post_type}-{datetime.now(timezone.utc).strftime('%Y%m%d')}")
    # The scan_content lane is a convenient way to ferry post_type-specific
    # narrative bullets into the LLM prompt without extending the composer.
    narrative = {
        "case_study":  "AUREM just onboarded this client and launched their site.",
        "repair_win":  f"AUREM fixed a live issue on this client's site: {ctx.get('result','')}",
        "weekly_tip":  "Share one actionable tip for Canadian local service businesses about getting found online this week.",
    }.get(post_type, "")
    return {**ctx, "scan_content_for_linkedin": narrative}


async def _compose_post_body(db, post_type: str, context: dict) -> dict:
    ctx = _shape_context_for_composer(context, post_type)
    from services.outreach_composer import compose_outreach
    return await compose_outreach(
        lead=ctx, channel="linkedin", step=1, db=db,
        scan_content=ctx.get("scan_content_for_linkedin"),
    )


# ─────────────────────────────────────────────────────────────────────
# Publish
# ─────────────────────────────────────────────────────────────────────
async def publish_linkedin_post(db, post_type: str, context: dict) -> dict:
    """Compose + post to LinkedIn. Never raises."""
    if post_type not in VALID_TYPES:
        return {"published": False, "reason": f"invalid_post_type:{post_type}"}

    try:
        composed = await _compose_post_body(db, post_type, context)
    except Exception as e:
        logger.warning(f"[linkedin] compose failed: {e}")
        return {"published": False, "reason": "compose_failed"}

    body_text = (composed.get("body") or "").strip()
    if not body_text:
        return {"published": False, "reason": "empty_body"}

    # Token lookup
    try:
        from routers.linkedin_router import get_decrypted_token
        tok = await get_decrypted_token()
    except Exception as e:
        logger.debug(f"[linkedin] token lookup failed: {e}")
        tok = None

    if not tok or not tok.get("profile_id"):
        await queue_post_if_offline(db, post_type, context)
        return {"published": False, "reason": "no_token"}

    payload = {
        "author":          f"urn:li:person:{tok['profile_id']}",
        "lifecycleState":  "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary":     {"text": body_text},
                "shareMediaCategory":  "NONE",
            },
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=15) as cli:
            r = await cli.post(
                _UGCPOSTS_URL,
                headers={
                    "Authorization":             f"Bearer {tok['access_token']}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type":              "application/json",
                },
                json=payload,
            )
        if r.status_code >= 300:
            detail = (r.text or "")[:240]
            logger.warning(f"[linkedin] publish HTTP {r.status_code}: {detail}")
            return {"published": False, "reason": f"http_{r.status_code}", "detail": detail}
        post_id = (r.json() or {}).get("id") or r.headers.get("x-restli-id")
    except Exception as e:
        logger.warning(f"[linkedin] publish network error: {e}")
        return {"published": False, "reason": f"network:{type(e).__name__}"}

    try:
        if db is not None:
            await db.linkedin_posts.insert_one({
                "post_type":        post_type,
                "content":          body_text,
                "linkedin_post_id": post_id,
                "ts":               datetime.now(timezone.utc),
                "cache_hit":        bool(composed.get("cache_hit")),
                "fallback_used":    bool(composed.get("fallback_used")),
            })
    except Exception as e:
        logger.debug(f"[linkedin] post log skipped: {e}")

    return {"published": True, "post_id": post_id}


# ─────────────────────────────────────────────────────────────────────
# Offline queue
# ─────────────────────────────────────────────────────────────────────
async def queue_post_if_offline(db, post_type: str, context: dict) -> dict:
    """Save a post to the pending queue for later auto-drain on reconnect."""
    if db is None:
        return {"queued": False, "reason": "db_unavailable"}
    try:
        await db.linkedin_publish_queue.insert_one({
            "post_type": post_type,
            "context":   dict(context or {}),
            "status":    "pending_auth",
            "ts":        datetime.now(timezone.utc),
        })
        return {"queued": True}
    except Exception as e:
        logger.debug(f"[linkedin] queue save failed: {e}")
        return {"queued": False, "reason": str(e)[:120]}


async def drain_queue(db) -> dict:
    """Publish every pending_auth queue row. Called after OAuth callback."""
    if db is None:
        return {"drained": 0}
    drained = 0
    try:
        cursor = db.linkedin_publish_queue.find(
            {"status": "pending_auth"}, projection={"_id": 1, "post_type": 1, "context": 1},
        )
        rows = await cursor.to_list(length=20)
    except Exception:
        rows = []
    for row in rows:
        res = await publish_linkedin_post(db, row.get("post_type"), row.get("context") or {})
        try:
            new_status = "published" if res.get("published") else "failed"
            await db.linkedin_publish_queue.update_one(
                {"_id": row["_id"]},
                {"$set": {"status": new_status, "result": res,
                           "drained_at": datetime.now(timezone.utc)}},
            )
        except Exception:
            pass
        if res.get("published"):
            drained += 1
    return {"drained": drained}


# ─────────────────────────────────────────────────────────────────────
# Weekly cron entrypoint
# ─────────────────────────────────────────────────────────────────────
async def weekly_linkedin_tip(db) -> dict:
    """Monday 9 AM UTC cron — publish one weekly tip. Never raises."""
    return await publish_linkedin_post(db, "weekly_tip", {
        "business_name": "Canadian local businesses",
        "category":      "general",
        "city":          "Canada",
    })


# ─────────────────────────────────────────────────────────────────────
# Pillar-map chip probe
# ─────────────────────────────────────────────────────────────────────
async def linkedin_publisher_status(db) -> dict:
    """GREEN connected+>7d · YELLOW connected<7d · RED not-connected."""
    if db is None:
        return {"ok": False, "status": "red", "detail": "db unavailable"}
    try:
        doc = await db.linkedin_tokens.find_one({"_id": "admin"})
    except Exception as e:
        return {"ok": False, "status": "red", "detail": f"db: {e}"}
    if not doc:
        return {"ok": False, "status": "red", "detail": "not connected"}
    expires_at = doc.get("expires_at")
    if not isinstance(expires_at, datetime):
        return {"ok": True, "status": "yellow", "detail": "expiry unknown"}
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        return {"ok": False, "status": "red", "detail": "token expired"}
    if expires_at - now <= timedelta(days=7):
        return {"ok": True, "status": "yellow",
                "detail": f"expires {expires_at.isoformat()} (< 7 days)"}
    return {"ok": True, "status": "green",
            "detail": f"connected · expires {expires_at.isoformat()}"}


__all__ = [
    "publish_linkedin_post",
    "queue_post_if_offline",
    "drain_queue",
    "weekly_linkedin_tip",
    "linkedin_publisher_status",
]
