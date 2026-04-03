"""
Shared configuration and database connection for all modules.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Database Configuration - NO localhost fallback for production safety
# Don't raise at import time - let the app start so health checks can respond
MONGO_URL = os.environ.get("MONGO_URL")
if not MONGO_URL:
    logging.warning("MONGO_URL not set - database operations will fail until configured")
    
DB_NAME = os.environ.get("DB_NAME", "reroots_db")

# JWT Configuration
JWT_SECRET = os.environ.get("JWT_SECRET", "reroots-secret-key")
JWT_ALGORITHM = "HS256"

# API Keys
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
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
