"""
TOTP + Refresh Token service for Founder/Super-Admin auth hardening.
- TOTP: pyotp (RFC 6238). 30s step. SHA1.
- Refresh tokens: opaque random tokens hashed in DB (sha256), 7-day TTL,
  rotated on each refresh, revocable.
"""
import os
import hashlib
import secrets
import io
import base64
from datetime import datetime, timezone, timedelta
from typing import Optional

import pyotp
import qrcode

ISSUER = os.environ.get("AUREM_TOTP_ISSUER", "AUREM Admin")

ADMIN_ACCESS_TOKEN_HOURS = 8
REFRESH_TOKEN_DAYS = 7


def generate_totp_secret() -> str:
    """Base32 secret for new enrolment."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, account_email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account_email, issuer_name=ISSUER)


def qr_data_url(uri: str) -> str:
    """Return a data:image/png;base64 QR for the provisioning URI."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1)
    except Exception:
        return False


# ──────────── Refresh tokens ────────────

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_refresh_token(db, user_id: str, *, ip: str = "", ua: str = "") -> str:
    raw = secrets.token_urlsafe(48)
    await db.admin_refresh_tokens.insert_one({
        "user_id": user_id,
        "token_hash": _hash_token(raw),
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_DAYS)).isoformat(),
        "ip": ip,
        "ua": ua,
        "revoked": False,
    })
    return raw


async def consume_refresh_token(db, raw_token: str) -> Optional[str]:
    """Validate + revoke a refresh token. Returns user_id if valid."""
    if not raw_token:
        return None
    th = _hash_token(raw_token)
    row = await db.admin_refresh_tokens.find_one({"token_hash": th, "revoked": False})
    if not row:
        return None
    try:
        exp = datetime.fromisoformat(row["expires_at"])
    except Exception:
        return None
    if exp < datetime.now(timezone.utc):
        return None
    # Rotate: revoke this token immediately
    await db.admin_refresh_tokens.update_one(
        {"_id": row["_id"]},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}},
    )
    return row.get("user_id")


async def revoke_all_refresh_tokens(db, user_id: str) -> int:
    res = await db.admin_refresh_tokens.update_many(
        {"user_id": user_id, "revoked": False},
        {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc).isoformat()}},
    )
    return res.modified_count
