"""
routers/platform_secrets_router.py — iter D-43

Founder-controlled UI for managing AUREM platform environment secrets
WITHOUT touching the Emergent / Kubernetes dashboard. Used by the new
`/developers/settings` page.

Why this exists
---------------
The Admin Integrations Health page (D-38) made it obvious that 9 keys
were unset in preview. Asking the founder to SSH or open the Emergent
deploy panel every time they need to add a key for SendGrid / Anthropic
/ etc. is friction. With this router, the founder pastes the key in the
AUREM UI, we AES-256 (Fernet via `services.credential_crypto`) it,
store the ciphertext in `platform_secrets`, AND apply the plaintext to
`os.environ` so every existing code path that reads from env picks it
up immediately — no restart needed.

Security model
--------------
- Founder-only (`require_admin`).
- A strict whitelist of allowed secret names — prevents the UI from
  becoming a way to inject arbitrary env vars (e.g. `PATH`, `LD_PRELOAD`).
- AES-128-CBC + HMAC-SHA256 via Fernet at rest.
- We NEVER return the plaintext value. The list endpoint returns only
  `{name, has_value, key_tail (last 4 chars), updated_at}`.

On boot
-------
`apply_platform_secrets_to_env()` is called once at startup (wired in
`server.py`) so DB-stored keys override any stale `.env` values.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.credential_crypto import (
    decrypt_credentials, encrypt_credentials, is_encryption_available,
)
from utils.require_auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/developers/settings",
    tags=["developer-settings"],
    dependencies=[Depends(require_admin)],
)

_db = None


def set_db(database):
    global _db
    _db = database


# ── Whitelist of allowed secret names ───────────────────────────────
# Aligned with the 17 integrations on /admin/integrations (D-38). Add
# new names here as integrations are added. We refuse to set anything
# not on this list to keep this endpoint from becoming a generic
# environment-poisoning surface.

_ALLOWED_SECRETS = {
    # LLM providers
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "EMERGENT_LLM_KEY",
    # Comms
    "RESEND_API_KEY",
    "SENDGRID_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "WHAPI_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    # Payment / data
    "STRIPE_SECRET_KEY",
    "TAVILY_API_KEY",
    "SCRAPINGBEE_API_KEY",
    "LINKEDIN_ACCESS_TOKEN",
    # Infra
    "HETZNER_API_TOKEN",
    "CLOUDFLARE_API_TOKEN",
    "GITHUB_BOT_PAT",
    # GitHub OAuth (added D-42)
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "GITHUB_OAUTH_REDIRECT_URI",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tail4(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip()
    return s[-4:] if len(s) >= 4 else "*" * len(s)


# ── Models ───────────────────────────────────────────────────────────

class SecretSaveBody(BaseModel):
    value: str = Field(..., min_length=1, max_length=4096)


class SecretRow(BaseModel):
    name: str
    has_value: bool
    key_tail: str
    updated_at: str | None = None
    source: str  # "db" or "env" or "unset"


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/secrets")
async def list_secrets() -> dict[str, Any]:
    """List every whitelisted secret with its current status — no
    plaintext is ever returned, only `key_tail` (last 4 chars)."""
    rows: list[dict[str, Any]] = []
    if _db is not None:
        db_rows = await _db.platform_secrets.find(
            {}, {"_id": 0, "name": 1, "ct_envelope": 1, "updated_at": 1},
        ).to_list(length=200)
    else:
        db_rows = []
    db_map = {r["name"]: r for r in db_rows}

    for name in sorted(_ALLOWED_SECRETS):
        env_val = (os.environ.get(name) or "").strip()
        db_row  = db_map.get(name)
        plain   = None
        source  = "unset"
        if db_row:
            plain = decrypt_credentials(db_row.get("ct_envelope"))
            if isinstance(plain, dict):
                plain = plain.get("value")
            if plain:
                source = "db"
        elif env_val:
            plain  = env_val
            source = "env"

        rows.append({
            "name":       name,
            "has_value":  bool(plain),
            "key_tail":   _tail4(plain or env_val or ""),
            "updated_at": (db_row or {}).get("updated_at"),
            "source":     source,
        })

    return {
        "encryption_available": is_encryption_available(),
        "total":                len(rows),
        "items":                rows,
    }


@router.put("/secrets/{name}")
async def save_secret(name: str, body: SecretSaveBody) -> dict[str, Any]:
    """Encrypt and persist a secret, then apply it to os.environ so
    every existing code path picks it up immediately."""
    if name not in _ALLOWED_SECRETS:
        raise HTTPException(400, f"secret '{name}' is not on the allow-list")
    if _db is None:
        raise HTTPException(503, "db_unavailable")

    value = body.value.strip()
    if not value:
        raise HTTPException(400, "empty_value")

    envelope = encrypt_credentials({"value": value})
    await _db.platform_secrets.update_one(
        {"name": name},
        {"$set": {
            "name":         name,
            "ct_envelope":  envelope,
            "updated_at":   _now(),
        }},
        upsert=True,
    )
    # Apply live so the running backend can use the new key without
    # restart.
    os.environ[name] = value
    logger.info(f"[platform-secrets] saved {name} (live env applied)")
    return {"ok": True, "name": name, "key_tail": _tail4(value)}


@router.delete("/secrets/{name}")
async def delete_secret(name: str) -> dict[str, Any]:
    if name not in _ALLOWED_SECRETS:
        raise HTTPException(400, "not_allowed")
    if _db is None:
        return {"ok": True, "deleted": 0}
    res = await _db.platform_secrets.delete_one({"name": name})
    # Also clear from live env so the change is immediate.
    os.environ.pop(name, None)
    return {"ok": True, "deleted": res.deleted_count}


# ── Startup helper ──────────────────────────────────────────────────

async def apply_platform_secrets_to_env() -> int:
    """Load every DB-stored secret into os.environ.

    Called once during FastAPI startup. DB rows OVERRIDE any value
    already present in the environment, so the founder can supersede
    a stale .env entry by saving a new value on /developers/settings.
    Returns the number of keys applied (for boot logging).
    """
    if _db is None:
        return 0
    try:
        rows = await _db.platform_secrets.find(
            {}, {"_id": 0, "name": 1, "ct_envelope": 1},
        ).to_list(length=500)
    except Exception as e:
        logger.warning(f"[platform-secrets] startup load failed: {e}")
        return 0
    n = 0
    for r in rows:
        name = r.get("name")
        if not name or name not in _ALLOWED_SECRETS:
            continue
        plain = decrypt_credentials(r.get("ct_envelope"))
        if isinstance(plain, dict):
            plain = plain.get("value")
        if plain:
            os.environ[name] = plain
            n += 1
    if n:
        logger.info(f"[platform-secrets] applied {n} DB-stored secrets to env")
    return n
