# ============================================================
# AUREM AGENT RULES — READ ORA_MEMORY.md FIRST, ALWAYS
# 1. Read /app/ORA_MEMORY.md before any task — no exceptions
# 2. Minimum tokens. No verbose reasoning. No preamble.
# 3. Each tool once only. No redundant calls.
# 4. Stop when done. No post-task commentary.
# 5. No hallucination. Unknown = "unknown".
# 6. Never rewrite working code unless told.
# 7. After every task — update ORA_MEMORY.md with changes.
# 8. MODEL: claude-sonnet ONLY — never opus
# ============================================================
"""
AUREM AI Platform — Proprietary Software
Copyright (c) 2026 Polaris Built Inc.
All rights reserved. Unauthorized copying, distribution,
or use of this software is strictly prohibited.
Licensed under Polaris Built Inc. commercial license.
"""
import sys
import os
import logging as _logging_early
import asyncio as _asyncio
import warnings
print("[STARTUP] Python starting...", flush=True)

# Suppress HuggingFace Hub unauthenticated request warnings globally
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
# duckduckgo_search → ddgs rename — emits RuntimeWarning on every DDGS() call.
# Silence to keep deploy logs clean; library still functions correctly.
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")
# Leaked TCP transports from httpx AsyncClient during scheduled scans — cosmetic.
warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*TCPTransport.*")
_logging_early.getLogger("huggingface_hub").setLevel(_logging_early.ERROR)
_logging_early.getLogger("huggingface_hub.utils._http").setLevel(_logging_early.ERROR)

# ═══════════════════════════════════════════════════════════════════════════
# DEPLOY-NOISE SUPPRESSION (permanent, root-cause fixed)
# ═══════════════════════════════════════════════════════════════════════════
# These loggers spam the deploy log with warnings that are NOT bugs:
#
#   apscheduler.executors.default  "Run time was missed by Xs"
#       → fires during the 20-40s cold-start window when uvicorn is importing
#         1000+ modules and the event loop is temporarily busy. Job runs fine
#         once startup finishes. Not actionable. Silence at WARNING.
#
#   routers.ai_router               "OpenRouter 401 / 429 on <model>"
#   services.openrouter_client      "[OpenRouter] 401/429 ..."
#       → OpenRouter free-tier keys get rate-limited constantly. We already
#         have Emergent fallback + 1h cooldown. Repeated WARNING on every
#         retry is log-pollution. We log ONCE at startup via the probe below,
#         then go quiet for the rest of the process.
#
#   services.self_repair_loop       "[SelfRepair] Could not fetch <url>"
#       → Target sites (customer websites) can be slow or down. Already
#         gracefully degraded. Demoted to INFO.
_logging_early.getLogger("apscheduler.executors.default").setLevel(_logging_early.ERROR)
_logging_early.getLogger("apscheduler.scheduler").setLevel(_logging_early.ERROR)
_logging_early.getLogger("routers.ai_router").setLevel(_logging_early.ERROR)
_logging_early.getLogger("services.openrouter_client").setLevel(_logging_early.ERROR)
_logging_early.getLogger("services.self_repair_loop").setLevel(_logging_early.INFO)
_logging_early.getLogger("LiteLLM").setLevel(_logging_early.ERROR)
_logging_early.getLogger("litellm").setLevel(_logging_early.ERROR)
# auto_heal fires "Backend health check error: ''" during the first 10s of
# cold-boot when the probe URL is hitting the pod before it's routable.
_logging_early.getLogger("services.auto_heal").setLevel(_logging_early.ERROR)

# ───────────────────────────────────────────────────────────────────────
# iter 285 — K8s health-probe log suppression
#
# The ingress nginx proxy hammers /health every 1-2 s for liveness. During
# the 1-2 s window when supervisor is hot-reloading uvicorn (e.g., after a
# code change or deploy), nginx logs:
#   "nginx connect() failed (111: Connection refused) upstream"
# This is a TRANSIENT K8s artifact (not a real failure) — the backend is
# simply not listening yet. Once uvicorn rebinds port 8001 (~1-2 s), probes
# go green again. We can't silence nginx from our container, but we CAN
# stop flooding uvicorn's own access log with /health 200s — which keeps
# the signal-to-noise ratio high when grepping real errors.
class _HealthLogFilter(_logging_early.Filter):
    """Drop uvicorn access-log lines for liveness probes (/health, /api/health, /ready, /)
    and bot-flood targets (/api/sentinel/client-error, /api/sentinel/heartbeat)."""
    _SILENT_PATHS = (
        '"GET /health ', '"GET /api/health ',
        '"GET /ready ', '"GET / HTTP',
        '"HEAD /health ', '"HEAD /api/health ',
        # iter 282al-25 — bot/stale-client floods drown deploy logs and bury
        # real errors. Each request is already short-circuited by the ASGI
        # flood gate; suppressing the access log just removes the noise.
        '"POST /api/sentinel/client-error ',
        '"POST /api/sentinel/heartbeat ',
        '"GET /api/sentinel/heartbeat ',
    )
    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return True
        return not any(p in msg for p in self._SILENT_PATHS)

_logging_early.getLogger("uvicorn.access").addFilter(_HealthLogFilter())


def _safe_task(coro, name="unnamed"):
    """Wrap a coroutine so unhandled exceptions never crash uvicorn."""
    async def _wrapper():
        try:
            await coro
        except _asyncio.CancelledError:
            pass
        except BaseException as exc:
            import logging as _log
            _log.getLogger("safe_task").error(f"[SAFE_TASK] '{name}' crashed: {exc}")
    return _asyncio.create_task(_wrapper(), name=name)

from fastapi import (
    FastAPI,
    APIRouter,
    HTTPException,
    Request,
    Depends,
    UploadFile,
    File,
    Form,
    Response,
    Body,
    WebSocket,
    WebSocketDisconnect,
    Header,
)
print("[STARTUP] FastAPI imported", flush=True)

from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.gzip import GZipMiddleware
print("[STARTUP] FastAPI extras imported", flush=True)

from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response as StarletteResponse
print("[STARTUP] Starlette imported", flush=True)

from motor.motor_asyncio import AsyncIOMotorClient
print("[STARTUP] Motor imported", flush=True)

# RLS Security Module
from rls_security import (
    BrandID, AdminRole, AdminUser, RLSContext,
    BRAND_CONFIGS, get_brand_config, RLS_PROTECTED_COLLECTIONS,
    migrate_add_brand_id, create_indexes_for_rls
)
print("[STARTUP] RLS Security imported", flush=True)

import os
import logging
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict
import uuid
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import shutil
import re
import html
import time
import random
import secrets
import hashlib
from collections import defaultdict
print("[STARTUP] Standard libs imported", flush=True)

# Lazy imports for heavy modules - loaded on first use to speed up startup
_stripe_checkout = None
_llm_chat = None
_openai_image_gen = None
_openai_video_gen = None

def get_stripe_checkout():
    global _stripe_checkout
    if _stripe_checkout is None:
        from emergentintegrations.payments.stripe.checkout import (
            StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
        )
        _stripe_checkout = {
            'StripeCheckout': StripeCheckout,
            'CheckoutSessionResponse': CheckoutSessionResponse,
            'CheckoutStatusResponse': CheckoutStatusResponse,
            'CheckoutSessionRequest': CheckoutSessionRequest
        }
    return _stripe_checkout

def get_llm_chat():
    global _llm_chat
    if _llm_chat is None:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        _llm_chat = {'LlmChat': LlmChat, 'UserMessage': UserMessage}
    return _llm_chat

def get_openai_generators():
    global _openai_image_gen, _openai_video_gen
    if _openai_image_gen is None:
        from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration
        from emergentintegrations.llm.openai.video_generation import OpenAIVideoGeneration
        _openai_image_gen = OpenAIImageGeneration
        _openai_video_gen = OpenAIVideoGeneration
    return _openai_image_gen, _openai_video_gen

print("[STARTUP] Lazy loaders defined for Emergent modules", flush=True)

import base64
# iter 282al-32 — resend + twilio pull ~200ms at cold import on warm disk
# (≈8 s on cold K8s disk). Lazy-load them on first use so uvicorn binds
# the port instantly and K8s liveness probe stops timing out.
_resend = None
def _get_resend():
    global _resend
    if _resend is None:
        import resend as _r
        _resend = _r
    return _resend

_TwilioClient = None
def _get_twilio():
    global _TwilioClient
    if _TwilioClient is None:
        from twilio.rest import Client as _C
        _TwilioClient = _C
    return _TwilioClient

# Thin module-level shims so existing call sites (`resend.Emails.send(...)`,
# `TwilioClient(sid, token)`) keep working without edits.
class _ResendShim:
    def __getattr__(self, name):
        return getattr(_get_resend(), name)
resend = _ResendShim()
print("[STARTUP] Resend lazy-loader installed", flush=True)

class _TwilioClientShim:
    def __call__(self, *a, **kw):
        return _get_twilio()(*a, **kw)
TwilioClient = _TwilioClientShim()
print("[STARTUP] Twilio lazy-loader installed", flush=True)

# PayPal REST API v2 - Direct HTTP calls (more reliable than SDK)
import httpx

# Import Whapi service

sys.path.insert(0, str(Path(__file__).parent))
# Import Twilio service (replaces WHAPI) with backwards-compatible function names
from services.twilio_service import (
    validate_whatsapp_number,
    validate_phone_number,
    send_whatsapp_message,
    send_sms,
    make_voice_call,
    send_notification,
    send_milestone_new_referral_whatsapp,
    send_milestone_almost_there_whatsapp,
    send_milestone_unlocked_whatsapp,
    send_launch_invite_whatsapp,
    send_blog_followup_whatsapp,
    batch_send_launch_invites,
    verify_referral_phone,
    get_whatsapp_broadcast_list,
    analyze_scan_concerns,
    generate_social_proof_post,
    normalize_phone_number,
    send_partner_approved_whatsapp,
    send_partner_denied_whatsapp,
    send_shipping_whatsapp,
    # New Twilio features
    send_order_confirmation,
    send_abandoned_cart_notification,
    send_review_request,
    send_restock_alert,
    send_birthday_message,
    send_otp,
)

# Import modular auth routes
from routes.auth import router as auth_router
from routes.orders import router as orders_router
from routes.business_system import router as business_system_router, set_db as set_business_db, seed_business_system_data
from routes.automations import router as automations_router, set_db as set_automations_db, init_clients as init_automation_clients
from routes.rbac import router as rbac_router, set_db as set_rbac_db
from routes.automation_gaps import (
    router as automation_gaps_router,
    set_db as set_automation_gaps_db,
    init_sendgrid as init_automation_gaps_sendgrid,
    check_low_stock_alerts,
    check_npn_expiry_reminders
)
from routes.whatsapp_ai_routes import router as whatsapp_ai_router, set_db as set_whatsapp_ai_db
from routes.cache_routes import cache_router, init_cache_routes
from routes.mcp_routes import mcp_router, init_mcp_routes
from routes.db_query_routes import db_query_router, init_db_query_routes
from routes.admin import router as admin_router, init_admin_routes
from routes.chat_widget_routes import router as chat_widget_router, set_db as set_chat_widget_db
from routes.admin_action_ai_routes import router as admin_action_ai_router, set_db as set_admin_action_ai_db
# Legacy voice.voice_routes REMOVED — dead code (Deepgram/Telnyx)
from services.auto_heal import auto_heal_scheduler, set_db as set_auto_heal_db, run_all_health_checks, get_auto_heal_logs
from routes.email_routes import router as email_router, set_db as set_email_db
from routes.content_routes import router as content_router, set_db as set_content_db
from routes.api_key_routes import router as api_key_router, set_db as set_api_key_db
from routes.data_security_routes import router as data_security_router, set_db as set_data_security_db, run_monthly_data_cleanup
from routes.crash_dashboard_routes import router as crash_dashboard_router, set_db as set_crash_dashboard_db
from routes.a2a_routes import router as a2a_router, set_db as set_a2a_db
from routes.outreach_routes import router as outreach_router, set_db as set_outreach_db
from routes.phone_routes import router as phone_router, set_db as set_phone_db
from routes.site_audit_routes import router as site_audit_router, set_db as set_site_audit_db
from routes.compliance_routes import router as compliance_router, set_db as set_compliance_db
from routes.auto_repair_routes import router as auto_repair_router, set_db as set_auto_repair_db
from routes.orchestrator_routes import router as orchestrator_router, set_db as set_orchestrator_routes_db
from services.orchestrator import orchestrator, set_db as set_orchestrator_db, send_daily_digest

