"""
routers/security_keys_router.py — iter D-46

One-click security-key generation for AUREM customers.

Customer flow
-------------
1. Founder/customer clicks "Generate security keys" on /developers/settings
2. Backend mints fresh `JWT_SECRET`, `AUREM_ENCRYPTION_KEY`, and a
   `CORS_ORIGINS` default, stores them AES-256 encrypted in
   `customer_security_keys`, marks any prior row for the same user as
   `rotated`, and applies the new values LIVE to `os.environ` (no
   restart needed — every code path that reads from env picks up the
   new secret on the next request).
3. The plaintext values are returned to the client ONCE in the same
   response. They are NEVER fetchable again — only the masked tails
   and metadata.

Admin flow (`/admin/security-keys`)
-----------------------------------
Lists every customer's current key status (active / rotated / none),
IP that triggered the last generation, and lets an admin force-rotate
any customer's keys. Plaintext values are NEVER returned via the admin
endpoints — admins see only `key_tail` (last 4 chars).
"""
from __future__ import annotations

import base64
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from services.credential_crypto import (
    decrypt_credentials, encrypt_credentials, is_encryption_available,
)
from utils.require_auth import require_admin, require_auth

logger = logging.getLogger(__name__)


# Two routers because the admin endpoints live under /api/admin/* but
# the customer-facing endpoints live under /api/developers/*.
dev_router = APIRouter(
    prefix="/api/developers/security",
    tags=["security-keys"],
    dependencies=[Depends(require_auth)],
)
admin_router = APIRouter(
    prefix="/api/admin/security-keys",
    tags=["security-keys"],
    dependencies=[Depends(require_admin)],
)

_db = None
DEFAULT_CORS = "https://aurem.live"


