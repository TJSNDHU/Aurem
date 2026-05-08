"""
AUREM SSOT config — iter 282aj.

Single import-friendly source for third-party credentials and platform URLs.
Always read via `os.getenv` at read-time, not import-time, so a reload after
`.env` edits picks up fresh values without a full pod restart.
"""
from __future__ import annotations

import os


def getenv(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


# LinkedIn OAuth (iter 282aj)
LINKEDIN_CLIENT_ID     = getenv("LINKEDIN_CLIENT_ID")
LINKEDIN_CLIENT_SECRET = getenv("LINKEDIN_CLIENT_SECRET")

# Canonical external URL (used for OAuth redirect_uri assembly etc.)
AUREM_BASE_URL = getenv("AUREM_BASE_URL", "https://aurem.live")

# test-lab.ai — autonomous AI QA for AWB-generated sites (iter 282al-15)
TEST_LAB_API_KEY  = getenv("TEST_LAB_API_KEY")
TEST_LAB_BASE_URL = getenv("TEST_LAB_BASE_URL", "https://www.test-lab.ai/api/v1")

# Stripe price ID for one-time $197 site repair
STRIPE_PRICE_SITE_REPAIR = getenv("STRIPE_PRICE_SITE_REPAIR")

# Stripe price ID for $297 manual (human-reviewed) repair — second-chance
# offer for customers whose $197 auto-repair was refunded (iter 282al-17)
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