# TOON-based SaaS System imports
try:
    from routers.admin_mission_control_router import set_db as set_mission_control_db
    from routers.subscription_public_router import router as subscription_public_router, set_db as set_subscription_public_db
    from routers.custom_subscription_router import router as custom_subscription_router, set_db as set_custom_subscription_db
    from routers.admin_plan_management import router as admin_plan_router, set_db as set_admin_plan_db
    from routers.self_healing_router import router as self_healing_router
    from routers.connector_router import router as connector_router
    from routers.smart_search_router import router as smart_search_router
    from routers.agent_harness_router import router as agent_harness_router
    from routers.skills_router import router as skills_router
    from routers.vector_search_router import router as vector_search_router
    from routers.hooks_router import router as hooks_router
    # Crypto treasury — loads connection-status endpoint for mock/live badge
    try:
        from routers.crypto_treasury_router import router as crypto_treasury_router
    except ImportError:
        crypto_treasury_router = None
    from routers.generative_ui_router import router as generative_ui_router, set_db as set_generative_ui_db
    from services.toon_service import set_toon_service_db
    from services.self_healing_ai import set_self_healing_ai_db, get_self_healing_ai
    from services.connector_ecosystem import set_connector_ecosystem_db
    from services.smart_search import set_smart_search_db
except ImportError as e:
    logging.warning(f"[STARTUP] Mission Control imports failed: {e}")
    set_mission_control_db = None
    set_subscription_public_db = None
    set_custom_subscription_db = None
    set_admin_plan_db = None
    set_toon_service_db = None
    set_self_healing_ai_db = None
    set_connector_ecosystem_db = None
    set_smart_search_db = None
    subscription_public_router = None
    custom_subscription_router = None
    admin_plan_router = None
    self_healing_router = None
    connector_router = None
    smart_search_router = None
    agent_harness_router = None
    skills_router = None
    vector_search_router = None
    hooks_router = None
    generative_ui_router = None
    set_generative_ui_db = None
    crypto_treasury_router = None

# Crypto Signal Engine - Conditionally loaded (disabled for deployment)
crypto_router = None
start_crypto_tasks = None
if os.environ.get("ENABLE_CRYPTO_ENGINE", "").lower() == "true":
    try:
        from crypto_engine.router import router as crypto_router, start_background_tasks as start_crypto_tasks
        print("[STARTUP] Crypto Signal Engine imported", flush=True)
    except ImportError as e:
        print(f"[STARTUP] Crypto Signal Engine not available: {e}", flush=True)


# Import new CRM, Refund, and Analytics services
from services.customer_service import (
    upsert_customer_record,
    save_order_to_history,
    get_customer_full_record,
    get_all_customers_summary,
    update_customer_notes,
    send_vip_notification,
    set_db as set_customer_service_db
)
from services.refund_service import (
    request_refund,
    resolve_refund,
    get_refunds,
    set_db as set_refund_service_db
)
from services.analytics_service import (
    get_sales_dashboard,
    get_acquisition_sources,
    get_revenue_metrics,
    capture_utm_params,
    set_db as set_analytics_service_db
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env", override=False)


# Helper function to get frontend URL with intelligent fallback
def get_frontend_url():
    """Get frontend URL from environment with smart fallback.
    Priority: FRONTEND_URL > SITE_URL > None (caller must handle)
    """
    return os.environ.get("FRONTEND_URL") or os.environ.get("SITE_URL") or ""


# Extract database name from MongoDB URL if present (for Atlas), otherwise use env var
# MongoDB Atlas URLs are in format: mongodb+srv://user:pass@cluster.xxx.mongodb.net/dbname?retryWrites=true
def extract_db_from_url(url):
    """Extract database name from MongoDB connection string."""
    if not url:
        return None
    try:
        # Handle mongodb+srv:// and mongodb:// URLs
        from urllib.parse import urlparse

        parsed = urlparse(url)
        # Get the path (should be /dbname or empty)
        path = parsed.path
        if path and path != "/" and len(path) > 1:
            # Remove leading slash
            db_from_url = path.lstrip("/")
            # Remove any query params if accidentally included
            if "?" in db_from_url:
                db_from_url = db_from_url.split("?")[0]
            if db_from_url and db_from_url != "":
                return db_from_url
    except Exception:
        pass
    return None


# MongoDB connection configuration
# IMPORTANT: Client creation is deferred to startup event to avoid blocking port binding
mongo_url = os.environ.get("MONGO_URL", "")
# Priority: DB_NAME env var takes precedence over URL-embedded name (explicit > implicit)
db_name = os.environ.get("DB_NAME") or extract_db_from_url(mongo_url)

# These will be initialized in the startup event AFTER uvicorn binds to port
client = None
db = None

print(f"[DB] Configuration loaded: {db_name} (client will be created at startup)")


# MongoDB Index Setup for Performance
async def setup_database_indexes():
    """Create indexes for commonly queried fields - critical for dashboard speed.

    iter 322ee — Stripped the dead-feature indexes (bio_scans,
    marketing_broadcasts, marketing_social_posts). These collections sat
    empty in production and the indexes themselves were re-creating
    empty shells on every restart, polluting the DB scan output. Kept
    founding_members, verified_referrals, and waitlist because they're
    actively wired to the live referral system."""
    try:
        # Founding members indexes
        await db.founding_members.create_index("email", unique=True, sparse=True)
        await db.founding_members.create_index(
            "referral_code", unique=True, sparse=True
        )
        await db.founding_members.create_index("whatsapp")
        await db.founding_members.create_index("verified_referral_count")

        # Verified referrals indexes (for milestone system)
        await db.verified_referrals.create_index("referrer_code")
        await db.verified_referrals.create_index("referred_email")
        await db.verified_referrals.create_index("phone_hash")
        await db.verified_referrals.create_index(
            [("referrer_code", 1), ("referred_email", 1)], unique=True
        )

        # Waitlist indexes
        await db.waitlist.create_index("email", unique=True, sparse=True)
        await db.waitlist.create_index("referral_code")

        print("[DB] Indexes created successfully for optimized queries")
    except Exception as e:
        print(f"[DB] Index creation warning (may already exist): {e}")


# JWT Secret — uses safe 3-tier resolver (env -> file -> generated) from config.py
# so the pod boots even if JWT_SECRET env var isn't injected. K8s health probes
# stay green; admins don't get ECONNREFUSED on misconfigured deploys.
from config import JWT_SECRET, JWT_ALGORITHM  # noqa: E402

# Stripe (accepts either STRIPE_SECRET_KEY or legacy STRIPE_API_KEY)
STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY")

# Bambora/TD Merchant Configuration
BAMBORA_MERCHANT_ID = os.environ.get("BAMBORA_MERCHANT_ID")
BAMBORA_API_PASSCODE = os.environ.get("BAMBORA_API_PASSCODE")
BAMBORA_API_URL = "https://api.na.bambora.com/v1"  # Production URL

# PayPal REST API Configuration
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.environ.get("PAYPAL_SECRET")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "live")  # "sandbox" or "live"

# PayPal API Base URL
PAYPAL_API_BASE = "https://api-m.paypal.com" if PAYPAL_MODE == "live" else "https://api-m.sandbox.paypal.com"

# PayPal OAuth Token Cache
_paypal_token_cache = {"token": None, "expires_at": 0}

# Admin Data Cache - For static/semi-static data
# TTL in seconds, data stored with timestamp
_admin_cache = {}
CACHE_TTL = {
    "products": 300,        # 5 minutes
    "collections": 300,     # 5 minutes  
    "store_settings": 600,  # 10 minutes
    "shipping_zones": 600,  # 10 minutes
    "discount_codes": 120,  # 2 minutes
    "stats": 60,            # 1 minute
}

def get_cached(cache_key: str):
    """Get cached data if not expired"""
    if cache_key not in _admin_cache:
        return None
    cached = _admin_cache[cache_key]
    ttl = CACHE_TTL.get(cache_key, 60)
    if time.time() - cached["timestamp"] < ttl:
        return cached["data"]
    return None

def set_cached(cache_key: str, data):
    """Store data in cache with timestamp"""
    _admin_cache[cache_key] = {
        "data": data,
        "timestamp": time.time()
    }

def invalidate_cache(cache_key: str = None):
    """Invalidate specific cache key or all caches"""
    global _admin_cache
    if cache_key:
        _admin_cache.pop(cache_key, None)
    else:
        _admin_cache = {}

async def get_paypal_access_token():
    """Get PayPal OAuth2 access token with caching"""
    import time
    
    # Check if cached token is still valid (with 60s buffer)
    if _paypal_token_cache["token"] and _paypal_token_cache["expires_at"] > time.time() + 60:
        return _paypal_token_cache["token"]
    
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise Exception("PayPal credentials not configured")
    
    # Get new token
    credentials = base64.b64encode(f"{PAYPAL_CLIENT_ID}:{PAYPAL_SECRET}".encode()).decode()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAYPAL_API_BASE}/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data="grant_type=client_credentials"
        )
        
        if response.status_code != 200:
            logging.error(f"PayPal OAuth error: {response.text}")
            raise Exception(f"PayPal authentication failed: {response.text}")
        
        token_data = response.json()
        _paypal_token_cache["token"] = token_data["access_token"]
        _paypal_token_cache["expires_at"] = time.time() + token_data.get("expires_in", 3600)
        
        logging.info(f"✓ PayPal OAuth token obtained (expires in {token_data.get('expires_in', 3600)}s)")
        return _paypal_token_cache["token"]

# Log PayPal configuration status
if PAYPAL_CLIENT_ID and PAYPAL_SECRET:
    logging.info(f"✓ PayPal REST API configured in {PAYPAL_MODE} mode")

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID")

# Initialize Twilio client
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger = logging.getLogger(__name__)
    logger.info("✓ Twilio client initialized")

# Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

# Anthropic Claude API Key (User's Pro subscription)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Helper function to get the best API key for Claude
def get_claude_api_key():
    """Returns Emergent LLM key (primary) or falls back to Anthropic key"""
    # Prioritize Emergent LLM key as it's more reliable
    return EMERGENT_LLM_KEY or ANTHROPIC_API_KEY

# Resend Email
RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Cloudinary CDN Configuration
import cloudinary
import cloudinary.uploader
import cloudinary.utils

CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )
    logging.info("✓ Cloudinary CDN configured")

# ============= WEBSOCKET & MIDDLEWARE (Extracted to /app/backend/middleware/) =============
from middleware.websocket_manager import WebSocketConnectionManager, ws_manager
manager = WebSocketConnectionManager()

# ============= SECURITY STACK (Extracted to /app/backend/middleware/) =============
from middleware.legacy_redirect import LegacyRedirectMiddleware
from middleware.security import RedisRateLimiter, SecurityMiddleware, sanitize_input, validate_email, rate_limiter

# ============= EMAIL SYSTEM (Extracted to /app/backend/services/email_templates.py) =============
from services.email_templates import (
    get_email_base_styles,
    generate_order_confirmation_email,
    generate_shipping_update_email,
    send_order_confirmation_email,
    send_shipping_update_email,
    send_shipping_sms,
    send_shipping_notifications,
    deduct_inventory_for_order,
    process_auto_shipping,
    generate_order_cancellation_email,
    send_order_cancellation_email,
    send_review_notification_email,
    generate_email_action_token,
    verify_email_action_token,
    send_daily_review_digest,
    send_review_thank_you_email,
    generate_newsletter_confirmation_email,
    send_newsletter_confirmation_email,
    generate_goal_achieved_email,
    send_goal_achieved_email,
    send_oroe_vip_approval_email,
    validate_password_strength,
    check_account_lockout,
    record_failed_login,
    clear_failed_logins,
    set_db as _email_templates_set_db,
    set_twilio_client as _email_templates_set_twilio_client,
)

_aurem_env = os.environ.get("AUREM_ENV", "")
if not _aurem_env:
    try:
        with open(os.path.join(os.path.dirname(__file__), ".env")) as _ef:
            for _line in _ef:
                if _line.startswith("AUREM_ENV="):
                    _aurem_env = _line.strip().split("=", 1)[1].strip('"').strip("'")
    except Exception:
        pass

_is_production = _aurem_env == "production"

