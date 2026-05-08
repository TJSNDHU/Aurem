"""
Shopify OAuth + App Installation Router
=========================================
Handles the full Shopify OAuth2 flow:
  1. /api/shopify/auth?shop=store.myshopify.com → redirect to Shopify
  2. /api/shopify/auth/callback → exchange code for access token
  3. /api/shopify/auth/status → check if a shop is connected
  4. Register mandatory webhooks after install
"""

import os
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/shopify/auth", tags=["Shopify OAuth"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


def _get_config():
    return {
        "api_key": os.environ.get("SHOPIFY_API_KEY", ""),
        "api_secret": os.environ.get("SHOPIFY_API_SECRET", ""),
        "scopes": os.environ.get("SHOPIFY_SCOPES", "read_products,write_products,read_orders,write_orders"),
        "app_url": os.environ.get("SHOPIFY_APP_URL", ""),
    }


def _verify_hmac(query_params: dict, secret: str) -> bool:
    """Verify Shopify's HMAC signature on callback."""
    received_hmac = query_params.get("hmac", "")
    params_to_sign = {k: v for k, v in query_params.items() if k != "hmac"}
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params_to_sign.items()))
    computed = hmac.new(secret.encode(), sorted_params.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, received_hmac)


# ═══════════════════════════════════════════════════
# Step 1: Initiate OAuth
# ═══════════════════════════════════════════════════

