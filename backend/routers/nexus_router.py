"""
AUREM Nexus — Hybrid Integration Hub

Provides OAuth 2.0 "Connect" for services that support it (Google, GitHub, Stripe)
and encrypted API key vault for all other services. Unified connector status API.
"""

import os
import uuid
import base64
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/nexus", tags=["Nexus Connectors"])

_db = None

def set_db(database):
    global _db
    _db = database


ENCRYPTION_KEY = os.environ.get("AUREM_ENCRYPTION_KEY", "aurem32characterencryptionkey!")


def _aes_key():
    k = ENCRYPTION_KEY.encode("utf-8")
    return (k.ljust(32, b"\0"))[:32]


def _encrypt(text: str) -> str:
    aesgcm = AESGCM(_aes_key())
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, text.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("utf-8")


def _decrypt(blob: str) -> str:
    aesgcm = AESGCM(_aes_key())
    raw = base64.b64decode(blob)
    return aesgcm.decrypt(raw[:12], raw[12:], None).decode("utf-8")


def _mask(val: str) -> str:
    if len(val) <= 8:
        return "********"
    return val[:4] + "********" + val[-4:]


def _get_user(request: Request):
    import jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        return jwt.decode(auth.split(" ", 1)[1], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


# ═══════════════════════════════════════════════════════════════
# CONNECTOR DEFINITIONS
# ═══════════════════════════════════════════════════════════════
CONNECTORS = [
    # OAuth providers
    {"id": "google",    "name": "Google (Gmail / Calendar)", "icon": "mail",        "method": "oauth",   "category": "Communication", "description": "Connect Gmail, Calendar, and Google Workspace."},
    {"id": "github",    "name": "GitHub",                    "icon": "github",      "method": "oauth",   "category": "Developer",     "description": "Connect repositories, issues, and CI/CD."},
    {"id": "stripe",    "name": "Stripe Payments",           "icon": "credit-card", "method": "oauth",   "category": "Payments",      "description": "Accept payments, manage subscriptions."},

    # API Key providers
    {"id": "twilio",        "name": "Twilio SMS",            "icon": "phone",          "method": "api_key", "category": "Communication", "description": "Send SMS, voice calls, and WhatsApp.","fields": ["account_sid", "auth_token"]},
    {"id": "sendgrid",      "name": "SendGrid",              "icon": "send",           "method": "api_key", "category": "Communication", "description": "Transactional and marketing email.","fields": ["api_key"]},
    {"id": "resend",        "name": "Resend Email",          "icon": "mail",           "method": "api_key", "category": "Communication", "description": "Developer-first email API.","fields": ["api_key"]},
    {"id": "whapi",         "name": "Whapi.cloud",           "icon": "message-circle", "method": "api_key", "category": "Communication", "description": "WhatsApp Business automation.","fields": ["api_token"]},
    {"id": "meta_whatsapp", "name": "Meta WhatsApp",         "icon": "message-circle", "method": "api_key", "category": "Communication", "description": "Official Meta WhatsApp Business API.","fields": ["app_secret", "phone_number_id", "access_token"]},
    {"id": "aurem_voice",   "name": "AUREM DIY Voice",       "icon": "mic",            "method": "api_key", "category": "Voice",         "description": "AUREM built-in voice-to-voice AI engine.","fields": ["emergent_llm_key"]},
    {"id": "openrouter",    "name": "OpenRouter",            "icon": "cpu",            "method": "api_key", "category": "AI / ML",       "description": "Multi-model AI routing gateway.","fields": ["api_key"]},
    {"id": "anthropic",     "name": "Anthropic Claude",      "icon": "brain",          "method": "api_key", "category": "AI / ML",       "description": "Claude AI for reasoning and analysis.","fields": ["api_key"]},
    {"id": "cloudinary",    "name": "Cloudinary",            "icon": "image",          "method": "api_key", "category": "Media",         "description": "Image and video management.","fields": ["cloud_name", "api_key", "api_secret"]},
    {"id": "brave_search",  "name": "Brave Search",          "icon": "search",         "method": "api_key", "category": "Search",        "description": "Privacy-focused web search API.","fields": ["api_key"]},
    {"id": "exa_search",    "name": "EXA Search",            "icon": "search",         "method": "api_key", "category": "Search",        "description": "Neural search engine for content.","fields": ["api_key"]},
    {"id": "openweather",   "name": "OpenWeatherMap",        "icon": "cloud",          "method": "api_key", "category": "Data",          "description": "Weather data API.","fields": ["api_key"]},
    {"id": "omnidimension", "name": "OmniDimension 3D",      "icon": "box",            "method": "api_key", "category": "AI / ML",       "description": "3D model generation and rendering.","fields": ["api_key"]},
    {"id": "elevenlabs",    "name": "ElevenLabs",            "icon": "volume-2",       "method": "api_key", "category": "Voice",         "description": "AI voice synthesis and cloning.","fields": ["api_key"]},
]


# ═══════════════════════════════════════════════════════════════
# LIST ALL CONNECTORS + STATUS
# ═══════════════════════════════════════════════════════════════
@router.get("/connectors")
async def list_connectors(request: Request):
    """Returns all connectors with their connection status for the current user."""
    user = _get_user(request)
    user_id = user.get("user_id", "")

    if _db is None:
        raise HTTPException(500, "Database not available")

    # Fetch stored credentials for this user
    stored = {}
    async for doc in _db.nexus_credentials.find(
        {"user_id": user_id}, {"_id": 0, "encrypted_data": 0}
    ):
        stored[doc["connector_id"]] = doc

    result = []
    for c in CONNECTORS:
        cred = stored.get(c["id"])
        status = "not_connected"
        connected_at = None
        if cred:
            status = cred.get("status", "connected")
            connected_at = cred.get("connected_at")

        result.append({
            "id": c["id"],
            "name": c["name"],
            "icon": c["icon"],
            "method": c["method"],
            "category": c["category"],
            "description": c["description"],
            "fields": c.get("fields", []),
            "status": status,
            "connected_at": connected_at,
        })

    return {"connectors": result}


# ═══════════════════════════════════════════════════════════════
# CONNECT VIA API KEY (Encrypted Vault)
# ═══════════════════════════════════════════════════════════════
class ConnectKeyRequest(BaseModel):
    connector_id: str
    credentials: dict  # e.g. {"api_key": "sk_...", "account_sid": "..."}


@router.post("/connect/key")
async def connect_via_key(body: ConnectKeyRequest, request: Request):
    """Store encrypted API key credentials for a connector."""
    user = _get_user(request)
    user_id = user.get("user_id", "")
    tenant_id = user.get("tenant_id", user_id)

    if _db is None:
        raise HTTPException(500, "Database not available")

    # Validate connector exists and is api_key type
    connector = next((c for c in CONNECTORS if c["id"] == body.connector_id), None)
    if not connector:
        raise HTTPException(404, f"Connector '{body.connector_id}' not found")
    if connector["method"] != "api_key":
        raise HTTPException(400, f"Connector '{body.connector_id}' uses OAuth, not API key")

    # Encrypt the credentials
    encrypted = _encrypt(str(body.credentials))

    # Create masked preview
    masked = {k: _mask(v) for k, v in body.credentials.items()}

    doc = {
        "id": f"nexus_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "tenant_id": tenant_id,
        "connector_id": body.connector_id,
        "method": "api_key",
        "encrypted_data": encrypted,
        "masked_preview": masked,
        "status": "connected",
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Upsert (replace if exists)
    await _db.nexus_credentials.update_one(
        {"user_id": user_id, "connector_id": body.connector_id},
        {"$set": doc},
        upsert=True,
    )

    return {
        "success": True,
        "connector_id": body.connector_id,
        "status": "connected",
        "masked": masked,
    }


# ═══════════════════════════════════════════════════════════════
# DISCONNECT A CONNECTOR
# ═══════════════════════════════════════════════════════════════
@router.delete("/disconnect/{connector_id}")
async def disconnect_connector(connector_id: str, request: Request):
    """Remove stored credentials for a connector."""
    user = _get_user(request)
    user_id = user.get("user_id", "")

    if _db is None:
        raise HTTPException(500, "Database not available")

    result = await _db.nexus_credentials.delete_one(
        {"user_id": user_id, "connector_id": connector_id}
    )

    return {
        "success": True,
        "deleted": result.deleted_count > 0,
        "connector_id": connector_id,
    }


# ═══════════════════════════════════════════════════════════════
# GET DECRYPTED CREDENTIALS (internal use / admin)
# ═══════════════════════════════════════════════════════════════
@router.get("/credentials/{connector_id}")
async def get_credentials(connector_id: str, request: Request):
    """Get masked credential preview for a connector."""
    user = _get_user(request)
    user_id = user.get("user_id", "")

    if _db is None:
        raise HTTPException(500, "Database not available")

    doc = await _db.nexus_credentials.find_one(
        {"user_id": user_id, "connector_id": connector_id},
        {"_id": 0, "encrypted_data": 0},
    )

    if not doc:
        raise HTTPException(404, "No credentials stored")

    return doc


# ═══════════════════════════════════════════════════════════════
# OAUTH INITIATE (placeholder — full OAuth requires redirect URIs)
# ═══════════════════════════════════════════════════════════════
@router.get("/oauth/{provider}/initiate")
async def oauth_initiate(provider: str, request: Request):
    """
    Returns the OAuth authorization URL for the given provider.
    The frontend opens this in a popup window.
    """
    user = _get_user(request)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", request.base_url)

    if provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        if not client_id:
            raise HTTPException(
                400,
                "Google OAuth not configured. Add GOOGLE_CLIENT_ID to environment.",
            )
        redirect_uri = f"{base_url}/api/nexus/oauth/google/callback"
        scopes = "openid email profile https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.readonly"
        url = (
            f"https://accounts.google.com/o/oauth2/v2/auth"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes}"
            f"&access_type=offline"
            f"&prompt=consent"
            f"&state={user.get('user_id', '')}"
        )
        return {"auth_url": url, "provider": "google"}

    elif provider == "github":
        client_id = os.environ.get("GITHUB_CLIENT_ID", "")
        if not client_id:
            raise HTTPException(
                400,
                "GitHub OAuth not configured. Add GITHUB_CLIENT_ID to environment.",
            )
        redirect_uri = f"{base_url}/api/nexus/oauth/github/callback"
        url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=repo,user,read:org"
            f"&state={user.get('user_id', '')}"
        )
        return {"auth_url": url, "provider": "github"}

    elif provider == "stripe":
        client_id = os.environ.get("STRIPE_CONNECT_CLIENT_ID", "")
        if not client_id:
            raise HTTPException(
                400,
                "Stripe Connect not configured. Add STRIPE_CONNECT_CLIENT_ID to environment.",
            )
        redirect_uri = f"{base_url}/api/nexus/oauth/stripe/callback"
        url = (
            f"https://connect.stripe.com/oauth/authorize"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&scope=read_write"
            f"&redirect_uri={redirect_uri}"
            f"&state={user.get('user_id', '')}"
        )
        return {"auth_url": url, "provider": "stripe"}

    raise HTTPException(400, f"OAuth not supported for '{provider}'")


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str = "", state: str = ""):
    """
    OAuth callback handler. Exchanges auth code for tokens and stores them.
    In production, this redirects back to the frontend with a success indicator.
    """
    if not code:
        raise HTTPException(400, "Missing authorization code")

    if _db is None:
        raise HTTPException(500, "Database not available")

    # The state param carries the user_id
    user_id = state
    if not user_id:
        raise HTTPException(400, "Missing state (user_id)")

    # Store the OAuth grant (in production, exchange code for tokens here)
    doc = {
        "id": f"nexus_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "tenant_id": user_id,
        "connector_id": provider,
        "method": "oauth",
        "oauth_code": _encrypt(code),
        "status": "connected",
        "connected_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    await _db.nexus_credentials.update_one(
        {"user_id": user_id, "connector_id": provider},
        {"$set": doc},
        upsert=True,
    )

    # Redirect back to frontend Nexus page
    frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "")
    return {"success": True, "provider": provider, "redirect": f"{frontend_url}/dashboard?nexus=connected&provider={provider}"}