app = FastAPI(
    title="AUREM AI Platform",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

# ─────────────────────────────────────────────────────────────────────
# K8s/nginx liveness probes — registered FIRST so they respond as soon
# as uvicorn binds the port, before any router/middleware/startup-event
# is loaded. Critical for deployment: the probe runs `GET /health` (no
# /api prefix) every 10s during pod startup; if it 404s or times out,
# the pod is killed and the deploy fails.
# Three aliases cover all known probe configurations:
#   /health      — k8s liveness probe (current Emergent native deploy)
#   /api/health  — Emergent ingress probe (preview)
#   /ready       — k8s readiness probe (some Helm charts)
# iter 280.15 fix.
# ─────────────────────────────────────────────────────────────────────
@app.get("/health", include_in_schema=False)
async def _liveness_health():
    return {"status": "healthy"}


@app.get("/ready", include_in_schema=False)
async def _liveness_ready():
    return {"status": "ready"}


# Belt-and-braces: even though HealthProbeMiddleware short-circuits these
# paths at the outermost ASGI layer, register direct routes too so any
# request that bypasses the middleware (route prefix order, exception in
# middleware code, etc.) still gets a fast OK response. Critical for K8s
# readiness/liveness probes during production cold-start.
@app.get("/api/platform/health", include_in_schema=False)
async def _liveness_platform_health():
    return {"status": "healthy", "platform": "aurem"}


@app.get("/api/health", include_in_schema=False)
async def _liveness_api_health():
    return {"status": "healthy"}


@app.get("/live", include_in_schema=False)
async def _liveness_live():
    return {"status": "alive"}

# NOTE: /api/platform/health, /api/health, /ready, /live are ALL served
# in <1ms by `middleware/health_probe.py::HealthProbeMiddleware` at the
# outermost ASGI layer, before any router or DB touch. Do not duplicate
# them here — the middleware catches them first anyway, but a duplicate
# would just be dead code.

# ============= CORS - HARDENED FOR PRODUCTION =============
_cors_raw = os.environ.get("CORS_ORIGINS", "")
_cors_raw_stripped = _cors_raw.strip()
if _cors_raw_stripped == "*":
    # Explicit wildcard — operator opted-in to allow any origin (credentials
    # must be disabled when origin is "*" per CORS spec, so we also flip
    # allow_credentials below).
    _cors_origins = ["*"]
elif not _cors_raw_stripped:
    # Unset → safe default allowlist for aurem.live + local dev. The production
    # Emergent preview URL is appended below via REACT_APP_BACKEND_URL.
    _cors_origins = [
        "https://aurem.live",
        "https://reroots.ca",
        "http://localhost:3000",
    ]
else:
    _cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()]

# In production, also allow the dynamically assigned Emergent domain
_react_url = os.environ.get("REACT_APP_BACKEND_URL", "")
if _cors_origins != ["*"] and _react_url and _react_url not in _cors_origins:
    _cors_origins.append(_react_url)

# Also allow the APP_URL (supervisor-injected preview URL)
_app_url = os.environ.get("APP_URL", "")
if _cors_origins != ["*"] and _app_url and _app_url not in _cors_origins:
    _cors_origins.append(_app_url)

# CORS spec: allow_credentials cannot be True when origin is "*".
_allow_credentials = _cors_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=_allow_credentials,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Cache-Control", "ETag", "Content-Encoding"],
)

# ============= SECURITY HEADERS + JWT BLOCKLIST MIDDLEWARES =============
# Extracted to /app/backend/bootstrap/middlewares.py (iter 263 final surgery).
# Keeps the old 90 LOC middleware class bodies out of server.py.
from bootstrap.middlewares import (
    register_security_headers,
    register_jwt_blocklist,
    register_usage_metering,
)

register_security_headers(app)

# ============= GEO SCHEMA MIDDLEWARE (Biotech Schema 2.0) =============
from middleware.geo_schema import GeoSchemaMiddleware
app.add_middleware(GeoSchemaMiddleware)

# JWT blocklist — reject revoked tokens via Redis
register_jwt_blocklist(app)



# ============= PERFORMANCE PATCH - RATE LIMITING =============
from performance_patch import setup_rate_limiter, limiter, CacheManager, warm_cache_on_startup
setup_rate_limiter(app)

# Global cache manager instance
cache_manager = CacheManager()

# ============= USAGE METERING MIDDLEWARE =============
# Tracks AI actions per tenant for subscription enforcement.
# Registered via bootstrap.middlewares.register_usage_metering — lambda grabs
# the live `db` global so the middleware sees it after startup_event sets it.
register_usage_metering(
    app,
    db_getter=lambda: globals().get("db"),
    jwt_secret=JWT_SECRET,
    jwt_alg=JWT_ALGORITHM,
)

# ============= HEALTH CHECK ENDPOINTS - MUST BE FIRST =============
# These are registered BEFORE any heavy middleware to ensure instant response.
# Critical for deployment health probes.
# Extracted to /app/backend/bootstrap/health_routes.py (iter 263 final surgery).
from bootstrap.health_routes import register_health_routes
register_health_routes(app, db_getter=lambda: globals().get("db"))

# ============= END HEALTH CHECK ENDPOINTS =============

# ============= ASSETLINKS.JSON + UCP DISCOVERY (extracted) =============
# Extracted to /app/backend/bootstrap/wellknown_routes.py (iter 263 final surgery).
from bootstrap.wellknown_routes import register_wellknown_routes
register_wellknown_routes(app)

# ============= REQUEST LIFECYCLE MIDDLEWARE (Extracted to /app/backend/middleware/) =============
from middleware.request_lifecycle import DatabaseReadinessMiddleware, BrandDetectionMiddleware
from middleware.crash_protection import RequestTimeoutMiddleware, global_exception_handler
try:
    from services.crash_protection import log_crash, set_crash_log_db
except ImportError:
    def _noop_crash_db(db): pass
    set_crash_log_db = _noop_crash_db
from middleware.cache_headers import CacheHeadersMiddleware

# ============= MILESTONE UNLOCK SYSTEM (Extracted to services/milestone_system.py) =============
from services.milestone_system import (
    generate_device_fingerprint,
    check_referral_fraud,
    verify_referral_for_milestone,
    get_milestone_progress,
    unlock_milestone_discount,
    send_milestone_almost_there_email,
    send_milestone_unlocked_email,
    set_db as set_milestone_db,
    MILESTONE_REFERRAL_THRESHOLD,
    MILESTONE_DISCOUNT_PERCENT,
    MILESTONE_EMAIL_TRIGGER,
    FRAUD_MAX_REFERRALS_PER_IP,
    FRAUD_MAX_REFERRALS_PER_DEVICE,
)


# (Milestone functions moved to services/milestone_system.py)



# CacheHeadersMiddleware — canonical version in middleware/cache_headers.py


app.add_middleware(CacheHeadersMiddleware)

# Add security middleware
app.add_middleware(SecurityMiddleware)

# Add legacy URL redirect middleware (for old Wix URLs - SEO)
app.add_middleware(LegacyRedirectMiddleware)

# Tier metering middleware — enforces plan limits on every /api/ call
try:
    from middleware.tier_metering import TierMeteringMiddleware
    app.add_middleware(TierMeteringMiddleware)
    print("[STARTUP] Tier Metering Middleware loaded", flush=True)
except ImportError as e:
    print(f"[STARTUP] Tier Metering Middleware not loaded: {e}", flush=True)

# iter 322 — BIN context middleware. Decodes JWT once, attaches BinCtx to
# request.state. Must come BEFORE service_gate-decorated routes.
try:
    from middleware.bin_context import BinContextMiddleware
    app.add_middleware(BinContextMiddleware)
    print("[STARTUP] BIN Context Middleware loaded", flush=True)
except Exception as e:
    print(f"[STARTUP] BIN Context Middleware not loaded: {e}", flush=True)

# iter 322ff — Auto-capture every 5xx + unhandled exception into the
# incident pipeline. Observes, never blocks. Must come BEFORE the global
# exception handler so we see the exception before it's swallowed.
try:
    from middleware.exception_to_incident import ExceptionToIncidentMiddleware
    app.add_middleware(ExceptionToIncidentMiddleware)
    print("[STARTUP] Exception→Incident Middleware loaded (iter 322ff)", flush=True)
except Exception as e:
    print(f"[STARTUP] Exception→Incident Middleware not loaded: {e}", flush=True)


# Register global exception handler (extracted from middleware/crash_protection.py)
app.add_exception_handler(Exception, global_exception_handler)

# Database Activity Audit Middleware — logs all writes + suspicious reads
try:
    from middleware.db_audit import DatabaseAuditMiddleware
    app.add_middleware(DatabaseAuditMiddleware)
    print("[STARTUP] Database Audit Middleware loaded", flush=True)
except ImportError as e:
    print(f"[STARTUP] Database Audit Middleware not loaded: {e}", flush=True)


# Phase 4 — Error Ledger crash-catcher (persists every uncaught backend
# exception into `error_ledger`, dedupes by hash, emits ERROR_CAPTURED).
# MUST be added BEFORE HealthProbeMiddleware so HealthProbe stays outermost
# and short-circuits /health|/ready|/live before any DB write attempt.
try:
    from services.error_ledger import install_crash_catcher, install_global_exception_hook
    install_crash_catcher(app)
    install_global_exception_hook()
    print("[STARTUP] Error Ledger crash-catcher installed", flush=True)
except Exception as _e:
    print(f"[STARTUP] Error Ledger FAILED to load: {_e}", flush=True)

# ─── HEALTH PROBE SHIM (iter 282v) ────────────────────────────────────
# MUST be the LAST add_middleware call → becomes the OUTERMOST wrapper →
# intercepts GET /health|/ready|/live before any other middleware or
# FastAPI routing runs. Guarantees K8s liveness/readiness probes NEVER
# time out, even during heavy startup or when a long APScheduler job
# blocks the event loop.
try:
    from middleware.health_probe import HealthProbeMiddleware
    app.add_middleware(HealthProbeMiddleware)
    print("[STARTUP] Health Probe shim loaded (outermost)", flush=True)
except Exception as _e:
    print(f"[STARTUP] Health Probe shim FAILED to load: {_e}", flush=True)


# ============= DATABASE INDEXES FOR PERFORMANCE =============
async def create_indexes():
    """Create database indexes for optimal query performance.

    iter 322ee — Stripped the e-commerce-skeleton indexes (products,
    orders, carts, discount_codes, subscribers, abandoned_carts,
    analytics_visits, reviews). AUREM is a SaaS platform, not a
    Shopify-style storefront — none of these collections has ever
    received a write and they keep auto-resurrecting empty on every
    startup, polluting `list_collection_names()` and confusing the DB
    audit. The full e-commerce code surface is also lean-mode-skipped
    via routers/_registry_config.SKIP_IN_LEAN."""
    try:
        # Users - auth lookups (handle duplicate key gracefully)
        try:
            await db.users.create_index("email", unique=True)
        except Exception as e:
            if "duplicate key" in str(e).lower():
                logging.info(
                    "Users email index exists (duplicate key detected in data)"
                )
            else:
                raise

        # Analytics - time-based queries (the *_events live collection
        # actually receives data; the *_visits one was dead).
        await db.analytics_events.create_index("timestamp")
        await db.analytics_events.create_index("event_type")

        # Bug-fix #33 — TTL index for the BIN-auth reset-token JTI
        # replay-protection collection. `expires_at` lets Mongo auto-prune
        # used jtis after 20 min so the collection never balloons.
        try:
            await db.bin_reset_token_jtis.create_index(
                "expires_at", expireAfterSeconds=0
            )
            await db.bin_reset_token_jtis.create_index("jti", unique=True)
        except Exception as _e:
            logging.debug(f"[INDEX] bin_reset_token_jtis idx: {_e}")

        logging.info("✓ Database indexes created/verified")

        # iter 324f — Auth-critical login indexes (B-tree on users.email,
        # platform_users.email, team_members.email, etc.). Idempotent;
        # safe to call on every startup. Cuts login DB lookup from
        # 50-500ms (full scan) to <5ms (B-tree hit).
        try:
            from utils.ensure_auth_indexes import ensure_auth_indexes
            res = await ensure_auth_indexes(db)
            logging.info(f"[startup] auth indexes ensured — {res.get('ok')} ok, {res.get('errors')} errors")
        except Exception as e:
            logging.warning(f"[startup] auth index setup failed (non-fatal): {e}")

        # Seed internal @aurem.live addresses into do_not_contact so any
        # legacy code paths that pre-check DNC also respect the block.
        try:
            from services.recipient_guard import ensure_dnc_seeded
            seeded = await ensure_dnc_seeded(db)
            if seeded:
                logging.info(f"[recipient-guard] seeded {seeded} internal addresses into do_not_contact")
        except Exception as e:
            logging.warning(f"[recipient-guard] DNC seed failed (non-fatal): {e}")
    except Exception as e:
        logging.warning(f"Index creation warning (may already exist): {e}")


# Global HTTP client for auth operations (connection pooling for speed)
_auth_client: httpx.AsyncClient = None

async def get_auth_client() -> httpx.AsyncClient:
    """Get or create a reusable HTTP client for auth operations"""
    global _auth_client
    if _auth_client is None or _auth_client.is_closed:
        _auth_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)
        )
    return _auth_client


async def _async_archive(db):
    """Background task: archive cold data + seed tenant integrations."""
    import asyncio
    await asyncio.sleep(30)
    try:
        from services.db_optimizer import archive_cold_data, _update_db_summary
        archived = await archive_cold_data(db, days_threshold=7)
        await _update_db_summary(db)
        if archived > 0:
            logging.info(f"[DB-OPT] Background archive complete: {archived} docs moved to cold storage")
    except Exception as e:
        logging.warning(f"[DB-OPT] Background archive failed: {e}")
    
    # Seed integration profiles for existing tenants
    try:
        from services.provisioning_service import set_db as set_prov_db, seed_existing_tenants
        set_prov_db(db)
        seeded = await seed_existing_tenants()
        if seeded > 0:
            logging.info(f"[Provisioning] Auto-seeded {seeded} tenant integration profiles")
    except Exception as e:
        logging.warning(f"[Provisioning] Auto-seed failed: {e}")


