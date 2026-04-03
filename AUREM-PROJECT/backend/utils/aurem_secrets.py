"""
AUREM Security - Secrets Management & Validation
Company: Polaris Built Inc.

Validates all required environment variables on startup.
Server refuses to start if any critical secret is missing.
"""

import os
import sys
import base64
import logging
from typing import Dict, List, Optional
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# REQUIRED SECRETS REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_SECRETS = {
    # Critical - Server won't start without these
    "critical": [
        "MONGO_URL",
    ],
    # Important - Features will be degraded but server will start
    "important": [
        "EMERGENT_LLM_KEY",
        "AUREM_ENCRYPTION_KEY",  # For Fernet encryption
        "JWT_SECRET_KEY",
        "WHAPI_API_TOKEN",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "SENDGRID_API_KEY",
    ],
    # Optional - Will use defaults
    "optional": [
        "ADMIN_WHATSAPP",
        "OPENROUTER_API_KEY",
    ]
}

# Base64-encoded agent prompts (decoded at runtime)
AGENT_PROMPT_VARS = [
    "AUREM_SCOUT_PROMPT",
    "AUREM_ARCHITECT_PROMPT", 
    "AUREM_ENVOY_PROMPT",
    "AUREM_CLOSER_PROMPT",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECRETS VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_secrets(strict: bool = False) -> Dict[str, List[str]]:
    """
    Validate all required secrets are present.
    In strict mode, raises SystemExit if critical secrets are missing.
    """
    missing = {
        "critical": [],
        "important": [],
        "optional": []
    }
    
    for level, secrets in REQUIRED_SECRETS.items():
        for secret in secrets:
            if not os.environ.get(secret):
                missing[level].append(secret)
    
    # Log warnings
    if missing["critical"]:
        logger.critical(f"[AUREM SECURITY] CRITICAL secrets missing: {missing['critical']}")
        if strict:
            logger.critical("[AUREM SECURITY] Server startup blocked - configure required secrets")
            sys.exit(1)
    
    if missing["important"]:
        logger.warning(f"[AUREM SECURITY] Important secrets missing (degraded features): {missing['important']}")
    
    if missing["optional"]:
        logger.info(f"[AUREM SECURITY] Optional secrets missing (defaults used): {missing['optional']}")
    
    return missing


def get_secret(name: str, default: str = None) -> Optional[str]:
    """Get a secret from environment with optional default"""
    return os.environ.get(name, default)


@lru_cache(maxsize=1)
def get_encryption_key() -> bytes:
    """Get Fernet encryption key (cached)"""
    key = os.environ.get("AUREM_ENCRYPTION_KEY")
    if not key:
        # Generate a default for development only
        logger.warning("[AUREM SECURITY] Using development encryption key - NOT FOR PRODUCTION")
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
        os.environ["AUREM_ENCRYPTION_KEY"] = key
    return key.encode() if isinstance(key, str) else key


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT PROMPT DECODER (Base64)
# ═══════════════════════════════════════════════════════════════════════════════

# Default prompts (used only if env vars not set)
DEFAULT_AGENT_PROMPTS = {
    "scout": """You are The Scout, an elite B2B intelligence agent for AUREM.
Your mission is to identify high-value prospects based on industry triggers.
Respond ONLY in valid JSON format with prospects array.""",
    
    "architect": """You are The Architect, the strategic analyst for AUREM.
Your mission is to analyze prospect data and craft engagement hooks.
Respond ONLY in valid JSON format with qualified_prospects array.""",
    
    "envoy": """You are The Envoy, the outreach strategist for AUREM.
Your mission is to select optimal channels and craft personalized messages.
Respond ONLY in valid JSON format with outreach_plans array.""",
    
    "closer": """You are The Closer, the execution agent for AUREM.
Your mission is to initiate contact and book meetings.
Execute with precision and professionalism."""
}


def get_agent_prompt(agent_name: str) -> str:
    """
    Get agent prompt - decodes from base64 env var if available,
    otherwise uses default prompt.
    """
    env_var = f"AUREM_{agent_name.upper()}_PROMPT"
    encoded = os.environ.get(env_var)
    
    if encoded:
        try:
            return base64.b64decode(encoded).decode('utf-8')
        except Exception as e:
            logger.warning(f"[AUREM SECURITY] Failed to decode {env_var}: {e}")
    
    return DEFAULT_AGENT_PROMPTS.get(agent_name.lower(), "")


def encode_prompt_for_env(prompt: str) -> str:
    """Helper to encode a prompt for storage in env var"""
    return base64.b64encode(prompt.encode('utf-8')).decode('utf-8')


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_aurem_security(strict: bool = False):
    """
    Initialize AUREM security module.
    Call this on server startup.
    """
    logger.info("[AUREM SECURITY] Initializing security module...")
    
    # Validate secrets
    missing = validate_secrets(strict=strict)
    
    # Check encryption key
    try:
        key = get_encryption_key()
        logger.info(f"[AUREM SECURITY] Encryption key loaded ({len(key)} bytes)")
    except Exception as e:
        logger.error(f"[AUREM SECURITY] Encryption key error: {e}")
    
    # Validate agent prompts exist
    for agent in ["scout", "architect", "envoy", "closer"]:
        prompt = get_agent_prompt(agent)
        source = "env" if os.environ.get(f"AUREM_{agent.upper()}_PROMPT") else "default"
        logger.info(f"[AUREM SECURITY] {agent.capitalize()} prompt loaded ({source}, {len(prompt)} chars)")
    
    total_missing = len(missing["critical"]) + len(missing["important"])
    if total_missing == 0:
        logger.info("[AUREM SECURITY] ✅ All secrets validated successfully")
    else:
        logger.warning(f"[AUREM SECURITY] ⚠️ {total_missing} secrets missing - some features degraded")
    
    return missing
