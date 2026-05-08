"""
AUREM Secret Vault Router
BYON Compliance — AES-256-GCM encrypted secret management for tenant API keys
"""
import logging
import os
import uuid
import json
import base64
from datetime import datetime, timezone
from typing import Optional, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

router = APIRouter(prefix="/api/vault", tags=["AUREM Vault"])
logger = logging.getLogger(__name__)

_db = None

def set_db(db):
    global _db
    _db = db

def get_db():
    if _db is None:
        raise HTTPException(500, "Database not initialized")
    return _db


ENCRYPTION_KEY = os.environ.get("AUREM_ENCRYPTION_KEY", "aurem32characterencryptionkey!")

def _get_aes_key():
    """Derive a 32-byte key from the encryption key."""
    key_bytes = ENCRYPTION_KEY.encode("utf-8")
    if len(key_bytes) < 32:
        key_bytes = key_bytes.ljust(32, b'\0')
    return key_bytes[:32]


def _encrypt(plaintext: str) -> str:
    """Encrypt with AES-256-GCM, return base64-encoded nonce+ciphertext."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def _decrypt(encrypted_b64: str) -> str:
    """Decrypt AES-256-GCM from base64-encoded nonce+ciphertext."""
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    raw = base64.b64decode(encrypted_b64)
    nonce = raw[:12]
    ciphertext = raw[12:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


def _mask_value(value: str) -> str:
    """Mask a secret value showing first 4 and last 4 chars."""
    if len(value) <= 8:
        return "••••••••"
    return value[:4] + "••••••••" + value[-4:]


def _get_user_from_token(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = auth_header.split(" ", 1)[1]
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET", "")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(401, "Invalid token")


class StoreSecretRequest(BaseModel):
    name: str
    provider: str
    credentials: Dict[str, str]


@router.get("/secrets")
async def list_secrets(request: Request):
    """List all secrets for the user (with masked values)."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    secrets = []
    cursor = db.secret_vault.find({"user_id": user_id}, {"_id": 0})
    async for doc in cursor:
        # Return masked credentials
        masked = {}
        encrypted_creds = doc.get("encrypted_credentials", {})
        for key in encrypted_creds:
            try:
                decrypted = _decrypt(encrypted_creds[key])
                masked[key] = _mask_value(decrypted)
            except Exception:
                masked[key] = "••••••••"

        secrets.append({
            "id": doc.get("id"),
            "name": doc.get("name"),
            "provider": doc.get("provider"),
            "masked": masked,
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at")
        })

    return {"secrets": secrets}