@app.on_event("startup")
async def startup_event():
    """Run on application startup - AFTER uvicorn binds to port"""
    import traceback
    import time
    global client, db
    
    app.state.start_time = time.time()
    startup_start = time.time()
    
    try:
        # Log immediate startup
        logging.info("✓ ReRoots API starting...")

        # ═══ SMS KILL SWITCH (A2P 10DLC pending) ═══
        # Globally intercept twilio.rest.Client.messages.create so any direct
        # SMS send (drip_sequencer, trial_sms, automations, etc.) is suppressed
        # and logged. WhatsApp messages pass through untouched.
        try:
            from services.sms_killswitch import install_global_patch, is_sms_disabled
            install_global_patch()
            logging.info(f"[SMS] kill switch active: SMS_DISABLED={is_sms_disabled()}")
        except Exception as e:  # noqa: BLE001
            logging.warning(f"[SMS] kill switch install failed: {e}")

        # ═══ RECIPIENT GUARD (block @aurem.live outbound except ora@) ═══
        # Globally monkey-patch resend.Emails.send so EVERY outbound email
        # path filters out internal/own-domain recipients (qa-bot@aurem.live,
        # etc.). Prevents the self-spam loop where qa_bot's SEO probe
        # auto-subscribed itself into the outreach pipeline.
        try:
            from services.recipient_guard import install_recipient_guard
            install_recipient_guard()
        except Exception as e:  # noqa: BLE001
            logging.warning(f"[recipient-guard] install failed: {e}")
        
        # Log critical environment variables (for debugging production issues)
        logging.info(f"[ENV] MONGO_URL set: {'✓' if os.environ.get('MONGO_URL') else '❌'}")
        logging.info(f"[ENV] DB_NAME: {os.environ.get('DB_NAME', 'not set')}")
        logging.info(f"[ENV] FRONTEND_URL: {os.environ.get('FRONTEND_URL', 'not set')}")
        logging.info(f"[ENV] SITE_URL: {os.environ.get('SITE_URL', 'not set')}")
        logging.info(f"[ENV] JWT_SECRET set: {'✓' if os.environ.get('JWT_SECRET') else '❌'}")
        
        # iter 322br — pre-warm Groq HTTP/2 socket (saves ~100ms first chat)
        try:
            from routers.public_ora_demo_router import prewarm_groq
            asyncio.create_task(prewarm_groq())
        except Exception as _pe:
            logging.debug(f"[ORA] Groq prewarm skipped: {_pe}")

        # Validate required secrets first
        try:
            from utils.secrets import validate_all_secrets, scan_for_pymongo_antipatterns
            validate_all_secrets()
            logging.info("Secrets validation passed")
            
            # PyMongo anti-pattern scan — skip on startup to reduce log noise
            # Run manually via: python -c "from utils.secrets import scan_for_pymongo_antipatterns; scan_for_pymongo_antipatterns()"
        except RuntimeError as e:
            logging.error(f"❌ Secrets validation failed: {e}")
            # Don't crash - some secrets may be optional in dev mode
        except ImportError:
            logging.warning("⚠ Secrets module not found - skipping validation")
        
        # Initialize MongoDB client - this is where DNS SRV lookup happens for mongodb+srv://
        # It runs AFTER uvicorn binds, so health checks will already work
        t0 = time.time()
        try:
            if not mongo_url:
                logging.error("❌ MONGO_URL not configured - database operations will fail")
                logging.warning("Server will continue but database operations will fail")
            else:
                # [DEPLOY FIX iter 322ea] Atlas pool exhaustion was killing
                # K8s health probes: with maxPoolSize=50 + 4 per-minute
                # scheduler jobs all hitting Atlas at xx:00, the pool
                # iter 323b — REVERTED maxPoolSize 200 → 10 (user directive).
                # Connection storms during Atlas hiccups were saturating the
                # pool faster than waitQueueTimeoutMS could fail-fast. Small
                # pool + tight timeouts = fail-fast + clear error logs.
                #   • maxPoolSize 10        : enough for steady-state, no storm
                #   • minPoolSize 1         : single warm connection always ready
                #   • maxIdleTimeMS 30s     : drop idle connections, force refresh
                #   • connectTimeoutMS 5s   : was 10s
                #   • serverSelectionTimeoutMS 5s  : was 5s (unchanged)
                #   • socketTimeoutMS 10s   : was 20s — fail-fast on stuck Atlas
                #   • waitQueueTimeoutMS 5s : was 2s — give pool a chance to drain
                client = AsyncIOMotorClient(
                    mongo_url,
                    maxPoolSize=10,
                    minPoolSize=1,
                    maxIdleTimeMS=30000,
                    connectTimeoutMS=5000,
                    serverSelectionTimeoutMS=5000,
                    socketTimeoutMS=10000,
                    waitQueueTimeoutMS=5000,
                    retryWrites=True,
                )
                db = client[db_name]
                print(f"[STARTUP] ✓ MongoDB client created ({time.time()-t0:.2f}s)", flush=True)
                logging.info(f"✓ MongoDB client created ({time.time()-t0:.2f}s)")

                # iter 323b — startup health check: ping Mongo within 3s.
                # If unreachable, log a CLEAR message instead of hanging
                # silently and letting every downstream request timeout.
                # Note: uses asyncio.shield + Motor's get_io_loop adapter
                # to avoid "this event loop is already running" when Motor's
                # internal Future is awaited under wait_for during lifespan.
                async def _mongo_ping():
                    try:
                        await client.admin.command("ping")
                        print(f"[STARTUP] ✓ MongoDB ping OK ({time.time()-t0:.2f}s)", flush=True)
                        logging.info(f"✓ MongoDB ping OK ({time.time()-t0:.2f}s)")
                    except Exception as _ping_e:
                        print(f"[STARTUP] 🔴 MONGO UNREACHABLE — ping error: {_ping_e}", flush=True)
                        logging.error(f"🔴 MONGO UNREACHABLE — ping error: {_ping_e}")
                try:
                    import asyncio as _aio
                    _ping_task = _aio.create_task(_mongo_ping())
                    try:
                        await _aio.wait_for(_aio.shield(_ping_task), timeout=3.0)
                    except _aio.TimeoutError:
                        print("[STARTUP] 🔴 MONGO UNREACHABLE — ping timeout after 3s", flush=True)
                        logging.error(
                            "🔴 MONGO UNREACHABLE — ping timeout after 3s. "
                            "App will start but DB-dependent routes will fail fast."
                        )
                except Exception as _outer_e:
                    logging.warning(f"[STARTUP] mongo ping check skipped: {_outer_e}")
                
                # ════════════════════════════════════════════════════════════════
                # TENANT SCOPED DB — wrap raw db with auto-scoping proxy
                # ════════════════════════════════════════════════════════════════
                try:
                    from services.scoped_db import TenantScopedDatabase
                    db = TenantScopedDatabase(db)
                    logging.info("[STARTUP] ✓ TenantScopedDatabase proxy active — all queries auto-scoped")
                except Exception as e:
                    logging.warning(f"[STARTUP] TenantScopedDatabase not loaded: {e} — using raw db")
                
                # ════════════════════════════════════════════════════════════════
                # [DEPLOY FIX iter 322bz] All Atlas-touching probes moved to a
                # SINGLE background task so startup_event() returns in <500ms
                # on cold Atlas. Without this, validation(8s)+founders(8s)+
                # prewarm(8s) could push lifespan startup past the K8s probe
                # budget and the pod is killed before /health ever responds.
                # ════════════════════════════════════════════════════════════════
                async def _bg_atlas_init():
                    # 0. Env-var validation (never raises; flat report)
                    try:
                        from bootstrap.startup_validation import validate_environment
                        validate_environment()
                    except Exception as e:
                        logging.warning(f"[STARTUP-BG] env validation skipped: {e}")

                    # 1. Startup validation
                    try:
                        from services.startup_validation import run_startup_validation
                        validation_passed = await asyncio.wait_for(
                            run_startup_validation(db), timeout=15.0
                        )
                        if validation_passed:
                            logging.info("[STARTUP-BG] ✅ Startup validation passed")
                        else:
                            logging.warning("[STARTUP-BG] ⚠️ Startup validation failed (continuing)")
                    except Exception as e:
                        logging.warning(f"[STARTUP-BG] validation skipped: {e}")

                    # 2. Founder auto-provision (idempotent)
                    try:
                        from services.founder_provision import ensure_founders
                        fdr = await asyncio.wait_for(ensure_founders(db), timeout=15.0)
                        logging.info(f"[STARTUP-BG] founders provisioned: {fdr}")
                    except Exception as e:
                        logging.warning(f"[STARTUP-BG] founders skipped: {e}")

                    # 3. Auth-pool pre-warm
                    try:
                        cmds = [
                            db.users.estimated_document_count(),
                            db.platform_users.estimated_document_count(),
                            db.team_members.estimated_document_count(),
                            db.aurem_billing.estimated_document_count(),
                            db.command("ping"),
                        ]
                        pw_t0 = time.time()
                        pw_results = await asyncio.wait_for(
                            asyncio.gather(*cmds, return_exceptions=True), timeout=15.0
                        )
                        n_ok = sum(1 for r in pw_results if not isinstance(r, Exception))
                        logging.info(
                            f"[STARTUP-BG] auth-pool prewarm done in {(time.time()-pw_t0)*1000:.0f}ms "
                            f"({n_ok}/{len(pw_results)} ok)"
                        )
                    except Exception as e:
                        logging.warning(f"[STARTUP-BG] auth-pool prewarm skipped: {e}")

                asyncio.create_task(_bg_atlas_init())
                logging.info("[STARTUP] Atlas-touching probes scheduled in background")
                # ════════════════════════════════════════════════════════════════
                
        except Exception as e:
            logging.error(f"❌ MongoDB client creation failed: {e}")
            logging.warning("Server will continue but database operations will fail")
        
        # Initialize auth client immediately (fast) — moved to bg to never
        # block lifespan startup. Client construction does no I/O; the
        # check just happens to be wrapped in a coroutine.
        async def _bg_auth_client_init():
            try:
                await asyncio.wait_for(get_auth_client(), timeout=10.0)
                logging.info("[STARTUP-BG] Auth HTTP client initialized")
            except Exception as e:
                logging.warning(f"[STARTUP-BG] Auth HTTP client init failed: {e}")
        asyncio.create_task(_bg_auth_client_init())
        
        # Initialize Redis cache and warm hot data (all bg to keep lifespan fast)
        async def _bg_cache_init():
            try:
                await asyncio.wait_for(cache_manager.connect(), timeout=10.0)
                if cache_manager.available and db is not None:
                    asyncio.create_task(warm_cache_on_startup(cache_manager, db))
                    init_cache_routes(cache_manager, db, warm_cache_on_startup)
                logging.info("[STARTUP-BG] Cache layer initialized")
            except Exception as e:
                logging.warning(f"[STARTUP-BG] Cache init skipped: {e}")
        asyncio.create_task(_bg_cache_init())
        
        # Rate limiter — bg init
        async def _bg_ratelimit_init():
            try:
                await asyncio.wait_for(rate_limiter.connect(), timeout=10.0)
                logging.info("[STARTUP-BG] Rate limiter initialized")
            except Exception as e:
                logging.warning(f"[STARTUP-BG] Rate limiter init failed: {e}")
        asyncio.create_task(_bg_ratelimit_init())

        # ════════════════════════════════════════════════════════════════
        # [iter 322ex] ORA Agent Jobs background worker
        # ════════════════════════════════════════════════════════════════
        # Production bug found: /admin/ora-chat enqueues a job via
        # POST /api/ora/agent/run-async but NOTHING WAS DRAINING THE QUEUE.
        # Frontend polls /status for 5.4 min, sees "pending" forever, gives
        # up — user feels "spinner scrolls then goes silent".
        # This boot wires the single-process worker into the live loop
        # right after Mongo is ready so every enqueued job gets executed.
        async def _bg_ora_agent_jobs_worker():
            try:
                from services import ora_agent_jobs
                # Re-bind db in case set_db wasn't called yet via the
                # ora_agent_router import path.
                if db is not None:
                    ora_agent_jobs.set_db(db)
                ora_agent_jobs.start_worker()
                logging.info("[STARTUP-BG] ✓ ora_agent_jobs worker started")
            except Exception as e:
                logging.warning(f"[STARTUP-BG] ora_agent_jobs worker failed: {e}")
        asyncio.create_task(_bg_ora_agent_jobs_worker())
        
        # Initialize DB Query routes with shared db connection
        if db is not None:
            init_db_query_routes(db)
            init_mcp_routes(db)
            logging.info("✓ DB Query and MCP routes initialized")
        
        # Set database reference for Business System module
        t0 = time.time()
        set_business_db(db)
        logging.info(f"✓ Business System module initialized ({time.time()-t0:.2f}s)")
        
        # Initialize extracted modules (Milestone, Cron, Misc Routes)
        set_milestone_db(db)
        set_cron_db(db)
        set_misc_deps(db, os.environ.get("JWT_SECRET") or "", "HS256", ws_manager)
        logging.info("✓ Extracted modules initialized (Milestone, Cron, Misc Routes)")

        # iter 322 — expose db on app.state for service_gate decorator
        app.state.db = db
        
        # Register ALL routers (extracted from server.py Phase 2)
        register_all_routers(app, db)
        logging.info("✓ All routers registered via registry.py")

        # Wire db + twilio_client into the extracted email_templates module
        # (these used to be globals when this code lived in server.py)
        try:
            _email_templates_set_db(db)
            _email_templates_set_twilio_client(twilio_client)
            logging.info("✓ email_templates.db + twilio_client wired")
        except Exception as _e:
            logging.warning(f"email_templates wiring skipped: {_e}")

        # iter 296 — Platform Spine: A2A queue + Council + ORA Learning
        try:
            from services.a2a_task_queue import set_db as _a2a_set_db
            from services.council import set_db as _council_set_db
            from services.ora_learning import set_db as _ora_set_db
            from services.auto_website_builder import ensure_indexes as _awb_ix
            from services.awb_autopilot import set_db as _ap_set_db
            _a2a_set_db(db); _council_set_db(db); _ora_set_db(db); _awb_ix(db); _ap_set_db(db)
            logging.info("✓ Platform Spine wired (A2A + Council + ORA Learning + AWB + AutoPilot)")
        except Exception as _e:
            logging.warning(f"Platform Spine wiring skipped: {_e}")
        
        # Set database reference for Automations module
        t0 = time.time()
        set_automations_db(db)
        init_automation_clients()
        logging.info(f"✓ Automations module initialized ({time.time()-t0:.2f}s)")
        
        # Set database reference for RBAC module
        t0 = time.time()
        set_rbac_db(db)
        logging.info(f"✓ RBAC module initialized ({time.time()-t0:.2f}s)")
        
        # Phase F-G db init (handled by registry.py, but ensure key ones are set)
        try:
            from routers.universal_connector_router import set_db as set_universal_db
            from routers.ucp_router import set_db as set_ucp_db
            from routers.ora_action_router import set_db as set_ora_action_db
            from routers.ghost_geo_router import set_db as set_ghost_geo_db
            set_universal_db(db)
            set_ucp_db(db)
            set_ora_action_db(db)
            set_ghost_geo_db(db)
            logging.info("✓ Phase F-G initialized (Universal + UCP + ORA + Ghost + GEO)")
        except Exception as e:
            logging.warning(f"Phase F-G partial init: {e}")
        
        # Initialize Guardrail Proxy + Backup Service
        try:
            from services.guardrail_proxy import set_db as set_guardrail_db
            from services.backup_service import set_db as set_backup_db
            set_guardrail_db(db)
            set_backup_db(db)
            logging.info("✓ Guardrail Proxy + Backup Service initialized")
        except Exception as e:
            logging.warning(f"Guardrail/Backup init: {e}")
        
        # Backup loop moved to Pillar 4 worker (pillars/command_hub/worker.py)
        # — runs in the isolated observability task group instead of on the
        # main event loop. Leaving this comment as a breadcrumb for iter 263+.
        
        # Run DB optimization (compound indexes + cold storage archive)
        # [DEPLOY FIX iter 246] Move to background to avoid blocking uvicorn startup.
        # On a cold Atlas cluster, creating 16 compound indexes synchronously
        # takes 30-60+ seconds which exceeds K8s readiness probe timeout and
        # causes the pod to be killed in a restart loop. K8s best practice:
        # startup_event should ONLY initialize the bare minimum needed to bind
        # the port; everything else (indexes, DB summaries, archives) goes to
        # background tasks so uvicorn accepts requests immediately.
        try:
            from services.db_optimizer import create_compound_indexes, _update_db_summary
            async def _db_opt_bg():
                try:
                    await create_compound_indexes(db)
                    await _update_db_summary(db)
                    logging.info("✓ DB Optimizer (bg): indexes ensured, summary updated")
                except Exception as e:
                    logging.warning(f"DB Optimizer bg task: {e}")
            asyncio.create_task(_db_opt_bg())
            asyncio.create_task(_async_archive(db))
            logging.info("✓ DB Optimizer scheduled (background)")
        except Exception as e:
            logging.warning(f"DB Optimizer init: {e}")
        
        # Self-Repair Loop is now run by Pillar 3 worker (pillars/site_monitor/worker.py)
        # Only the router-side DB/JWT injection happens here.
        try:
            from routers.self_repair_router import set_db as set_self_repair_router_db, set_jwt as set_self_repair_jwt
            set_self_repair_router_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_self_repair_jwt(JWT_SECRET, JWT_ALGORITHM)
            logging.info("✓ Self-Repair router wired (loop runs in Pillar 3 worker)")
        except Exception:
            pass
        # Set DB and JWT for Client Dashboard router
        try:
            from routers.client_dashboard_router import set_db as set_client_dash_db, set_jwt as set_client_jwt
            set_client_dash_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_client_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception:
            pass
        # Set DB for Patch Deployer router
        try:
            from routers.patch_router import set_db as set_patch_router_db
            set_patch_router_db(db)
        except Exception:
            pass
        # Set DB for Deployment Router API
        try:
            from routers.deployment_router_api import set_db as set_deploy_api_db
            set_deploy_api_db(db)
        except Exception:
            pass
        # Set DB and JWT for SOC 2 Compliance Router
        try:
            from routers.soc2_compliance_router import set_db as set_soc2_db_fn, set_jwt as set_soc2_jwt_fn
            set_soc2_db_fn(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_soc2_jwt_fn(JWT_SECRET, JWT_ALGORITHM)
            # Load kill switch state from DB (bg-task to avoid startup block)
            from services.kill_switch import load_state_from_db
            asyncio.create_task(load_state_from_db())
            # Daily compliance scheduler moved to Pillar 2 worker (pillars/billing/worker.py)
            # Init HMAC signing DB (router-side wiring only)
            from services.hmac_signing import set_db as set_hmac_db_fn
            set_hmac_db_fn(db)
        except Exception:
            pass

        # Set DB and JWT for Root Command (Unified Error Intelligence Hub)
        try:
            from routers.root_command_router import set_db as set_root_cmd_db, set_jwt as set_root_cmd_jwt
            set_root_cmd_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_root_cmd_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception as _e:
            logging.warning(f"[STARTUP] Root Command router wiring failed: {_e}")

        # Set DB and JWT for Stem-Fix (Phase 2 — Root-Level Refactor Engine)
        try:
            from routers.stem_fix_router import set_db as set_stem_fix_db, set_jwt as set_stem_fix_jwt
            set_stem_fix_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_stem_fix_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception as _e:
            logging.warning(f"[STARTUP] Stem-Fix router wiring failed: {_e}")

        # Set DB and JWT for Pillars Map (3-Level Deep Drill Diagnostic)
        try:
            from routers.pillars_map_router import set_db as set_pmap_db, set_jwt as set_pmap_jwt
            set_pmap_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_pmap_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception as _e:
            logging.warning(f"[STARTUP] Pillars Map router wiring failed: {_e}")

        # Set DB and JWT for Endpoint Audit (Evidence Classifier)
        try:
            from routers.endpoint_audit_router import set_db as set_epaudit_db, set_jwt as set_epaudit_jwt
            set_epaudit_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_epaudit_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception as _e:
            logging.warning(f"[STARTUP] Endpoint Audit router wiring failed: {_e}")

        # Set DB and JWT for Deploy Drift Monitor (iter 280.2)
        try:
            from routers.deploy_drift_router import set_db as set_drift_db, set_jwt as set_drift_jwt
            set_drift_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_drift_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception as _e:
            logging.warning(f"[STARTUP] Deploy Drift router wiring failed: {_e}")

        # Set DB and JWT for Autonomous Repair Engine (iter 281)
        try:
            from routers.autonomous_repair_router import set_db as set_ar_db, set_jwt as set_ar_jwt
            set_ar_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_ar_jwt(JWT_SECRET, JWT_ALGORITHM)
        except Exception as _e:
            logging.warning(f"[STARTUP] Autonomous Repair router wiring failed: {_e}")

        # Wire A2A bus DB so pillar_monitor + autonomous_repair events persist (iter 282)
        try:
            from services.a2a_bus import bus as _a2a_bus
            _a2a_bus.set_db(db)
            logging.info("[STARTUP] A2A bus DB wired (iter 282)")
        except Exception as _e:
            logging.warning(f"[STARTUP] A2A bus DB wiring failed: {_e}")

        # Set DB and JWT for Truth Ledger (iter 283 — Honesty DNA)
        try:
            from routers.truth_ledger_router import set_db as set_tl_db, set_jwt as set_tl_jwt
            set_tl_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_tl_jwt(JWT_SECRET, JWT_ALGORITHM)
            logging.info("[STARTUP] Truth Ledger wired (iter 283)")
        except Exception as _e:
            logging.warning(f"[STARTUP] Truth Ledger wiring failed: {_e}")

        # Set DB and JWT for A2A Connectivity Audit (iter 284)
        try:
            from routers.a2a_audit_router import set_db as set_au_db, set_jwt as set_au_jwt
            set_au_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_au_jwt(JWT_SECRET, JWT_ALGORITHM)
            logging.info("[STARTUP] A2A Connectivity Audit wired (iter 284)")
        except Exception as _e:
            logging.warning(f"[STARTUP] A2A Connectivity Audit wiring failed: {_e}")

        # Set DB and JWT for Sentinel Anomaly (iter 285.3)
        try:
            from routers.sentinel_anomaly_router import set_db as set_sa_db, set_jwt as set_sa_jwt
            set_sa_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_sa_jwt(JWT_SECRET, JWT_ALGORITHM)
            logging.info("[STARTUP] Sentinel Anomaly wired (iter 285.3)")
        except Exception as _e:
            logging.warning(f"[STARTUP] Sentinel Anomaly wiring failed: {_e}")

        # Set DB and JWT for MTTH & Transparency Wall (iter 285.4)
        try:
            from routers.mtth_router import set_db as set_mtth_db, set_jwt as set_mtth_jwt
            set_mtth_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_mtth_jwt(JWT_SECRET, JWT_ALGORITHM)
            logging.info("[STARTUP] MTTH & Transparency wired (iter 285.4)")
        except Exception as _e:
            logging.warning(f"[STARTUP] MTTH & Transparency wiring failed: {_e}")

        # Set DB and JWT for Sovereign Node & Empire HUD (iter 285.6)
        try:
            from routers.sovereign_node_router import set_db as set_sn_db, set_jwt as set_sn_jwt
            set_sn_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_sn_jwt(JWT_SECRET, JWT_ALGORITHM)
            logging.info("[STARTUP] Sovereign Node & Empire HUD wired (iter 285.6)")
        except Exception as _e:
            logging.warning(f"[STARTUP] Sovereign Node wiring failed: {_e}")

        # Set DB and JWT for Master Autopilot (iter 285.8) + launch tick scheduler
        try:
            from routers.master_autopilot_router import (
                set_db as set_ap_db, set_jwt as set_ap_jwt,
                autopilot_tick_scheduler, evening_wrap_scheduler,
            )
            set_ap_db(db)
            from config import JWT_SECRET, JWT_ALGORITHM
            set_ap_jwt(JWT_SECRET, JWT_ALGORITHM)
            import asyncio as _aio
            _aio.create_task(autopilot_tick_scheduler())
            _aio.create_task(evening_wrap_scheduler())  # iter 286.0
            logging.info("[STARTUP] Master Autopilot + Evening Wrap wired (iter 285.8 + 286.0)")
        except Exception as _e:
            logging.warning(f"[STARTUP] Master Autopilot wiring failed: {_e}")

        # Set database reference for Automation Gaps (low stock, NPN expiry, etc.)
        t0 = time.time()
        set_automation_gaps_db(db)
        init_automation_gaps_sendgrid()
        logging.info(f"✓ Automation Gaps module initialized ({time.time()-t0:.2f}s)")
        
        # Set database reference for WhatsApp AI Assistant
        t0 = time.time()
        set_whatsapp_ai_db(db)
        logging.info(f"✓ WhatsApp AI Assistant initialized ({time.time()-t0:.2f}s)")
        
        # Set database references for Mission Control admin dashboard
        try:
            if set_mission_control_db:
                set_mission_control_db(db)
            if set_subscription_public_db:
                set_subscription_public_db(db)
            if set_custom_subscription_db:
                set_custom_subscription_db(db)
            if set_admin_plan_db:
                set_admin_plan_db(db)
            if set_toon_service_db:
                set_toon_service_db(db)
            logging.info("✓ Mission Control DB initialized")
        except Exception as e:
            logging.warning(f"Mission Control DB init failed: {e}")
        
        # Set database references for new CRM, Refund, and Analytics services
        t0 = time.time()
        set_customer_service_db(db)
        set_refund_service_db(db)
        set_analytics_service_db(db)
        logging.info(f"✓ CRM, Refund, and Analytics services initialized ({time.time()-t0:.2f}s)")
        
        # Initialize Admin routes with shared dependencies
        t0 = time.time()
        init_admin_routes(db, os.environ.get("JWT_SECRET") or "", None, None)
        logging.info(f"✓ Admin routes module initialized ({time.time()-t0:.2f}s)")
        
        # ═══ BULK SERVICE INIT (Extracted to services/startup_init.py) ═══
        # [DEPLOY FIX iter 247] init_all_service_dbs does 130+ module imports.
        # In a deployed container with cold module cache this can take 5-15s.
        # Moved to background task so uvicorn accepts traffic immediately.
        # Route handlers will return 503 briefly if hit before set_db completes,
        # but health checks (which matter for K8s readiness) pass instantly.
        from services.startup_init import init_all_service_dbs, init_aurem_indexes, init_aurem_redis, start_agent_reach_crawler, ensure_indexes
        async def _bulk_service_init_bg():
            try:
                t0 = time.time()
                init_all_service_dbs(db)
                start_agent_reach_crawler(db)
                logging.info(f"[bg] All service DBs initialized via startup_init.py ({time.time()-t0:.2f}s)")
            except Exception as e:
                logging.warning(f"[bg] Bulk service init failed: {e}")
        asyncio.create_task(_bulk_service_init_bg())
        _safe_task(init_aurem_indexes(db), "init_aurem_indexes")
        _safe_task(init_aurem_redis(), "init_aurem_redis")
        _safe_task(ensure_indexes(db), "ensure_indexes")
        logging.info("✓ Service init scheduled (background)")

        # ── ORA Async Job Worker (CF 524 fix) ────────────────────────
        # Spawns a long-running coroutine that drains the ora_agent_jobs
        # Mongo queue. Without this, /run-async would enqueue jobs that
        # never get processed. The worker is the entire reason the
        # async pattern works — keep it BEFORE any other startup that
        # might raise and abort the startup callback.
        try:
            from services import ora_agent_jobs
            ora_agent_jobs.set_db(db)
            _safe_task(ora_agent_jobs.worker_loop(), "ora_agent_jobs_worker")
            logging.info("✓ ORA async job worker started")
        except Exception as _e:
            logging.warning(f"[startup] ora_agent_jobs worker failed: {_e}")

        # Iter 289.5 — record this boot's commit for Founder Timeline + commit links
        try:
            from services.deploy_logger import log_deploy_event
            _safe_task(log_deploy_event(db, trigger="boot"), "deploy_event_log")
        except Exception as _e:
            logging.warning(f"[deploy-log] startup hook skipped: {_e}")

        # ═══ Circuit Breakers + Pillar Orchestrator (Autonomy v3) ═══
        print("[STARTUP] Autonomy v3: initializing breakers + orchestrator…", flush=True)
        try:
            from services.breakers import attach_db_listeners
            attach_db_listeners(db)
            print("[STARTUP] ✓ Breaker DB listeners attached", flush=True)
        except Exception as _e:
            print(f"[STARTUP] ✗ Breakers attach failed: {_e}", flush=True)

        try:
            from services.pillar_orchestrator import PillarOrchestrator
            # Redis client for heartbeat keys (sync client — safe for setex)
            try:
                from utils.redis_pool import get_sync_redis
                _redis_sync = get_sync_redis()
            except Exception:
                _redis_sync = None

            _orch = PillarOrchestrator(db, _redis_sync)

            # Each pillar is wrapped as a long-lived coroutine that kicks off
            # the existing start_pillarN_worker() WITH closure factories so
            # all factory-based schedulers (Health Score, Daily Digest,
            # Orchestrator Digest, Operational Alerts, WhatsApp CRM, Monthly
            # Cleanup, Daily Client Scan, Auto-Repair, etc.) attach. Without
            # these, only ~16/24 Pillar 4 schedulers were running.
            async def _pillar_forever(start_fn, *args, **kwargs):
                try:
                    start_fn(*args, **kwargs)
                except Exception as e:
                    logging.warning(f"[orchestrator] start_fn raised: {e}")
                    raise
                # Park forever — start_fn already spawned child tasks.
                await asyncio.Event().wait()

            # Lazy-import factory closures so we have them in scope below.
            try:
                from services.startup_init import (
                    daily_digest_scheduler as _f_daily_digest,
                    operational_alerts_scheduler as _f_op_alerts,
                    whatsapp_crm_scheduler as _f_whatsapp,
                    orchestrator_digest_scheduler as _f_orch_digest,
                    auto_repair_scheduler as _f_auto_repair,
                    monthly_data_cleanup_scheduler as _f_monthly_cleanup,
                    _daily_client_scan_loop as _f_daily_client_scan,
                    _health_score_scheduler as _f_health_score,
                    abandoned_cart_scheduler as _f_abandoned_cart,
                    day21_review_scheduler as _f_day21,
                    birthday_bonus_scheduler as _f_birthday,
                    aurem_morning_scheduler as _f_aurem_morning,
                    _news_monitor_scheduler as _f_news_monitor,
                )
            except Exception as _ie:
                logging.warning(f"[orchestrator] factory import skipped: {_ie}")
                _f_daily_digest = _f_op_alerts = _f_whatsapp = None
                _f_orch_digest = _f_auto_repair = _f_monthly_cleanup = None
                _f_daily_client_scan = _f_health_score = None
                _f_abandoned_cart = _f_day21 = _f_birthday = None
                _f_aurem_morning = _f_news_monitor = None

            try:
                from pillars.sales.worker import start_pillar1_worker
                _orch.register("scout", lambda: _pillar_forever(
                    start_pillar1_worker, db,
                    news_monitor_coro_factory=(lambda: _f_news_monitor(db)) if _f_news_monitor else None,
                ))
            except Exception as _e:
                logging.warning(f"[orchestrator] pillar1 register skipped: {_e}")
            try:
                from pillars.billing.worker import start_pillar2_worker
                _orch.register("envoy", lambda: _pillar_forever(
                    start_pillar2_worker, db,
                    # iter 322p — abandoned_cart / day21 / birthday factories
                    # removed: their underlying schedulers are deprecated no-op
                    # stubs (iter 322h) that return immediately, leaving zombie
                    # task names that flip aurem_abandoned_carts / payment_reminders
                    # backend pulse to red. The pillars-map writer mappings have
                    # been updated accordingly.
                    abandoned_cart_coro_factory=None,
                    day21_coro_factory=None,
                    birthday_coro_factory=None,
                    aurem_morning_coro_factory=(lambda: _f_aurem_morning(db)) if _f_aurem_morning else None,
                ))
            except Exception as _e:
                logging.warning(f"[orchestrator] pillar2 register skipped: {_e}")
            try:
                from pillars.site_monitor.worker import start_pillar3_worker
                _orch.register("sentinel", lambda: _pillar_forever(start_pillar3_worker, db))
            except Exception as _e:
                logging.warning(f"[orchestrator] pillar3 register skipped: {_e}")
            try:
                from pillars.command_hub.worker import start_pillar4_worker
                _orch.register("closer", lambda: _pillar_forever(
                    start_pillar4_worker, db,
                    daily_digest_coro_factory=_f_daily_digest,
                    operational_alerts_coro_factory=_f_op_alerts,
                    whatsapp_crm_coro_factory=_f_whatsapp,
                    orchestrator_digest_coro_factory=_f_orch_digest,
                    auto_repair_coro_factory=_f_auto_repair,
                    monthly_cleanup_coro_factory=_f_monthly_cleanup,
                    daily_client_scan_coro_factory=_f_daily_client_scan,
                    health_score_coro_factory=(lambda: _f_health_score(db)) if _f_health_score else None,
                ))
            except Exception as _e:
                logging.warning(f"[orchestrator] pillar4 register skipped: {_e}")

            app.state.orchestrator = _orch
            # iter 322m — DEFERRED orchestrator launch to keep K8s liveness
            # probes (`/health`, 10s nginx upstream timeout) green during
            # cold boot. Heavy lazy imports + 30+ scheduler first-tick I/O
            # were saturating the event loop and killing the pod.
            _ORCH_BOOT_DELAY_S = float(os.environ.get("SCHED_BOOT_DELAY_S", "25"))

            async def _deferred_orch_run():
                await asyncio.sleep(_ORCH_BOOT_DELAY_S)
                logging.info(
                    f"[orchestrator] starting after T+{_ORCH_BOOT_DELAY_S}s grace"
                )
                try:
                    await _orch.run()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logging.error(f"[orchestrator] run failed: {e}")

            app.state.orch_task = asyncio.create_task(
                _deferred_orch_run(), name="orchestrator_main",
            )
            print(
                f"[STARTUP] ✓ PillarOrchestrator armed — {len(_orch._fns)} pillars "
                f"(launches at T+{_ORCH_BOOT_DELAY_S}s)",
                flush=True,
            )
        except Exception as _e:
            print(f"[STARTUP] ✗ Orchestrator init failed: {_e}", flush=True)

        logging.info(f"✅ ReRoots API startup complete in {time.time()-startup_start:.2f}s - ready to serve requests")
        
    except Exception as e:
        logging.error(f"❌ STARTUP FAILED: {e}")
        logging.error(traceback.format_exc())
        # Don't raise - let server continue for health checks
        logging.warning("Server continuing despite startup errors")
    
    # Run heavy tasks in background (don't block startup).
    # Extracted to bootstrap/background_init.py (iter 264).
    from bootstrap.background_init import run_background_init as _run_bg_init

    asyncio.create_task(
        _run_bg_init(
            db,
            create_indexes_fn=create_indexes,
            setup_database_indexes_fn=setup_database_indexes,
            seed_business_system_data_fn=seed_business_system_data,
            start_crypto_tasks_fn=start_crypto_tasks,
        )
    )
    
    # ═══ BACKGROUND SCHEDULERS — handled by PillarOrchestrator above ═══
    # iter 322m: scheduler launch is now owned by `_deferred_orch_run`
    # registered in startup_event above. It launches all 4 pillar workers
    # WITH closure factories (24+ schedulers) after T+SCHED_BOOT_DELAY_S
    # seconds, keeping K8s `/health` probes green during cold boot.
    #
    # The legacy direct call to start_all_background_schedulers(db) is
    # left only for the post-launch migration tasks (dry_run cleanup,
    # lifecycle backfill, pixel/trial reminders) — those are scheduled
    # below as small standalone tasks instead of via the legacy launcher.
    async def _deferred_post_orch_tasks():
        # Wait until the orchestrator boot has had time to attach pillars.
        _delay = float(os.environ.get("SCHED_BOOT_DELAY_S", "25")) + 8.0
        await asyncio.sleep(_delay)
        try:
            from services.startup_init import (
                _safe_task as _si_safe_task,
                _pixel_install_reminder_loop,
                _trial_expiry_reminder_loop,
            )

            async def _dry_run_cleanup_migration():
                try:
                    r1 = await db.agent_state.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
                    r2 = await db.agent_config.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
                    r3 = await db.campaign_leads.update_many({"status": "dry_run"}, {"$set": {"status": "new"}})
                    r4 = await db.campaign_leads.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
                    r5 = await db.hunt_commands.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
                    r6 = await db.agent_feed.update_many({"dry_run": {"$exists": True}}, {"$unset": {"dry_run": ""}})
                    touched = (r1.modified_count + r2.modified_count + r3.modified_count +
                               r4.modified_count + r5.modified_count + r6.modified_count)
                    if touched:
                        logging.info(f"[STARTUP] Dry-run cleanup migration: {touched} docs updated")
                except Exception as e:
                    logging.warning(f"[STARTUP] Dry-run cleanup migration skipped: {e}")
            _si_safe_task(_dry_run_cleanup_migration(), "dry_run_cleanup_migration")

            async def _lifecycle_backfill_migration():
                try:
                    from services.lead_lifecycle import backfill_lifecycle_stages
                    result = await backfill_lifecycle_stages(db, dry_run=False)
                    if result.get("updated", 0) > 0:
                        logging.info(f"[STARTUP] Lifecycle backfill: {result['updated']} leads → {result['counts']}")
                except Exception as e:
                    logging.warning(f"[STARTUP] Lifecycle backfill skipped: {e}")
            _si_safe_task(_lifecycle_backfill_migration(), "lifecycle_backfill_migration")

            _si_safe_task(_pixel_install_reminder_loop(db), "pixel_install_reminder_loop")
            _si_safe_task(_trial_expiry_reminder_loop(db), "trial_expiry_reminder_loop")
            # iter 322et — ORA morning brief at 6 AM Toronto
            _si_safe_task(daily_ora_morning_brief(), "ora_morning_brief_6am_toronto")
            logging.info("[STARTUP] post-orchestrator migration + reminder tasks armed")
        except Exception as _e:
            logging.warning(f"[STARTUP] post-orchestrator tasks failed: {_e}")

    asyncio.create_task(_deferred_post_orch_tasks())

    # ═══ Iter 288.5 — Autopilot Sentinel Watchdog ═══
    try:
        from services.autopilot_sentinel import set_db as _sentinel_set_db, sentinel_loop
        _sentinel_set_db(db)
        asyncio.create_task(sentinel_loop(interval_seconds=300))
        logging.info("[Sentinel] Watchdog scheduled (60s interval, 07:55–10:00 Toronto window)")
    except Exception as e:
        logging.warning(f"[Sentinel] failed to start: {e}")

    # ═══ Iter 322j — Sovereign Watchdog (continuous self-heal + Council) ═══
    try:
        from services.sovereign_watchdog import start_watchdog
        if start_watchdog(db):
            logging.info("[Sovereign Watchdog] online — log scan + Council auto-fix loop running")
    except Exception as e:
        logging.warning(f"[Sovereign Watchdog] failed to start: {e}")

    # ═══ Iter 322l — Day 2 Sovereign Discipline ═══
    try:
        from services.council_rotation import start_council_rotation
        if start_council_rotation(db):
            logging.info("[Council Rotation] online — self-driving 2-stamp reviewer")
    except Exception as e:
        logging.warning(f"[Council Rotation] failed to start: {e}")
    try:
        from services.pillar_restart_fulfiller import start_pillar_fulfiller
        if start_pillar_fulfiller(db):
            logging.info("[Pillar Fulfiller] online — auto-restart dead pillars")
    except Exception as e:
        logging.warning(f"[Pillar Fulfiller] failed to start: {e}")

    # ═══ ITER 322p — yield event loop before heavy scheduler boot ═══
    # The `asyncio.create_task(...)` blocks below collectively perform ~15
    # lazy module imports (each holds the GIL) inside startup_event and
    # starve the /health ASGI shim during cold-Atlas boot. We add explicit
    # `await asyncio.sleep(0)` yield points between blocks so K8s probes
    # can interleave with imports.
    _POST_BOOT_DELAY_S = float(os.environ.get("POST_BOOT_DELAY_S", "0.5"))
    if _POST_BOOT_DELAY_S > 0:
        await asyncio.sleep(_POST_BOOT_DELAY_S)

    # ═══ Iter 303 — Zero-Downtime Repair: post-restart state restore ═══
    try:
        from services.zero_downtime_repair import post_repair_restore
        async def _zdr_restore():
            try:
                res = await post_repair_restore(db)
                logging.info(f"[ZDR] post-repair restore: {res}")
            except Exception as e:
                logging.warning(f"[ZDR] restore skipped: {e}")
        asyncio.create_task(_zdr_restore())
    except Exception as e:
        logging.warning(f"[ZDR] init skipped: {e}")

    # ═══ Iter 322p — Weekend Warmth (Sat 9AM warm msg, Sun 8AM quote) ═══
    try:
        from services.weekend_warmth import (
            set_db as _ww_set_db,
            weekend_warmth_scheduler as _ww_scheduler,
            ensure_indexes as _ww_ensure_indexes,
        )
        _ww_set_db(db)
        asyncio.create_task(_ww_ensure_indexes())
        asyncio.create_task(_ww_scheduler())
        logging.info("[WeekendWarmth] hourly tick scheduled (Sat 9AM + Sun 8AM local)")
    except Exception as e:
        logging.warning(f"[WeekendWarmth] failed to start: {e}")

    # ═══ Iter 322p — Scout enrichment indexes (Section 3) ═══
    try:
        from services.scout_enrichment import ensure_indexes as _se_idx
        asyncio.create_task(_se_idx(db))
    except Exception as e:
        logging.warning(f"[ScoutEnrichment] index ensure skipped: {e}")

    # ═══ Iter 322p — Lead Sort indexes (Section 4) ═══
    try:
        from services.lead_sort import ensure_indexes as _sort_idx
        asyncio.create_task(_sort_idx(db))
    except Exception as e:
        logging.warning(f"[LeadSort] index ensure skipped: {e}")

    # ═══ Iter 304 — Website Repair Outreach (every 10 min) ═══
    try:
        from services.repair_outreach import (
            set_db as _ro_set_db, repair_outreach_scheduler,
        )
        _ro_set_db(db)
        asyncio.create_task(repair_outreach_scheduler())
        logging.info("[RepairOutreach] scheduler armed — fires website_repair_offer "
                     "for leads with audit_score<60")
    except Exception as e:
        logging.warning(f"[RepairOutreach] failed to start: {e}")

    # ═══ Iter 302 → Iter 282m — DISABLED. Replaced by services/founder_daily_brief.py
    # which uses ORA Web Push (VAPID) + a single 6 PM Resend email — NO WhatsApp.
    # See routers/registry.py for the new APScheduler jobs.
    # ════════════════════════════════════════════════════════════════════

    # ═══ Iter 311 — Monday Morning Brief (Mon 7 AM Toronto) ═══
    async def _monday_brief_scheduler():
        import asyncio as _a
        await _a.sleep(120)  # let other startup settle
        from services.monday_brief import maybe_send_monday_brief
        while True:
            try:
                await maybe_send_monday_brief(db)
            except Exception as e:
                logging.warning(f"[MondayBrief] tick failed: {e}")
            await _a.sleep(3600)  # hourly tick
    try:
        asyncio.create_task(_monday_brief_scheduler())
        logging.info("[MondayBrief] hourly scheduler attached (fires Mon 7 AM TO)")
    except Exception as e:
        logging.warning(f"[MondayBrief] failed to start: {e}")

    # ═══ Iter 313 — Sunday Founder's Forecast (Sun 8 PM Toronto) ═══
    async def _sunday_forecast_scheduler():
        import asyncio as _a
        await _a.sleep(150)
        from services.sunday_forecast import maybe_send_forecast
        while True:
            try:
                await maybe_send_forecast(db)
            except Exception as e:
                logging.warning(f"[SundayForecast] tick failed: {e}")
            await _a.sleep(3600)
    try:
        asyncio.create_task(_sunday_forecast_scheduler())
        logging.info("[SundayForecast] hourly scheduler attached (fires Sun 8 PM TO)")
    except Exception as e:
        logging.warning(f"[SundayForecast] failed to start: {e}")

    # ═══ Iter 314 — Forecast Campaign Dispatcher (Mon 9 AM Toronto) ═══
    async def _forecast_campaign_dispatcher():
        import asyncio as _a
        await _a.sleep(180)
        from services.forecast_campaigns import (
            dispatch_due_forecast_campaigns,
        )
        while True:
            try:
                out = await dispatch_due_forecast_campaigns(db)
                if out.get("count"):
                    logging.info(f"[ForecastCamp] fired {out['count']} campaigns")
            except Exception as e:
                logging.warning(f"[ForecastCamp] tick failed: {e}")
            await _a.sleep(900)  # 15 min — tighter so Mon 9 AM hits cleanly
    try:
        asyncio.create_task(_forecast_campaign_dispatcher())
        logging.info("[ForecastCamp] 15-min dispatcher attached")
    except Exception as e:
        logging.warning(f"[ForecastCamp] failed to start: {e}")

    # ═══ Iter 315b — Post-Publish Triggers (welcome + 2h domain upsell) ═══
    try:
        from services.post_publish_triggers import post_publish_scheduler
        asyncio.create_task(post_publish_scheduler(db))
        logging.info("[PostPublish] welcome + 2h upsell scheduler attached")
    except Exception as e:
        logging.warning(f"[PostPublish] failed to start: {e}")

    # ═══ Iter 315d — NPS Win-back sequence scheduler ═══
    try:
        from services.winback_sequence import winback_scheduler
        asyncio.create_task(winback_scheduler(db))
        logging.info("[Winback] NPS detractor 3-step sequence scheduler attached")
    except Exception as e:
        logging.warning(f"[Winback] failed to start: {e}")

    # ═══ Iter 315e — Payment Funnel Audit (nightly midnight Toronto) ═══
    try:
        from services.payment_funnel_audit import payment_audit_scheduler
        asyncio.create_task(payment_audit_scheduler())
        logging.info("[PaymentAudit] nightly Stripe reconciliation scheduler attached")
    except Exception as e:
        logging.warning(f"[PaymentAudit] failed to start: {e}")

    # ═══ Iter 315i — Armed Outreach (ORA-armed blast, fires on schedule) ═══
    try:
        from services.armed_outreach import armed_outreach_scheduler
        asyncio.create_task(armed_outreach_scheduler(db))
        logging.info("[ArmedOutreach] scheduler attached — fires due armed campaigns every 5 min")
    except Exception as e:
        logging.warning(f"[ArmedOutreach] failed to start: {e}")

    # ═══ Iter 282b — AWB Safety: index ensure + daily duplicate check ═══
    # iter 282al-19 — index creation scheduled in background to keep startup
    # under the K8s liveness-probe budget on cold Atlas.
    try:
        from services.awb_safety import ensure_indexes as _awb_ensure_indexes
        from services.awb_safety import awb_safety_scheduler
        asyncio.create_task(_awb_ensure_indexes(db))
        asyncio.create_task(awb_safety_scheduler(db))
        logging.info("[AwbSafety] unique-index ensure + daily 03:00 UTC duplicate-check scheduler scheduled in bg")
    except Exception as e:
        logging.warning(f"[AwbSafety] failed to start: {e}")

    # Sovereign Warmer — keep Legion ngrok tunnel warm (cold ~20s → ~800ms)
    try:
        from services.sovereign_warmer import sovereign_warmer_loop
        asyncio.create_task(sovereign_warmer_loop())
        logging.info("[SovereignWarmer] scheduler attached — pings /api/tags every 4 min")
    except Exception as e:
        logging.warning(f"[SovereignWarmer] failed to start: {e}")

    # Endpoint Heartbeat — keeps Pillars-Map Evidence Classifier honest by
    # synthetically pinging every safe GET every 4 h, populating
    # api_audit_log so endpoints can't drift to "leaky" without cause.
    try:
        from services.endpoint_heartbeat import heartbeat_loop
        asyncio.create_task(heartbeat_loop(db))
        logging.info("[EndpointHeartbeat] scheduler attached — every 4 h")
    except Exception as e:
        logging.warning(f"[EndpointHeartbeat] failed to start: {e}")

    # Unified Inbox indexes (used by /api/customer/inbox/*) — bg to never block startup
    try:
        from services.inbox_writer import ensure_indexes as _ensure_inbox_idx
        asyncio.create_task(_ensure_inbox_idx(db))
    except Exception as e:
        logging.warning(f"[InboxWriter] index ensure failed: {e}")

    # BIN Intelligence — indexes + 15-min merge loop + 30-min promote loop (Part 5)
    try:
        from services.bin_intelligence import (
            ensure_indexes as _ensure_intel_idx,
            merge_loop as _intel_merge_loop,
            promote_loop as _intel_promote_loop,
        )
        asyncio.create_task(_ensure_intel_idx(db))
        asyncio.create_task(_intel_merge_loop(db))
        asyncio.create_task(_intel_promote_loop(db))
        logging.info("[BinIntelligence] indexes + merge (15m) + promote (30m) loops scheduled in bg")
    except Exception as e:
        logging.warning(f"[BinIntelligence] startup failed: {e}")

    # ═══ Iter 282al-15 — Site QA (test-lab.ai) TTL indexes ═══
    # iter 282al-19 — defer to background so cold Atlas can't push startup
    # past the K8s liveness-probe budget. Indexes are idempotent.
    try:
        from services.site_qa_service import ensure_site_qa_indexes
        asyncio.create_task(ensure_site_qa_indexes(db))
        logging.info("[SiteQA] TTL index ensure scheduled in background")
    except Exception as e:
        logging.warning(f"[SiteQA] index ensure scheduling failed: {e}")

    # ═══ Iter 282al-21 — ORA God-Mode Brain TTLs (90d/365d) ═══
    try:
        from services.ora_god_mode import ensure_brain_indexes
        asyncio.create_task(ensure_brain_indexes(db))
        logging.info("[OraBrain] TTL index ensure scheduled in background")
    except Exception as e:
        logging.warning(f"[OraBrain] index ensure scheduling failed: {e}")

    # ═══ Iter 282al-23 — Scrapling Warmup (top-100 domains pre-fetch) ═══
    try:
        from services.scrapling_warmup import (
            run_scrapling_warmup,
            ensure_warmup_indexes,
        )
        asyncio.create_task(ensure_warmup_indexes(db))

        async def _delayed_warmup():
            # Iter 282al-24 — production hardening:
            # Wait long enough for K8s liveness probes to mark the pod
            # ready and for cold-start work to settle, then run a small
            # warmup wrapped in a hard timeout so a hung Playwright
            # session can never starve the event loop.
            await asyncio.sleep(180)
            try:
                # Cap at 25 domains on first warmup (the 6h scheduler
                # runs the full top-100). Hard timeout 90s.
                out = await asyncio.wait_for(
                    run_scrapling_warmup(db, max_domains=25, concurrency=3),
                    timeout=90.0,
                )
                logging.info(
                    f"[ScraplingWarmup] startup warm: "
                    f"{out.get('warmed')}/{out.get('considered')} ok={out.get('ok')}"
                )
            except asyncio.TimeoutError:
                logging.warning("[ScraplingWarmup] startup warm timed out (90s) — skipped")
            except Exception as _e:
                logging.warning(f"[ScraplingWarmup] startup warm failed: {_e}")

        asyncio.create_task(_delayed_warmup())
        logging.info("[ScraplingWarmup] startup warm scheduled (T+180s, top-25, 90s cap)")
    except Exception as e:
        logging.warning(f"[ScraplingWarmup] startup hook failed: {e}")

    logging.info("AUREM API ready (background tasks running)")

# ============= AUTOMATED CRON JOBS (Extracted to services/cron_schedulers.py) =============
from services.cron_schedulers import (
    daily_stock_alert_scheduler,
    weekly_revenue_summary_scheduler,
    cnf_reminder_scheduler,
    daily_ora_morning_brief,
    set_db as set_cron_db,
)


# ============= SMS NOTIFICATION SYSTEM (Kept in server.py — used by inline code) =============
# SMS functions (send_sms_verification, verify_sms_code, send_sms_notification) remain here
# as they depend on module-level twilio_client. They are referenced by the extracted misc routes
# via fallback imports.


# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# ============= RLS (Row Level Security) HELPERS =============

async def get_rls_context(
    request: Request,
    x_brand_id: Optional[str] = Header(None, alias="X-Brand-ID")
) -> RLSContext:
    """
    Dependency to get RLS context from request.
    Extracts brand_id from header and validates admin access.
    """
    admin_user = None
    
    # Try to get admin user from token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("user_id")
            if user_id:
                user_doc = await db.admin_users.find_one({"id": user_id}, {"_id": 0})
                if user_doc:
                    admin_user = AdminUser(**user_doc)
        except jwt.InvalidTokenError:
            pass
    
    return RLSContext(admin_user=admin_user, brand_id=x_brand_id)


def apply_brand_filter(query: dict, rls: RLSContext, collection_name: str = None) -> dict:
    """Apply brand filter to a MongoDB query"""
    brand_filter = rls.get_query_filter(collection_name)
    if brand_filter:
        return {**query, **brand_filter}
    return query


# ============= INLINE ROUTES (Extracted to routers/server_misc_routes.py) =============
# WebSocket, SSE, User Address, Password Reset, Phone Login, Product CRUD,
# Admin AI Assistant, WhatsApp Validate — all moved to server_misc_routes.py
from routers.server_misc_routes import router as server_misc_router, set_deps as set_misc_deps, push_sse_event

# ═══ ROUTER REGISTRY (Extracted to routers/registry.py) ═══
from routers.registry import register_all_routers
# All include_router() calls are in register_all_routers(app, db)
# Called from startup_event() after db initialization

# Note: api_router is included here because it holds RLS endpoints
app.include_router(api_router)

# iter 322ey — Founder Saves Audit Router (direct register; registry block
# wasn't being reached after hot-reload, so wire it here as a safety net).
try:
    from routers.founder_saves_router import (
        router as _founder_saves_router,
        set_db as _set_founder_saves_db,
    )
    # db wiring deferred until startup_event() runs and `db` is bound,
    # but include the router immediately so routes register.
    app.include_router(_founder_saves_router)

    @app.on_event("startup")
    async def _wire_founder_saves_db():
        # Late-bind the db handle once it's initialized.
        from server import db as _bound_db  # type: ignore
        _set_founder_saves_db(_bound_db)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] founder_saves_router wire failed: {_e}")

