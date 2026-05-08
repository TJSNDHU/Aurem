"""
AUREM Daily Intel Engine — Phase 2
====================================
Every morning at 7 AM customer's local time, we scrape fresh news in their
niche (biotech, skincare, SaaS, local service, etc.) via Tavily and ship
a curated HTML digest via Resend.

Data flow:
  customer_subscriptions[service_id=daily_intel] → cron
    → tavily.search(niche keywords, fresh:day)
    → format HTML digest
    → send via Resend
    → log to db.daily_intel_log

Subscribers:
  POST /api/daily-intel/subscribe — CASL double opt-in
  GET  /api/daily-intel/status    — my subscription
  POST /api/daily-intel/unsubscribe
"""
from __future__ import annotations

import os
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, EmailStr, Field
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/daily-intel", tags=["Daily Intel"])
_db = None

TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")


def set_db(database):
    global _db
    _db = database


def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    secret = os.environ.get("JWT_SECRET")
    try:
        return jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")


async def _require_user(request: Request) -> dict:
    p = _decode_jwt(request)
    email = (p.get("email") or p.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "no email")
    return {"email": email}


class SubscribeBody(BaseModel):
    email: EmailStr
    niche: str = Field(..., min_length=2, max_length=80)  # "biotech", "skincare", etc.
    keywords: Optional[list] = None
    consent_daily_digest: bool = Field(..., description="CASL double opt-in")
    timezone_offset: int = Field(default=-300)  # minutes from UTC (-300 = EST)


@router.post("/subscribe")
async def subscribe(body: SubscribeBody):
    """Double opt-in signup. CASL requires explicit consent."""
    if not body.consent_daily_digest:
        raise HTTPException(400, "Consent required for CASL compliance")
    if _db is None:
        raise HTTPException(503, "DB not ready")

    doc = {
        "email": body.email.lower(),
        "niche": body.niche,
        "keywords": body.keywords or [body.niche],
        "consent_daily_digest": True,
        "consent_timestamp": datetime.now(timezone.utc).isoformat(),
        "timezone_offset": body.timezone_offset,
        "status": "pending_confirmation",  # flip to 'active' on email click
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.daily_intel_subscribers.update_one(
        {"email": body.email.lower()},
        {"$set": doc},
        upsert=True,
    )

    # Send confirmation email
    if RESEND_KEY:
        try:
            confirm_url = f"https://aurem.live/daily-intel/confirm?email={body.email}"
            async with httpx.AsyncClient(timeout=8) as c:
                await c.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {RESEND_KEY}"},
                    json={
                        "from": RESEND_FROM, "to": [body.email],
                        "subject": "Confirm your AUREM Daily Intel subscription",
                        "html": f"""
                        <h2>Almost done 🎯</h2>
                        <p>Click below to confirm you want the AUREM Daily Intel digest for <strong>{body.niche}</strong>:</p>
                        <p><a href="{confirm_url}" style="background:#C9A84C;color:#000;padding:12px 24px;text-decoration:none;border-radius:6px;">Confirm Subscription</a></p>
                        <p style="color:#888;font-size:11px;">Required by CASL. You can unsubscribe any time.</p>
                        """,
                    },
                )
        except Exception as e:
            logger.warning(f"[daily-intel] confirm email failed: {e}")

    return {"ok": True, "status": "pending_confirmation"}


@router.get("/confirm")
async def confirm(email: str):
    if _db is None:
        raise HTTPException(503, "DB not ready")
    r = await _db.daily_intel_subscribers.update_one(
        {"email": email.lower()},
        {"$set": {"status": "active", "confirmed_at": datetime.now(timezone.utc).isoformat()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "Subscription not found")
    return {"ok": True, "status": "active"}


@router.get("/status")
async def my_status(user: dict = Depends(_require_user)):
    doc = await _db.daily_intel_subscribers.find_one({"email": user["email"]}, {"_id": 0})
    return doc or {"email": user["email"], "status": "not_subscribed"}


@router.post("/unsubscribe")
async def unsubscribe(user: dict = Depends(_require_user)):
    await _db.daily_intel_subscribers.update_one(
        {"email": user["email"]},
        {"$set": {"status": "unsubscribed", "unsubscribed_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


# ═════ Internal: called by scheduler ═════
async def fetch_niche_intel(niche: str, keywords: list) -> list:
    """Tavily search — returns fresh articles."""
    if not TAVILY_KEY:
        return []
    try:
        q = " OR ".join(keywords[:5]) if keywords else niche
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_KEY,
                    "query": f"{q} latest news competitors launches",
                    "topic": "news",
                    "days": 1,
                    "max_results": 5,
                    "include_answer": False,
                },
            )
            return r.json().get("results", [])
    except Exception as e:
        logger.warning(f"[daily-intel] tavily: {e}")
        return []


async def send_daily_digest(subscriber: dict) -> bool:
    articles = await fetch_niche_intel(subscriber.get("niche", ""), subscriber.get("keywords", []))
    if not articles:
        return False
    rows = "".join([
        f"""<tr><td style="padding:12px 0;border-bottom:1px solid #eee;">
          <a href="{a.get('url')}" style="color:#C9A84C;font-weight:600;text-decoration:none;">{a.get('title', '')}</a>
          <p style="margin:4px 0;color:#555;font-size:13px;">{(a.get('content') or '')[:200]}…</p>
        </td></tr>"""
        for a in articles
    ])
    if not RESEND_KEY:
        return False
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_KEY}"},
                json={
                    "from": RESEND_FROM, "to": [subscriber["email"]],
                    "subject": f"AUREM Daily Intel · {subscriber.get('niche', '')} · {datetime.now().strftime('%b %d')}",
                    "html": f"""
                    <h2>Your {subscriber.get('niche')} briefing for today</h2>
                    <table style="width:100%;max-width:600px;">{rows}</table>
                    <p style="color:#888;font-size:11px;margin-top:20px;">
                      AUREM Daily Intel · <a href="https://aurem.live/daily-intel/unsubscribe?email={subscriber['email']}" style="color:#888;">Unsubscribe</a>
                    </p>
                    """,
                },
            )
        # Log send
        if _db is not None:
            await _db.daily_intel_log.insert_one({
                "email": subscriber["email"],
                "niche": subscriber.get("niche"),
                "article_count": len(articles),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
        return True
    except Exception as e:
        logger.warning(f"[daily-intel] send failed for {subscriber['email']}: {e}")
        return False


async def run_daily_intel_batch() -> int:
    """Called by cron scheduler. Returns count of digests sent."""
    if _db is None or not RESEND_KEY or not TAVILY_KEY:
        return 0
    sent = 0
    cursor = _db.daily_intel_subscribers.find({"status": "active"}, {"_id": 0})
    async for sub in cursor:
        if await send_daily_digest(sub):
            sent += 1
    return sent