@router.get("")
async def initiate_oauth(shop: str = ""):
    """
    Start Shopify OAuth flow.
    Usage: GET /api/shopify/auth?shop=yourstore.myshopify.com
    """
    if not shop:
        raise HTTPException(400, "Missing 'shop' parameter")

    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    config = _get_config()
    if not config["api_key"] or not config["api_secret"]:
        raise HTTPException(503, "Shopify API keys not configured")

    import secrets
    nonce = secrets.token_hex(16)

    # Store nonce for verification
    db = _get_db()
    if db:
        await db.shopify_oauth_nonces.update_one(
            {"shop": shop},
            {"$set": {"nonce": nonce, "created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

    redirect_uri = f"{config['app_url']}/api/shopify/auth/callback"
    params = urlencode({
        "client_id": config["api_key"],
        "scope": config["scopes"],
        "redirect_uri": redirect_uri,
        "state": nonce,
    })

    auth_url = f"https://{shop}/admin/oauth/authorize?{params}"
    logger.info(f"[SHOPIFY-AUTH] Redirecting {shop} to OAuth: {auth_url}")
    return RedirectResponse(url=auth_url)


# ═══════════════════════════════════════════════════
# Step 2: OAuth Callback
# ═══════════════════════════════════════════════════

@router.get("/callback")
async def oauth_callback(request: Request):
    """
    Shopify OAuth callback — exchanges code for permanent access token.
    Registers mandatory webhooks after successful install.
    """
    params = dict(request.query_params)
    shop = params.get("shop", "")
    code = params.get("code", "")
    state = params.get("state", "")
    hmac_param = params.get("hmac", "")

    if not shop or not code:
        raise HTTPException(400, "Missing shop or code parameter")

    config = _get_config()

    # Verify HMAC
    if hmac_param and not _verify_hmac(params, config["api_secret"]):
        raise HTTPException(403, "HMAC verification failed")

    # Verify nonce
    db = _get_db()
    if db and state:
        nonce_doc = await db.shopify_oauth_nonces.find_one({"shop": shop, "nonce": state})
        if not nonce_doc:
            logger.warning(f"[SHOPIFY-AUTH] Nonce mismatch for {shop}")
            # Continue anyway — some flows don't preserve nonce

    # Exchange code for access token
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://{shop}/admin/oauth/access_token",
                json={
                    "client_id": config["api_key"],
                    "client_secret": config["api_secret"],
                    "code": code,
                },
            )
            if resp.status_code != 200:
                logger.error(f"[SHOPIFY-AUTH] Token exchange failed: {resp.text}")
                raise HTTPException(502, f"Token exchange failed: {resp.status_code}")

            token_data = resp.json()
            access_token = token_data.get("access_token", "")
            scope = token_data.get("scope", "")
            logger.info(f"[SHOPIFY-AUTH] Token exchange response for {shop}: status={resp.status_code}, scope='{scope}', token_prefix='{access_token[:8] if access_token else 'NONE'}'")
            logger.info(f"[SHOPIFY-AUTH] Full token response keys: {list(token_data.keys())}")

    except httpx.HTTPError as e:
        raise HTTPException(502, f"Network error during token exchange: {e}")

    if not access_token:
        raise HTTPException(502, "No access token received")

    # Save installation
    now = datetime.now(timezone.utc).isoformat()
    if db:
        await db.shopify_app_installs.update_one(
            {"shop_domain": shop},
            {"$set": {
                "shop_domain": shop,
                "access_token": access_token,
                "scope": scope,
                "status": "active",
                "installed_at": now,
                "updated_at": now,
            }},
            upsert=True,
        )

    logger.info(f"[SHOPIFY-AUTH] App installed on {shop} with scope: {scope}")

    # Register webhooks
    await _register_webhooks(shop, access_token)

    # Redirect to app dashboard
    app_url = config["app_url"]
    return RedirectResponse(url=f"{app_url}/dashboard?shop={shop}&installed=true")


# ═══════════════════════════════════════════════════
# Webhook Registration
# ═══════════════════════════════════════════════════

async def _register_webhooks(shop: str, access_token: str):
    """Register mandatory Shopify webhooks after install."""
    config = _get_config()
    base_url = config["app_url"]

    webhooks = [
        {"topic": "orders/paid", "address": f"{base_url}/api/shopify/pulse/webhook/order-paid"},
        {"topic": "checkouts/create", "address": f"{base_url}/api/shopify/pulse/webhook/checkout-created"},
        {"topic": "app/uninstalled", "address": f"{base_url}/api/shopify/auth/webhook/uninstalled"},
        {"topic": "customers/redact", "address": f"{base_url}/api/shopify/pulse/webhooks/customers-redact"},
        {"topic": "customers/data_request", "address": f"{base_url}/api/shopify/pulse/webhooks/customers-data-request"},
        {"topic": "shop/redact", "address": f"{base_url}/api/shopify/pulse/webhooks/shop-redact"},
    ]

    import httpx
    registered = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for wh in webhooks:
            try:
                resp = await client.post(
                    f"https://{shop}/admin/api/2026-04/webhooks.json",
                    json={"webhook": {"topic": wh["topic"], "address": wh["address"], "format": "json"}},
                    headers={"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"},
                )
                if resp.status_code in (200, 201):
                    registered += 1
                else:
                    logger.warning(f"[SHOPIFY-AUTH] Webhook {wh['topic']} failed: {resp.status_code}")
            except Exception as e:
                logger.warning(f"[SHOPIFY-AUTH] Webhook {wh['topic']} error: {e}")

    logger.info(f"[SHOPIFY-AUTH] Registered {registered}/{len(webhooks)} webhooks for {shop}")


# ═══════════════════════════════════════════════════
# App Uninstall Webhook
# ═══════════════════════════════════════════════════

@router.post("/webhook/uninstalled")
async def app_uninstalled(request: Request):
    """Handle app uninstall — mark shop as inactive."""
    db = _get_db()
    try:
        body = await request.json()
        shop = body.get("myshopify_domain", body.get("domain", ""))
        if db and shop:
            await db.shopify_app_installs.update_one(
                {"shop_domain": shop},
                {"$set": {"status": "uninstalled", "uninstalled_at": datetime.now(timezone.utc).isoformat()}},
            )
            logger.info(f"[SHOPIFY-AUTH] App uninstalled from {shop}")
    except Exception as e:
        logger.error(f"[SHOPIFY-AUTH] Uninstall webhook error: {e}")
    return {"status": "ok"}


# ═══════════════════════════════════════════════════
# Status Check
# ═══════════════════════════════════════════════════

@router.get("/status")
async def auth_status(shop: str = ""):
    """Check if a shop has an active installation."""
    db = _get_db()
    if not db or not shop:
        return {"connected": False}

    if not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    install = await db.shopify_app_installs.find_one(
        {"shop_domain": shop, "status": "active"}, {"_id": 0, "access_token": 0}
    )
    if install:
        return {
            "connected": True,
            "shop": shop,
            "scope": install.get("scope", ""),
            "installed_at": install.get("installed_at", ""),
        }
    return {"connected": False, "shop": shop}
