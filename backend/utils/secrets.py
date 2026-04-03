"""
Secrets Manager for Reroots
Centralized secrets access with validation and caching.

Features:
- Required vs optional secrets classification
- Startup validation (fail-fast if missing)
- Cached access for performance
- Audit logging for secret access

Usage:
    from utils.secrets import get_secret, validate_all_secrets
    
    # On startup:
    validate_all_secrets()  # Raises if required secrets missing
    
    # In code:
    mongo_url = get_secret("MONGO_URL")
"""

import os
import logging
from functools import lru_cache
from typing import Optional, List, Dict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Required secrets - server refuses to start without these
REQUIRED_SECRETS = [
    "MONGO_URL",
    "DB_NAME",
    "JWT_SECRET",
]

# Important but not blocking - features degrade gracefully
IMPORTANT_SECRETS = [
    "EMERGENT_LLM_KEY",
    "OPENROUTER_API_KEY",
    "LLM_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "STRIPE_API_KEY",
    "CLOUDINARY_API_KEY",
    "CLOUDINARY_API_SECRET",
    "RESEND_API_KEY",
    "REDIS_URL",
]

# Optional secrets - features are disabled if missing
OPTIONAL_SECRETS = [
    "SENDGRID_API_KEY",
    "DEEPGRAM_API_KEY",
    "ELEVENLABS_API_KEY",
    "GITHUB_TOKEN",
    "HEYGEN_API_KEY",
    "WHAPI_API_TOKEN",
    "FLAGSHIP_API_TOKEN",
    "BAMBORA_API_PASSCODE",
    "PAYPAL_CLIENT_ID",
    "PAYPAL_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "ENCRYPTION_KEY",  # For Fernet encryption of sensitive data
    "REROOTS_AI_SYSTEM_PROMPT",  # Base64-encoded AI system prompt
]

# Secrets that should never be logged (even redacted)
SUPER_SENSITIVE = [
    "MONGO_URL",
    "JWT_SECRET",
    "STRIPE_API_KEY",
    "TWILIO_AUTH_TOKEN",
]


@lru_cache(maxsize=None)
def get_secret(key: str, default: Optional[str] = None) -> str:
    """
    Get a secret from environment variables with caching.
    
    Args:
        key: Environment variable name
        default: Default value if not found (only for optional secrets)
    
    Returns:
        The secret value
    
    Raises:
        RuntimeError: If required secret is missing and no default provided
    """
    value = os.environ.get(key)
    
    if not value:
        if key in REQUIRED_SECRETS:
            raise RuntimeError(f"CRITICAL: Required secret {key} not set")
        
        if key in IMPORTANT_SECRETS:
            logger.warning(f"[SECRETS] Important secret {key} not set - some features may be degraded")
        
        return default or ""
    
    return value