@router.post("/secrets")
async def store_secret(data: StoreSecretRequest, request: Request):
    """Store encrypted credentials."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    # Encrypt each credential field
    encrypted_creds = {}
    for key, value in data.credentials.items():
        if value:
            encrypted_creds[key] = _encrypt(value)

    secret_id = f"sec-{uuid.uuid4().hex[:12]}"
    doc = {
        "id": secret_id,
        "user_id": user_id,
        "name": data.name,
        "provider": data.provider,
        "encrypted_credentials": encrypted_creds,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.secret_vault.insert_one(doc)

    return {"success": True, "id": secret_id}


@router.get("/secrets/{secret_id}/reveal")
async def reveal_secret(secret_id: str, request: Request):
    """Reveal decrypted credentials (audit logged)."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    doc = await db.secret_vault.find_one(
        {"id": secret_id, "user_id": user_id},
        {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Secret not found")

    # Decrypt
    credentials = {}
    for key, encrypted_value in doc.get("encrypted_credentials", {}).items():
        try:
            credentials[key] = _decrypt(encrypted_value)
        except Exception:
            credentials[key] = "[DECRYPTION_ERROR]"

    # Audit log
    await db.vault_audit_log.insert_one({
        "user_id": user_id,
        "secret_id": secret_id,
        "action": "reveal",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"credentials": credentials}


@router.delete("/secrets/{secret_id}")
async def delete_secret(secret_id: str, request: Request):
    """Delete a stored secret."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    result = await db.secret_vault.delete_one(
        {"id": secret_id, "user_id": user_id}
    )

    # Audit log
    await db.vault_audit_log.insert_one({
        "user_id": user_id,
        "secret_id": secret_id,
        "action": "delete",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"success": True, "deleted": result.deleted_count > 0}


# ═══════════════════════════════════════════════════════════════
# KEY ROTATION
# ═══════════════════════════════════════════════════════════════

class RotateSecretRequest(BaseModel):
    credentials: Dict[str, str]


@router.post("/secrets/{secret_id}/test")
async def test_secret(secret_id: str, request: Request):
    """Live-validate a stored credential against the provider's API.

    Returns `{ok, provider, status_code, detail, tested_at}`. Each provider
    has a minimal auth-probing endpoint (e.g. Stripe /v1/balance, Twilio
    /Accounts.json, OpenAI /v1/models, Apollo /v1/auth/health). Secrets
    that don't expose a probe endpoint fall through as `supported: false`
    but the row is still decryptable.
    """
    import httpx
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    doc = await db.secret_vault.find_one({"id": secret_id, "user_id": user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Secret not found")

    provider = (doc.get("provider") or "").lower()
    enc = doc.get("encrypted_credentials", {}) or {}
    creds: Dict[str, str] = {}
    for k, v in enc.items():
        try:
            creds[k] = _decrypt(v)
        except Exception:
            creds[k] = ""

    started = datetime.now(timezone.utc)
    result = {"ok": False, "provider": provider, "supported": True, "status_code": None, "detail": None}

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            if provider == "stripe":
                key = creds.get("api_key") or creds.get("secret_key")
                r = await client.get("https://api.stripe.com/v1/balance", auth=(key, ""))
                result.update(status_code=r.status_code, ok=r.status_code == 200,
                              detail="Balance retrieved" if r.status_code == 200 else r.json().get("error", {}).get("message", "auth failed"))
            elif provider == "twilio":
                sid = creds.get("account_sid") or creds.get("sid")
                tok = creds.get("auth_token") or creds.get("token")
                r = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json", auth=(sid, tok))
                result.update(status_code=r.status_code, ok=r.status_code == 200,
                              detail="Account reachable" if r.status_code == 200 else "auth failed")
            elif provider in ("whatsapp", "whatsapp_business", "whapi"):
                tok = creds.get("api_token") or creds.get("token") or creds.get("access_token")
                # Try WHAPI first, fall back to Meta
                r = await client.get("https://gate.whapi.cloud/health", headers={"Authorization": f"Bearer {tok}"})
                result.update(status_code=r.status_code, ok=r.status_code < 400,
                              detail=f"WHAPI health: {r.status_code}")
            elif provider == "openai":
                key = creds.get("api_key")
                r = await client.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"})
                result.update(status_code=r.status_code, ok=r.status_code == 200,
                              detail=f"{len((r.json() or {}).get('data', []))} models" if r.status_code == 200 else "auth failed")
            elif provider in ("apollo", "apollo.io"):
                key = creds.get("api_key")
                r = await client.post("https://api.apollo.io/v1/auth/health", json={"api_key": key})
                result.update(status_code=r.status_code, ok=r.status_code == 200, detail="Apollo reachable")
            elif provider == "hubspot":
                tok = creds.get("access_token") or creds.get("api_key")
                r = await client.get("https://api.hubapi.com/account-info/v3/details", headers={"Authorization": f"Bearer {tok}"})
                result.update(status_code=r.status_code, ok=r.status_code == 200, detail="Account reachable")
            elif provider == "salesforce":
                inst = creds.get("instance_url") or creds.get("base_url")
                tok = creds.get("access_token")
                if inst and tok:
                    r = await client.get(f"{inst.rstrip('/')}/services/data/", headers={"Authorization": f"Bearer {tok}"})
                    result.update(status_code=r.status_code, ok=r.status_code == 200, detail="API versions reachable")
                else:
                    result.update(supported=False, detail="Need instance_url + access_token")
            elif provider in ("coinbase", "coinbase_commerce"):
                key = creds.get("api_key")
                r = await client.get("https://api.commerce.coinbase.com/charges?limit=1",
                                     headers={"X-CC-Api-Key": key, "X-CC-Version": "2018-03-22"})
                result.update(status_code=r.status_code, ok=r.status_code == 200, detail="Charges endpoint reachable")
            else:
                # Custom API or unrecognised provider — just check we can decrypt.
                any_cred = any(v for v in creds.values())
                result.update(supported=False, ok=any_cred,
                              detail="Credentials decryptable" if any_cred else "Credentials empty or corrupted")
    except httpx.RequestError as e:
        result["detail"] = f"Network: {str(e)[:200]}"
    except Exception as e:
        result["detail"] = f"Error: {str(e)[:200]}"

    finished = datetime.now(timezone.utc)
    result["tested_at"] = finished.isoformat()
    result["duration_ms"] = int((finished - started).total_seconds() * 1000)

    # Persist last test result on the secret + audit log
    try:
        await db.secret_vault.update_one(
            {"id": secret_id, "user_id": user_id},
            {"$set": {"last_test_result": result, "last_tested_at": finished.isoformat()}},
        )
        await db.vault_audit_log.insert_one({
            "user_id": user_id,
            "secret_id": secret_id,
            "action": "test",
            "provider": provider,
            "ok": result["ok"],
            "status_code": result["status_code"],
            "timestamp": finished.isoformat(),
        })
    except Exception:
        pass

    return result


@router.post("/secrets/{secret_id}/rotate")
async def rotate_secret(secret_id: str, data: RotateSecretRequest, request: Request):
    """Rotate (re-encrypt) a secret with new credential values."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    doc = await db.secret_vault.find_one(
        {"id": secret_id, "user_id": user_id},
        {"_id": 0}
    )
    if not doc:
        raise HTTPException(404, "Secret not found")

    # Encrypt new credentials
    new_encrypted = {}
    for key, value in data.credentials.items():
        if value:
            new_encrypted[key] = _encrypt(value)

    # Update in DB
    now = datetime.now(timezone.utc).isoformat()
    prev_rotation = doc.get("last_rotated_at")
    rotation_count = doc.get("rotation_count", 0) + 1

    await db.secret_vault.update_one(
        {"id": secret_id, "user_id": user_id},
        {"$set": {
            "encrypted_credentials": new_encrypted,
            "updated_at": now,
            "last_rotated_at": now,
            "rotation_count": rotation_count,
            "previous_rotation_at": prev_rotation,
        }}
    )

    # Audit log
    await db.vault_audit_log.insert_one({
        "user_id": user_id,
        "secret_id": secret_id,
        "action": "rotate",
        "rotation_count": rotation_count,
        "timestamp": now,
    })

    return {
        "success": True,
        "rotated_at": now,
        "rotation_count": rotation_count,
    }


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════

@router.get("/audit")
async def list_audit_log(request: Request, limit: int = 50, skip: int = 0):
    """List audit trail for the user's vault operations."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    cursor = db.vault_audit_log.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("timestamp", -1).skip(skip).limit(limit)

    entries = []
    async for doc in cursor:
        entries.append(doc)

    total = await db.vault_audit_log.count_documents({"user_id": user_id})

    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "skip": skip,
    }


@router.get("/audit/summary")
async def audit_summary(request: Request):
    """Summarized vault audit: action counts, last activity, rotation stats."""
    user_data = _get_user_from_token(request)
    user_id = user_data.get("user_id")
    db = get_db()

    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$action",
            "count": {"$sum": 1},
            "last": {"$max": "$timestamp"},
        }}
    ]
    action_stats = {}
    async for doc in db.vault_audit_log.aggregate(pipeline):
        action_stats[doc["_id"]] = {"count": doc["count"], "last": doc["last"]}

    # Secrets with rotation info
    secrets_cursor = db.secret_vault.find(
        {"user_id": user_id},
        {"_id": 0, "id": 1, "name": 1, "provider": 1, "rotation_count": 1, "last_rotated_at": 1, "created_at": 1}
    )
    rotation_info = []
    async for doc in secrets_cursor:
        rotation_info.append({
            "id": doc.get("id"),
            "name": doc.get("name"),
            "provider": doc.get("provider"),
            "rotation_count": doc.get("rotation_count", 0),
            "last_rotated_at": doc.get("last_rotated_at"),
            "created_at": doc.get("created_at"),
        })

    return {
        "action_stats": action_stats,
        "rotation_info": rotation_info,
        "total_events": sum(s["count"] for s in action_stats.values()),
    }
