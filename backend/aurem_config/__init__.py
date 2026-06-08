"""
AUREM SSOT config package.

This package was previously shadowed by a flat `aurem_config.py` module
sitting next to it on the import path. Python resolves the package first,
so every `from aurem_config import LINKEDIN_CLIENT_ID, TEST_LAB_API_KEY`
was failing with ImportError / AttributeError (~36k 5xx incidents).

Fix: re-export the canonical constants here so the package becomes the
single SSOT. Always read via os.getenv at call-time so a reload after
.env edits picks up fresh values without a full pod restart.
"""
from __future__ import annotations

import os


def getenv(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


# LinkedIn OAuth
LINKEDIN_CLIENT_ID     = getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = getenv("LINKEDIN_CLIENT_SECRET")

# Canonical external URL (used for OAuth redirect_uri assembly etc.)
AUREM_BASE_URL = getenv("AUREM_BASE_URL", "https://aurem.live")

# test-lab.ai — autonomous AI QA for AWB-generated sites
TEST_LAB_API_KEY  = getenv("TEST_LAB_API_KEY")
TEST_LAB_BASE_URL = getenv("TEST_LAB_BASE_URL", "https://www.test-lab.ai/api/v1")

# Stripe price IDs
STRIPE_PRICE_SITE_REPAIR   = getenv("STRIPE_PRICE_SITE_REPAIR")
STRIPE_PRICE_MANUAL_REPAIR = getenv("STRIPE_PRICE_MANUAL_REPAIR")


def linkedin_redirect_uri() -> str:
    """Computed at call-time so environment edits reload correctly."""
    base = (os.getenv("AUREM_BASE_URL") or "https://aurem.live").rstrip("/")
    return f"{base}/api/linkedin/callback"


__all__ = [
    "LINKEDIN_CLIENT_ID",
    "LINKEDIN_CLIENT_SECRET",
    "AUREM_BASE_URL",
    "TEST_LAB_API_KEY",
    "TEST_LAB_BASE_URL",
    "STRIPE_PRICE_SITE_REPAIR",
    "STRIPE_PRICE_MANUAL_REPAIR",
    "linkedin_redirect_uri",
    "getenv",
]