def get_secret_preview(key: str) -> str:
    """Get a safe preview of a secret (for logging/debugging)"""
    value = os.environ.get(key, "")
    if not value:
        return "<NOT SET>"
    if key in SUPER_SENSITIVE:
        return "<REDACTED>"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def validate_all_secrets() -> Dict[str, any]:
    """
    Validate all secrets on startup.
    
    Returns:
        Dict with validation results
    
    Raises:
        RuntimeError: If any required secret is missing
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "required": {},
        "important": {},
        "optional": {},
        "missing_required": [],
        "missing_important": [],
        "valid": True
    }
    
    # Check required secrets
    for key in REQUIRED_SECRETS:
        value = os.environ.get(key)
        if value:
            results["required"][key] = "SET"
        else:
            results["required"][key] = "MISSING"
            results["missing_required"].append(key)
    
    # Check important secrets
    for key in IMPORTANT_SECRETS:
        value = os.environ.get(key)
        if value:
            results["important"][key] = "SET"
        else:
            results["important"][key] = "MISSING"
            results["missing_important"].append(key)
    
    # Check optional secrets
    for key in OPTIONAL_SECRETS:
        value = os.environ.get(key)
        results["optional"][key] = "SET" if value else "MISSING"
    
    # Fail if required secrets missing
    if results["missing_required"]:
        results["valid"] = False
        error_msg = f"Missing required secrets: {results['missing_required']}"
        logger.critical(f"[SECRETS] {error_msg}")
        raise RuntimeError(error_msg)
    
    # Warn about missing important secrets
    if results["missing_important"]:
        logger.warning(f"[SECRETS] Missing important secrets: {results['missing_important']}")
    
    logger.info(f"[SECRETS] Validation passed - {len(REQUIRED_SECRETS)} required, {len(IMPORTANT_SECRETS) - len(results['missing_important'])} important available")
    
    return results


def list_configured_secrets() -> List[str]:
    """List all secrets that are currently configured (names only)"""
    all_secrets = REQUIRED_SECRETS + IMPORTANT_SECRETS + OPTIONAL_SECRETS
    return [key for key in all_secrets if os.environ.get(key)]


def check_secret_exists(key: str) -> bool:
    """Check if a secret is configured without retrieving its value"""
    return bool(os.environ.get(key))


# Export common secrets as module-level constants (cached)
# These are accessed via get_secret() for proper validation
def get_mongo_url() -> str:
    return get_secret("MONGO_URL")


def get_jwt_secret() -> str:
    return get_secret("JWT_SECRET")


def get_llm_key() -> str:
    """Get the LLM API key (checks multiple possible names)"""
    for key in ["EMERGENT_LLM_KEY", "OPENROUTER_API_KEY", "LLM_API_KEY", "ANTHROPIC_API_KEY"]:
        value = os.environ.get(key)
        if value:
            return value
    return ""


def get_stripe_key() -> str:
    return get_secret("STRIPE_API_KEY", "")


def get_twilio_credentials() -> tuple:
    """Get Twilio credentials as tuple (sid, token)"""
    return (
        get_secret("TWILIO_ACCOUNT_SID", ""),
        get_secret("TWILIO_AUTH_TOKEN", "")
    )


# ═══════════════════════════════════════════════════════════════════
# PYMONGO ANTI-PATTERN SCANNER
# ═══════════════════════════════════════════════════════════════════

def scan_for_pymongo_antipatterns():
    """
    Scan codebase for dangerous PyMongo boolean patterns.
    
    PyMongo collection/database objects always evaluate as True,
    so `if collection:` or `if db is None:` will not work as expected.
    Must use `if collection is not None:` instead.
    
    This runs on server startup to warn about potential bugs.
    """
    import subprocess
    import re
    
    patterns_to_check = [
        r'if\s+self\.collection[^i]',  # if self.collection but not is
        r'if\s+not\s+self\.collection[^i]',  # if not self.collection
        r'if\s+self\.db[^i]',  # if self.db but not is
        r'if\s+not\s+self\.db[^i]',  # if not self.db
        r'if\s+_db[^i\s]',  # if _db but not is
        r'if\s+not\s+_db[^i]',  # if not _db
        r'if\s+db[^i\s]',  # if db but not is (local var)
        r'if\s+collection[^i\s]',  # if collection but not is
    ]
    
    issues_found = []
    
    try:
        # Search in services, utils, and routes directories
        search_dirs = [
            "/app/backend/services/",
            "/app/backend/utils/",
            "/app/backend/routes/",
        ]
        
        for search_dir in search_dirs:
            try:
                result = subprocess.run(
                    ["grep", "-rn", "--include=*.py", "-E",
                     r"if (not )?(self\.)?(collection|db|_db)\s*[^i]",
                     search_dir],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        # Filter out correct patterns (is None, is not None)
                        if line and "is None" not in line and "is not None" not in line:
                            # Skip comments and regex patterns (r'...')
                            if not line.strip().startswith('#') and "r'" not in line and 'r"' not in line:
                                # Skip lines in secrets.py itself (scanner code)
                                if "secrets.py" not in line:
                                    # Skip false positives: db_user, db_result, etc. (query results, not collections)
                                    if "db_user" not in line and "db_result" not in line and "db_record" not in line:
                                        issues_found.append(line)
                                
            except subprocess.TimeoutExpired:
                logger.warning(f"[SECRETS] Timeout scanning {search_dir}")
            except FileNotFoundError:
                pass  # Directory doesn't exist
                
    except Exception as e:
        logger.warning(f"[SECRETS] PyMongo pattern scan failed: {e}")
        return
    
    if issues_found:
        logger.warning(f"[SECRETS] ⚠️ Found {len(issues_found)} potential PyMongo anti-patterns:")
        for line in issues_found[:5]:  # Show first 5
            logger.warning(f"[SECRETS]   {line[:150]}")
        if len(issues_found) > 5:
            logger.warning(f"[SECRETS]   ... and {len(issues_found) - 5} more")
        logger.warning("[SECRETS] Fix: Use `if collection is not None:` instead of `if collection:`")
    else:
        logger.info("[SECRETS] ✓ No PyMongo anti-patterns detected")