# iter 322ey — Public Design-Extract lead magnet (NO auth)
try:
    from routers.design_extract_public_router import (
        router as _design_extract_public_router,
        set_db as _set_dep_db,
    )
    app.include_router(_design_extract_public_router)

    @app.on_event("startup")
    async def _wire_design_extract_public_db():
        from server import db as _bound_db  # type: ignore
        _set_dep_db(_bound_db)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] design_extract_public wire failed: {_e}")

# iter 322ez — Ghost Protocol Scout (Camoufox + Bezier/Markov behavior + cold storage)
try:
    from routers.scout_ghost_router import (
        router as _scout_ghost_router,
        set_db as _set_ghost_db,
    )
    app.include_router(_scout_ghost_router)

    @app.on_event("startup")
    async def _wire_scout_ghost_db():
        from server import db as _bound_db  # type: ignore
        _set_ghost_db(_bound_db)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] scout_ghost wire failed: {_e}")

# iter 322fa — Legion Bridge (reverse-poll daemon queue → ORA controls Legion)
try:
    from routers.legion_queue_router import (
        router as _legion_queue_router,
        bootstrap_router as _legion_bootstrap_router,
        set_db as _set_legion_db,
    )
    app.include_router(_legion_queue_router)
    app.include_router(_legion_bootstrap_router)

    @app.on_event("startup")
    async def _wire_legion_db():
        from server import db as _bound_db  # type: ignore
        _set_legion_db(_bound_db)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] legion_queue wire failed: {_e}")

