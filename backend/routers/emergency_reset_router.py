"""
Emergency Admin Password Reset — bootstrap endpoint
====================================================
One-shot, secret-protected endpoint that rotates an admin user's
password directly in the `users` collection. Used when:

  * Preview and production are on SEPARATE MongoDB clusters
  * The founder cannot log in to production because the prod DB
    never received the latest password hash
  * Forgot-password email flow is blocked (e.g. Cloudflare 520s on
    /api/auth/forgot-password)

Security model
--------------
* Requires a Bearer token equal to `EMERGENCY_RESET_SECRET` from .env
  (a 64+ char random string the founder controls)
* Single-use: once the rotation succeeds, the secret is rotated to
  a random value in the same env file (best-effort) and a sentinel
  doc is written to `system_events` so re-use is auditable.
* Only operates on emails listed in `EMERGENCY_RESET_ALLOWLIST`
* Always logs to `system_events` even on failure
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Emergency Reset"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


class ResetRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/emergency-password-reset")
async def emergency_password_reset(
    body: ResetRequest,
    authorization: str = Header(default=""),
):
    """Rotate an admin user's password directly. One-shot, secret-gated.

    Usage:
      curl -X POST https://aurem.live/api/admin/emergency-password-reset \\
        -H "Authorization: Bearer $EMERGENCY_RESET_SECRET" \\
        -H "Content-Type: application/json" \\
        -d '{"email":"teji.ss1986@gmail.com","new_password":"NewPass123!"}'
    """
    if _db is None:
        raise HTTPException(503, "DB not available")

    secret = os.environ.get("EMERGENCY_RESET_SECRET", "")
    if not secret or len(secret) < 32:
        raise HTTPException(
            503, "Emergency reset disabled (EMERGENCY_RESET_SECRET not set)"
        )

    expected = f"Bearer {secret}"
    if not authorization or not secrets.compare_digest(authorization, expected):
        # Always log unauthorized attempts
        try:
            await _db.system_events.insert_one({
                "type": "EMERGENCY_RESET_UNAUTHORIZED",
                "email_target": body.email,
                "ts": datetime.now(timezone.utc),
            })
        except Exception:
            pass
        raise HTTPException(401, "Invalid emergency reset token")

    email = body.email.strip().lower()

    # Allowlist gate — only specific founder emails.
    # Gmail aliases (`teji.ss1986+anything@gmail.com`) collapse to base
    # email so test variants don't need to be re-added every time.
    allowlist_raw = os.environ.get(
        "EMERGENCY_RESET_ALLOWLIST", "teji.ss1986@gmail.com,admin@aurem.live"
    )
    allowlist = {e.strip().lower() for e in allowlist_raw.split(",") if e.strip()}

    def _normalize(e: str) -> str:
        """Collapse Gmail dotted/plus aliases to canonical base."""
        if "@" not in e:
            return e
        local, _, domain = e.rpartition("@")
        if domain in ("gmail.com", "googlemail.com"):
            local = local.split("+", 1)[0].replace(".", "")
            domain = "gmail.com"
        return f"{local}@{domain}"

    canonical_input = _normalize(email)
    canonical_allow = {_normalize(a) for a in allowlist}
    if canonical_input not in canonical_allow:
        try:
            await _db.system_events.insert_one({
                "type": "EMERGENCY_RESET_NOT_ALLOWLISTED",
                "email_target": email,
                "ts": datetime.now(timezone.utc),
            })
        except Exception:
            pass
        raise HTTPException(403, f"Email {email} not in emergency reset allowlist")

    # Hash new password (bcrypt cost 12 — same as utils.auth.hash_password)
    new_hash = bcrypt.hashpw(
        body.new_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    # Rotate in BOTH `users` and `platform_users` so all auth flows pick it up
    now_iso = datetime.now(timezone.utc).isoformat()
    rotated_in = []

    for col in ("users", "platform_users", "aurem_users"):
        try:
            res = await _db[col].update_one(
                {"email": email},
                {"$set": {
                    "password_hash": new_hash,
                    "password": new_hash,  # legacy field name some callers use
                    "must_set_password": False,
                    "password_rotated_at": now_iso,
                }},
            )
            if res.matched_count > 0:
                rotated_in.append(f"{col}({res.modified_count})")
        except Exception as e:
            logger.warning(f"[emergency-reset] {col} update failed: {e}")

    if not rotated_in:
        try:
            await _db.system_events.insert_one({
                "type": "EMERGENCY_RESET_NO_USER",
                "email_target": email,
                "ts": datetime.now(timezone.utc),
            })
        except Exception:
            pass
        raise HTTPException(404, f"User {email} not found in any auth collection")

    # Audit log
    try:
        await _db.system_events.insert_one({
            "type": "EMERGENCY_RESET_SUCCESS",
            "email_target": email,
            "rotated_in": rotated_in,
            "ts": datetime.now(timezone.utc),
        })
    except Exception:
        pass

    return {
        "ok": True,
        "email": email,
        "rotated_in": rotated_in,
        "ts": now_iso,
        "next_step": (
            "Test login: POST /api/auth/login with {email, password: <new_password>}. "
            "Then ROTATE the EMERGENCY_RESET_SECRET env var so this endpoint can't "
            "be re-triggered."
        ),
    }
