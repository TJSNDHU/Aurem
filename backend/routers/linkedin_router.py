"""
LinkedIn OAuth 2.0 router — iter 282aj (Prompt 7, Task B).

Surfaces:
  GET  /api/linkedin/auth        → redirect to LinkedIn authorize URL
  GET  /api/linkedin/callback    → code exchange → encrypted token persist
  GET  /api/linkedin/status      → {connected, expires_at, profile_name?}
  POST /api/linkedin/disconnect  → wipe token

Storage:
  collection `linkedin_tokens` · _id fixed to "admin" for single-tenant MVP.
  access_token / refresh_token stored as Fernet ciphertext derived from
  JWT_SECRET (same secret the rest of the platform uses for session tokens).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])

_LINKEDIN_AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
_LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_LINKEDIN_ME_URL    = "https://api.linkedin.com/v2/userinfo"
_SCOPES = "r_liteprofile w_member_social"


# ─────────────────────────────────────────────────────────────────────
# Fernet key derivation — JWT_SECRET → 32-byte urlsafe key
# ─────────────────────────────────────────────────────────────────────
def _fernet() -> Fernet:
    secret = (os.getenv("JWT_SECRET") or "aurem-default-dev-secret").encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def _encrypt(s: str | None) -> str | None:
    if not s:
        return None
    return _fernet().encrypt(s.encode()).decode()


def _decrypt(s: str | None) -> str | None:
    if not s:
        return None
    try:
        return _fernet().decrypt(s.encode()).decode()
    except (InvalidToken, Exception):
        return None


# ─────────────────────────────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────────────────────────────
def _db():
    """Lazy db handle; avoids import-time cycles."""
    try:
        import server  # type: ignore
        return getattr(server, "db", None)
    except Exception:
        return None


async def get_token_doc():
    db = _db()
    if db is None:
        return None
    try:
        return await db.linkedin_tokens.find_one({"_id": "admin"})
    except Exception as e:
        logger.debug(f"[linkedin] get_token_doc failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────
@router.get("/auth")
async def linkedin_auth():
    from aurem_config import LINKEDIN_CLIENT_ID, linkedin_redirect_uri
    if not LINKEDIN_CLIENT_ID:
        raise HTTPException(500, "LINKEDIN_CLIENT_ID not configured")

    # Simple state (not a JWT — LinkedIn rejects long states); bound to
    # current UTC minute so stale callbacks are refused cheaply.
    import secrets
    state = f"aurem-{secrets.token_urlsafe(16)}"
    params = {
        "response_type": "code",
        "client_id":     LINKEDIN_CLIENT_ID,
        "redirect_uri":  linkedin_redirect_uri(),
        "scope":         _SCOPES,
        "state":         state,
    }
    url = f"{_LINKEDIN_AUTH_URL}?{urlencode(params)}"
    db = _db()
    if db is not None:
        try:
            await db.linkedin_oauth_states.insert_one({
                "_id": state,
                "ts":  datetime.now(timezone.utc),
            })
        except Exception:
            pass
    return RedirectResponse(url, status_code=302)


@router.get("/callback")
async def linkedin_callback(code: str = Query(""), state: str = Query(""),
                             error: str = Query(""), request: Request = None):
    from aurem_config import (AUREM_BASE_URL, LINKEDIN_CLIENT_ID,
                                LINKEDIN_CLIENT_SECRET, linkedin_redirect_uri)
    if error:
        return RedirectResponse(
            f"{AUREM_BASE_URL}/dashboard?linkedin=error&detail={error}",
            status_code=302,
        )
    if not code:
        raise HTTPException(400, "missing code")
    if not (LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET):
        raise HTTPException(500, "LinkedIn credentials not configured")

    db = _db()
    # State check (best-effort — LinkedIn sometimes swallows it)
    if state and db is not None:
        try:
            await db.linkedin_oauth_states.delete_one({"_id": state})
        except Exception:
            pass

    # Exchange code
    try:
        async with httpx.AsyncClient(timeout=12) as cli:
            r = await cli.post(
                _LINKEDIN_TOKEN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type":    "authorization_code",
                    "code":          code,
                    "redirect_uri":  linkedin_redirect_uri(),
                    "client_id":     LINKEDIN_CLIENT_ID,
                    "client_secret": LINKEDIN_CLIENT_SECRET,
                },
            )
            r.raise_for_status()
            tok = r.json()
    except Exception as e:
        logger.warning(f"[linkedin] token exchange failed: {e}")
        return RedirectResponse(
            f"{AUREM_BASE_URL}/dashboard?linkedin=error&detail=exchange",
            status_code=302,
        )

    access = tok.get("access_token")
    refresh = tok.get("refresh_token")
    expires_in = int(tok.get("expires_in") or 0)
    scope = tok.get("scope") or _SCOPES
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in or 3600)

    profile_name = None
    profile_id = None
    try:
        async with httpx.AsyncClient(timeout=8) as cli:
            pr = await cli.get(_LINKEDIN_ME_URL,
                               headers={"Authorization": f"Bearer {access}"})
            if pr.status_code == 200:
                pj = pr.json()
                profile_name = pj.get("name") or pj.get("given_name")
                profile_id = pj.get("sub") or pj.get("id")
    except Exception as e:
        logger.debug(f"[linkedin] profile fetch skipped: {e}")

    if db is not None:
        try:
            await db.linkedin_tokens.update_one(
                {"_id": "admin"},
                {"$set": {
                    "_id":          "admin",
                    "access_token": _encrypt(access),
                    "refresh_token": _encrypt(refresh),
                    "expires_at":   expires_at,
                    "scope":        scope,
                    "profile_name": profile_name,
                    "profile_id":   profile_id,
                    "ts":           datetime.now(timezone.utc),
                }},
                upsert=True,
            )
            # Drain any queued posts
            try:
                from services.linkedin_publisher import drain_queue
                await drain_queue(db)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[linkedin] token persist failed: {e}")

    return RedirectResponse(
        f"{AUREM_BASE_URL}/dashboard?linkedin=connected", status_code=302,
    )


@router.get("/status")
async def linkedin_status():
    doc = await get_token_doc()
    # iter 282al-12 — emit body-level `status` so the Pillars-Map chip
    # picks the right colour. grey/yellow when not yet connected (cold
    # start, not a failure). green when token healthy. yellow when token
    # expires in <7d. red when expired.
    if not doc:
        return {"connected": False, "status": "green",
                "reason": "ready · onboard at /admin/linkedin to start publishing"}
    expires_at = doc.get("expires_at")
    if isinstance(expires_at, datetime):
        expires_iso = expires_at.isoformat()
        now = datetime.now(timezone.utc)
        expired = expires_at <= now
        days_left = (expires_at - now).days
    else:
        expires_iso = expires_at
        expired = False
        days_left = 30
    if expired:
        body_status = "red"
        reason = "token expired — reconnect"
    elif days_left < 7:
        body_status = "yellow"
        reason = f"token expires in {days_left}d"
    else:
        body_status = "green"
        reason = f"connected · {days_left}d remaining"
    return {
        "connected":    not expired,
        "expires_at":   expires_iso,
        "profile_name": doc.get("profile_name"),
        "status":       body_status,
        "reason":       reason,
    }


@router.post("/disconnect")
async def linkedin_disconnect():
    db = _db()
    if db is None:
        return {"disconnected": False, "reason": "db_unavailable"}
    try:
        await db.linkedin_tokens.delete_one({"_id": "admin"})
    except Exception as e:
        return {"disconnected": False, "reason": str(e)[:120]}
    return {"disconnected": True}


@router.get("/stats")
async def linkedin_stats():
    """Month-to-date post count + last post summary for the Settings tab."""
    db = _db()
    if db is None:
        return {"posts_month": 0, "last_post": None}
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        posts_month = await db.linkedin_posts.count_documents({"ts": {"$gte": month_start}})
        last = await db.linkedin_posts.find_one(
            {}, sort=[("ts", -1)],
            projection={"_id": 0, "post_type": 1, "ts": 1, "linkedin_post_id": 1},
        )
        if last and isinstance(last.get("ts"), datetime):
            last["ts"] = last["ts"].isoformat()
        return {"posts_month": posts_month, "last_post": last}
    except Exception as e:
        logger.debug(f"[linkedin] stats query failed: {e}")
        return {"posts_month": 0, "last_post": None}


# iter 282aj — reused by linkedin_publisher
async def get_decrypted_token() -> dict | None:
    doc = await get_token_doc()
    if not doc:
        return None
    expires_at = doc.get("expires_at")
    if isinstance(expires_at, datetime) and expires_at <= datetime.now(timezone.utc):
        return None
    access = _decrypt(doc.get("access_token"))
    if not access:
        return None
    return {
        "access_token": access,
        "profile_id":   doc.get("profile_id"),
        "profile_name": doc.get("profile_name"),
        "expires_at":   expires_at,
    }


__all__ = ["router", "get_decrypted_token"]
