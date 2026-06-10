"""
Startup Lock-In Validator
=========================
Runs async at server start. Logs a RED WARNING with emoji flag if any
locked production build is missing, so future agents / deploys see it
immediately in the logs.

Does not crash the server — intentional. We want the deploy to succeed
so the rest of the platform keeps running, but the WARNING line must
appear in supervisor logs for anyone reviewing.
"""
from __future__ import annotations

import os
import logging

logger = logging.getLogger(__name__)

# Manifest — keep in sync with /app/memory/LOCKED_BUILDS.md
# NOTE: Only include files PRESENT IN THE BACKEND CONTAINER.
# Frontend files (/app/frontend/*) live in a separate deploy artifact — validating
# them from the backend container causes false-positive "missing" warnings in
# production (Kubernetes multi-container deploy).
LOCKED_FILES = [
    "/app/backend/routers/seo_audit_router.py",
    "/app/backend/routers/privacy_mode_router.py",
    "/app/backend/routers/daily_intel_router.py",
    "/app/backend/routers/voice_agent_router.py",
    "/app/backend/routers/shopify_oauth_router.py",
    # iter D-76 dedupe — google_oauth_callback.py removed (canonical is routes.auth)
    "/app/backend/services/sendgrid_compat.py",
    "/app/backend/services/email_service_resend.py",
    "/app/backend/services/lead_enrichment_casl.py",
    "/app/backend/static/plugins/aurem-pixel.zip",
]

LOCKED_ENV_VARS = [
    "STRIPE_PRICE_STARTER", "STRIPE_PRICE_GROWTH", "STRIPE_PRICE_ENTERPRISE",
    "STRIPE_PRICE_STARTER_ANNUAL", "STRIPE_PRICE_GROWTH_ANNUAL", "STRIPE_PRICE_ENTERPRISE_ANNUAL",
    "RETELL_API_KEY", "STRIPE_SECRET_KEY", "RESEND_API_KEY",
]

ARCHIVED_MUST_STAY = [
    "/app/backend/routers/clawchief_router.py",
    "/app/backend/routers/empire_hud_router.py",
    "/app/backend/routers/evolver_router.py",
    "/app/backend/routers/telegram_router.py",
]


def validate_locked_builds() -> dict:
    """Run every startup. Returns {'ok': bool, 'missing_files': [...], 'missing_env': [...]}."""
    missing_files = [p for p in LOCKED_FILES if not os.path.isfile(p)]
    missing_env = [k for k in LOCKED_ENV_VARS if not os.environ.get(k)]
    resurrected = [p for p in ARCHIVED_MUST_STAY if os.path.isfile(p)]

    ok = not (missing_files or missing_env or resurrected)

    if ok:
        logger.info("[lock-in] ✅ All %d locked production builds present. %d env vars configured.",
                    len(LOCKED_FILES), len(LOCKED_ENV_VARS))
    else:
        logger.warning("=" * 70)
        logger.warning("🔒 LOCKED BUILDS VALIDATION — REGRESSION DETECTED")
        logger.warning("=" * 70)
        if missing_files:
            logger.warning("❌ MISSING FILES (%d): %s", len(missing_files), ", ".join(missing_files))
        if missing_env:
            logger.warning("❌ MISSING ENV VARS (%d): %s", len(missing_env), ", ".join(missing_env))
        if resurrected:
            logger.warning("❌ ARCHIVED FILES RESURRECTED (%d): %s", len(resurrected), ", ".join(resurrected))
        logger.warning("See /app/memory/LOCKED_BUILDS.md for the full contract.")
        logger.warning("=" * 70)

    return {
        "ok": ok,
        "missing_files": missing_files,
        "missing_env": missing_env,
        "resurrected": resurrected,
    }
