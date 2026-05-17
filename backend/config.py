"""
Shared configuration and database connection for all modules.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv(override=False)

# Database Configuration - NO localhost fallback for production safety
# Don't raise at import time - let the app start so health checks can respond
MONGO_URL = os.environ.get("MONGO_URL")
if not MONGO_URL:
    logging.warning("MONGO_URL not set - database operations will fail until configured")
    
DB_NAME = os.environ.get("DB_NAME")
if not DB_NAME:
    # Bug-fix: previously `os.environ.get("DB_NAME")` returned None when
    # unset, and `client[None]` made Motor silently write to a database
    # literally named "None" (str(None)). Fail loudly instead.
    raise RuntimeError(
        "DB_NAME environment variable is required — refusing to start "
        "with a database named 'None'."
    )

# JWT Configuration — Must not CRASH the server just because the env
# var is missing. If uvicorn's module import raises at load time, the pod
# never binds port 8001 and K8s health probes get ECONNREFUSED (111).
#
# Three-tier resolution (iter 272):
#   1. JWT_SECRET env var   (preferred — production; set by operator)
#   2. /app/.jwt_secret     (persisted fallback — survives pod restarts)
#   3. generate + persist   (first boot; writes file with 0600 perms)
#
# This makes sessions survive pod restarts even when env var isn't set —
# admins stop getting random "Signature has expired" re-logins.
JWT_SECRET = os.environ.get("JWT_SECRET")
_JWT_SECRET_SOURCE = "env"

if not JWT_SECRET:
    _JWT_SECRET_FILE = "/app/.jwt_secret"
    try:
        if os.path.exists(_JWT_SECRET_FILE):
            with open(_JWT_SECRET_FILE, "r", encoding="utf-8") as _fh:
                JWT_SECRET = _fh.read().strip()
            if JWT_SECRET:
                _JWT_SECRET_SOURCE = "file"
                logging.warning(
                    "⚠ JWT_SECRET env var not set — loaded persisted secret "
                    "from %s. Set the env var in production for security.",
                    _JWT_SECRET_FILE,
                )
        if not JWT_SECRET:
            import secrets as _secrets
            JWT_SECRET = _secrets.token_urlsafe(48)
            try:
                with open(_JWT_SECRET_FILE, "w", encoding="utf-8") as _fh:
                    _fh.write(JWT_SECRET)
                os.chmod(_JWT_SECRET_FILE, 0o600)
                _JWT_SECRET_SOURCE = "file-new"
                logging.warning(
                    "⚠ JWT_SECRET generated and persisted to %s (0600). "
                    "Sessions will survive pod restarts. "
                    "Set JWT_SECRET env var in production for full control.",
                    _JWT_SECRET_FILE,
                )
            except Exception as _e:
                _JWT_SECRET_SOURCE = "ephemeral"
                logging.error(
                    "⚠ JWT_SECRET env missing AND failed to persist (%s). "
                    "Using ephemeral secret — tokens will be invalidated on "
                    "every pod restart. Fix JWT_SECRET in env immediately.", _e,
                )
    except Exception as _outer:
        import secrets as _secrets
        JWT_SECRET = _secrets.token_urlsafe(48)
        _JWT_SECRET_SOURCE = "ephemeral"
        logging.error("JWT secret resolution fell through (%s) — using ephemeral.", _outer)

JWT_ALGORITHM = "HS256"

# API Keys
STRIPE_API_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET = os.environ.get("PAYPAL_SECRET", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Database client (singleton)
_client = None
_db = None

def get_database():
    """Get database instance (creates connection if needed)"""
    global _client, _db
    if _db is None:
        if not MONGO_URL:
            raise RuntimeError("Cannot connect to database: MONGO_URL not configured")
        # Import here to avoid any potential import-time side effects
        from motor.motor_asyncio import AsyncIOMotorClient as MotorClient
        _client = MotorClient(
            MONGO_URL,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=20000,
            socketTimeoutMS=30000,
            maxPoolSize=50,
            retryWrites=True,
            connect=False,  # Don't verify connection at creation time
        )
        _db = _client[DB_NAME]
    return _db

# Convenience accessor
db = None

def init_database():
    """Initialize database connection"""
    global db
    db = get_database()
    return db