# iter 322g+ — System uptime endpoint (revenue heartbeat from phone)
try:
    from routers.system_uptime_router import (
        router as _system_uptime_router,
        set_db as _set_uptime_db,
    )
    app.include_router(_system_uptime_router)

    @app.on_event("startup")
    async def _wire_uptime_db():
        from server import db as _bound_db  # type: ignore
        _set_uptime_db(_bound_db)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] system_uptime wire failed: {_e}")

# iter 322g+ — CSV/JSON manual leads upload (founder bulk-prospect ingest)
try:
    from routers.csv_leads_upload_router import (
        router as _csv_leads_router,
        set_db as _set_csv_db,
    )
    app.include_router(_csv_leads_router)

    @app.on_event("startup")
    async def _wire_csv_leads_db():
        from server import db as _bound_db  # type: ignore
        _set_csv_db(_bound_db)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] csv_leads wire failed: {_e}")

# iter 324 — startup env-var report (admin diagnostic)
try:
    from routers.startup_report_router import router as _startup_report_router
    app.include_router(_startup_report_router)
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] startup_report wire failed: {_e}")

# iter 322g+ — Ghost Scout (IPRoyal residential proxy + Google Places harvest)
try:
    from routers.ghost_scout_router import (
        router as _ghost_scout_router,
        set_db as _set_ghost_scout_db,
    )
    app.include_router(_ghost_scout_router)

    @app.on_event("startup")
    async def _wire_ghost_scout():
        from server import db as _bound_db  # type: ignore
        _set_ghost_scout_db(_bound_db)
        # Start the autonomous harvest loop (gracefully exits if IPROYAL not set)
        try:
            import asyncio as _aio
            from services.ghost_scout_iproyal import ghost_scout_loop
            _aio.create_task(ghost_scout_loop())
        except Exception as __e:
            import logging as __lg
            __lg.getLogger(__name__).warning(f"[ghost-scout] loop start failed: {__e}")
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] ghost_scout wire failed: {_e}")