def set_db(database):
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tail4(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    return s[-4:] if len(s) >= 4 else "*" * len(s)


def _generate_triplet() -> dict[str, str]:
    """Mint a fresh `(JWT_SECRET, AUREM_ENCRYPTION_KEY, CORS_ORIGINS)`
    triplet. Cryptographically strong secrets via `secrets`."""
    return {
        "JWT_SECRET":            secrets.token_urlsafe(48),
        "AUREM_ENCRYPTION_KEY":  base64.urlsafe_b64encode(
                                    secrets.token_bytes(32)).decode("ascii"),
        "CORS_ORIGINS":          DEFAULT_CORS,
    }


def _row_summary(row: dict) -> dict[str, Any]:
    """Public-safe shape — no plaintext, only tails + metadata."""
    if not row:
        return {}
    keys = row.get("keys") or {}
    summary: dict[str, Any] = {}
    for k in ("JWT_SECRET", "AUREM_ENCRYPTION_KEY", "CORS_ORIGINS"):
        meta = keys.get(k) or {}
        summary[k] = {
            "set":       bool(meta.get("ct_envelope") or meta.get("value")),
            "key_tail":  meta.get("key_tail", ""),
            "encrypted": bool(meta.get("ct_envelope")),
        }
    return {
        "user_id":      row.get("user_id"),
        "email":        row.get("email"),
        "tenant_id":    row.get("tenant_id"),
        "generated_at": row.get("generated_at"),
        "ip_address":   row.get("ip_address"),
        "status":       row.get("status"),
        "keys":         summary,
    }


# ── Customer endpoints ─────────────────────────────────────────────

class GenerateBody(BaseModel):
    rotate: bool = True


@dev_router.post("/generate-keys")
async def generate_security_keys(
    body: GenerateBody = GenerateBody(),
    request: Request = None,
    user=Depends(require_auth),
) -> dict[str, Any]:
    """Mint a fresh triplet, encrypt at rest, apply live to env.
    Plaintext values are returned to the caller ONCE — never again."""
    if _db is None:
        raise HTTPException(503, "db_unavailable")

    triplet = _generate_triplet()
    user_id = user.get("user_id") or user.get("id") or user.get("email")
    if not user_id:
        raise HTTPException(401, "user_id_unavailable")

    # Mark any prior active row for this user as rotated.
    if body.rotate:
        await _db.customer_security_keys.update_many(
            {"user_id": user_id, "status": "active"},
            {"$set": {"status": "rotated",
                       "rotated_at": _now().isoformat()}},
        )

    # Build the encrypted envelope (each value gets its own envelope so
    # rotating just one secret later is straightforward).
    keys_doc: dict[str, dict[str, Any]] = {}
    for name, value in triplet.items():
        env = encrypt_credentials({"value": value})
        keys_doc[name] = {
            "ct_envelope": env,
            "key_tail":    _tail4(value),
        }

    ip = ""
    try:
        if request and request.client:
            ip = request.client.host or ""
    except Exception:
        pass

    row = {
        "user_id":      user_id,
        "email":        user.get("email", ""),
        "tenant_id":    user.get("tenant_id", "default"),
        "generated_at": _now().isoformat(),
        "ip_address":   ip,
        "status":       "active",
        "keys":         keys_doc,
    }
    await _db.customer_security_keys.insert_one(dict(row))

    # Apply live so the running backend picks up the new values without
    # restart (mirrors the D-43 platform-secrets pattern).
    for name, value in triplet.items():
        os.environ[name] = value
    logger.info(f"[security-keys] generated triplet for user {user_id} "
                f"(ip={ip or '?'}, live env applied)")

    # Plaintext returned ONCE — UI must persuade the user to copy.
    return {
        "ok":              True,
        "encryption_available": is_encryption_available(),
        "summary":         _row_summary(row),
        "plaintext_once":  triplet,
        "warning":         ("These values are shown ONCE. Save them now "
                            "to a password manager — AUREM will never "
                            "reveal them again."),
    }


@dev_router.get("/status")
async def my_keys_status(user=Depends(require_auth)) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db_unavailable")
    user_id = user.get("user_id") or user.get("id") or user.get("email")
    if not user_id:
        raise HTTPException(401, "user_id_unavailable")
    row = await _db.customer_security_keys.find_one(
        {"user_id": user_id, "status": "active"}, {"_id": 0},
    )
    return {"configured": bool(row), "current": _row_summary(row)}


# ── Admin endpoints ────────────────────────────────────────────────

@admin_router.get("")
async def admin_list_security_keys() -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db_unavailable")
    cur = _db.customer_security_keys.find({}, {"_id": 0})
    rows = await cur.sort("generated_at", -1).to_list(length=500)
    by_user: dict[str, dict] = {}
    for r in rows:
        uid = r.get("user_id")
        if not uid:
            continue
        if uid not in by_user or r.get("status") == "active":
            by_user[uid] = r
    summaries = [_row_summary(r) for r in by_user.values()]
    summaries.sort(key=lambda s: s.get("generated_at") or "", reverse=True)
    n_active  = sum(1 for s in summaries if s.get("status") == "active")
    n_rotated = sum(1 for s in summaries if s.get("status") == "rotated")
    return {
        "total":   len(summaries),
        "active":  n_active,
        "rotated": n_rotated,
        "items":   summaries,
    }


@admin_router.get("/{user_id}/history")
async def admin_history(user_id: str) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db_unavailable")
    cur = _db.customer_security_keys.find({"user_id": user_id}, {"_id": 0})
    rows = await cur.sort("generated_at", -1).to_list(length=100)
    return {"user_id": user_id, "items": [_row_summary(r) for r in rows]}


class AdminRotateBody(BaseModel):
    reason: str = ""


@admin_router.post("/{user_id}/rotate")
async def admin_force_rotate(
    user_id: str, body: AdminRotateBody = AdminRotateBody(),
    request: Request = None,
) -> dict[str, Any]:
    """Force-rotate a customer's keys. The customer must re-fetch the
    plaintext from their own /developers/security/generate-keys call
    next time they log in — we DO NOT return the new plaintext via
    the admin path."""
    if _db is None:
        raise HTTPException(503, "db_unavailable")
    target = await _db.customer_security_keys.find_one(
        {"user_id": user_id}, {"_id": 0},
    )
    if not target:
        raise HTTPException(404, "user_has_no_keys")

    # Mark all prior rows rotated and insert a fresh active row. We do
    # NOT apply this triplet to os.environ — those env vars belong to
    # the customer's tenant, not the admin's running process.
    await _db.customer_security_keys.update_many(
        {"user_id": user_id, "status": "active"},
        {"$set": {"status": "rotated", "rotated_at": _now().isoformat()}},
    )
    triplet = _generate_triplet()
    keys_doc = {}
    for name, value in triplet.items():
        keys_doc[name] = {
            "ct_envelope": encrypt_credentials({"value": value}),
            "key_tail":    _tail4(value),
        }
    ip = ""
    try:
        if request and request.client:
            ip = request.client.host or ""
    except Exception:
        pass
    row = {
        "user_id":      user_id,
        "email":        target.get("email", ""),
        "tenant_id":    target.get("tenant_id", "default"),
        "generated_at": _now().isoformat(),
        "ip_address":   ip,
        "status":       "active",
        "rotated_by_admin": True,
        "rotation_reason":  body.reason[:200],
        "keys":         keys_doc,
    }
    await _db.customer_security_keys.insert_one(dict(row))
    logger.info(f"[security-keys] admin force-rotated user_id={user_id}")
    return {"ok": True, "summary": _row_summary(row)}