# iter 324j — Scout Diagnose Router (live health-check + OSM emergency hunt)
try:
    from routers.scout_diagnose_router import (
        router as _scout_diagnose_router,
        set_db as _set_scout_diagnose_db,
    )
    app.include_router(_scout_diagnose_router)

    @app.on_event("startup")
    async def _wire_scout_diagnose():
        from server import db as _bound_db  # type: ignore
        _set_scout_diagnose_db(_bound_db)
        # iter 324l — also wire the replenish-cron DB so /cron-trigger works.
        try:
            from services.scout_replenish_cron import set_db as _set_cron_db
            _set_cron_db(_bound_db)
        except Exception as _err:
            import logging as _l2
            _l2.getLogger(__name__).warning(f"[INLINE] scout_replenish_cron DB wire failed: {_err}")
except Exception as _e:
    import logging as _lg
    _lg.getLogger(__name__).warning(f"[INLINE] scout_diagnose wire failed: {_e}")

# /.well-known/ucp moved to bootstrap.wellknown_routes (iter 263 final surgery).

# Serve standalone tracking pixel
from fastapi.staticfiles import StaticFiles
import os as _os
_pixel_dir = _os.path.join(_os.path.dirname(__file__), "static")
if _os.path.isdir(_pixel_dir):
    # Serve pixel JS file at /api/pixel/aurem-pixel.js via explicit route
    # (avoids StaticFiles swallowing /api/pixel/patches* dynamic routes)
    from fastapi.responses import FileResponse as _FR
    _pixel_js_path = _os.path.join(_pixel_dir, "aurem-pixel.js")
    if _os.path.isfile(_pixel_js_path):
        @app.get("/api/pixel/aurem-pixel.js", include_in_schema=False)
        async def _serve_aurem_pixel():
            return _FR(_pixel_js_path, media_type="application/javascript")
    # Static /api/static/* for monthly reports + artifacts
    app.mount("/api/static", StaticFiles(directory=_pixel_dir), name="customer_static")
    # WordPress plugin download — friendly one-click URL
    _wp_zip_path = _os.path.join(_pixel_dir, "plugins", "aurem-pixel.zip")
    if _os.path.isfile(_wp_zip_path):
        @app.get("/api/plugins/wordpress", include_in_schema=False)
        async def _serve_wp_plugin():
            return _FR(_wp_zip_path, media_type="application/zip", filename="aurem-pixel.zip")
    print("[STARTUP] Pixel JS served at /api/pixel/aurem-pixel.js; static files at /api/static/")

    # Lock-in validator — warns loudly if any Iter 256 production build regressed
    try:
        from services.lock_in_validator import validate_locked_builds
        _lock_result = validate_locked_builds()
        if _lock_result["ok"]:
            print(f"[STARTUP] 🔒 Lock-in: ✅ all 13 locked builds + 9 env vars present", flush=True)
        else:
            print(f"[STARTUP] 🔒 Lock-in: ❌ REGRESSION — missing_files={len(_lock_result['missing_files'])} missing_env={len(_lock_result['missing_env'])} resurrected={len(_lock_result['resurrected'])}", flush=True)
    except Exception as _lock_err:
        print(f"[STARTUP] 🔒 Lock-in: validator error → {_lock_err}", flush=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Silence noisy third-party library warnings that are upstream bugs we cannot fix
# and don't affect our app behaviour. Each is safe to suppress because:
#   - ddgs.engines.yahoo_news: library throws IndexError on empty search results;
#     our news_monitor already falls back to the text-search path when this happens.
#   - litellm.info banner: prints on every LLM error; we already log at call sites.
logging.getLogger("ddgs.engines.yahoo_news").setLevel(logging.ERROR)
logging.getLogger("ddgs.engines.google_news").setLevel(logging.ERROR)

# Default images + cleanup_broken_images extracted to bootstrap/image_cleanup.py
# (iter 264 final surgery). Kept re-export below so any stray callers keep working.
from bootstrap.image_cleanup import cleanup_broken_images, DEFAULT_IMAGES  # noqa: F401


# Blog indexes are created in the main startup_event background task


@app.on_event("shutdown")
async def shutdown_db_client():
    # Cancel pillar orchestrator first (clean shutdown of supervised tasks)
    try:
        if hasattr(app.state, "orchestrator"):
            await app.state.orchestrator.stop_all()
        if hasattr(app.state, "orch_task") and not app.state.orch_task.done():
            app.state.orch_task.cancel()
        logging.info("✓ Pillar orchestrator stopped")
    except Exception as e:
        logging.warning(f"Orchestrator shutdown error: {e}")

    # Close browser toolkit
    try:
        from services.whatsapp_ai_assistant import shutdown_browser
        await shutdown_browser()
        logging.info("✓ Browser toolkit closed")
    except Exception as e:
        logging.warning(f"Browser toolkit shutdown error: {e}")
    
    # Close cache manager
    try:
        await cache_manager.disconnect()
        logging.info("✓ Cache manager closed")
    except Exception as e:
        logging.warning(f"Cache manager shutdown error: {e}")

    # Close shared Redis pool (utils.redis_pool)
    try:
        from utils.redis_pool import close_pools
        await close_pools()
    except Exception as e:
        logging.warning(f"Shared Redis pool shutdown error: {e}")
    
    # Close auth HTTP client
    global _auth_client
    if _auth_client and not _auth_client.is_closed:
        await _auth_client.aclose()
        logging.info("✓ Auth HTTP client closed")
    
    # Close MongoDB client
    if client is not None:
        client.close()
        logging.info("Database connection closed")
