"""
Startup environment validation
──────────────────────────────
Surfaces missing/misconfigured env vars at boot time so silent fallbacks
(in-memory Redis, ephemeral JWT, mock APIs) are visible in logs and on a
single admin diagnostic endpoint — instead of being hidden across 2,500+
silent try/except swallowers scattered through the codebase.

Design:
- This module NEVER raises. It only logs warnings and records a report so
  the pod always boots and K8s health probes stay green.
- Critical vars (JWT_SECRET, MONGO_URL, DB_NAME) are checked via
  config.py's safe resolver, which already provides 3-tier fallbacks.
- "Should-have" integrations are listed below — missing ones become a
  flat list visible via GET /api/admin/startup-report.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger(__name__)

# Integration env vars expected in a fully-configured deployment.
# Group → list of env-var names. Missing vars degrade the matching feature
# but never crash boot.
EXPECTED: Dict[str, List[str]] = {
    "core": ["MONGO_URL", "DB_NAME"],
    "auth": ["JWT_SECRET"],
    "llm": ["EMERGENT_LLM_KEY"],
    "groq_fallback": ["GROQ_API_KEY"],
    "ollama_sovereign": ["OLLAMA_BASE_URL"],
    "redis": ["REDIS_URL"],
    "stripe": ["STRIPE_SECRET_KEY"],
    "twilio": ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"],
    "resend_email": ["RESEND_API_KEY"],
    "scraping": ["IPROYAL_USERNAME", "IPROYAL_PASSWORD"],
}

# Last-computed report, populated by validate_environment() on boot.
_LAST_REPORT: Dict = {}


def validate_environment() -> Dict:
    """Inspect process env vars and produce a structured report.

    Idempotent — safe to call multiple times. Always returns a dict; never
    raises (so it can be called from any startup hook).
    """
    global _LAST_REPORT
    started_at = datetime.now(timezone.utc).isoformat()
    groups = {}
    missing_total: List[str] = []

    for group, names in EXPECTED.items():
        present = [n for n in names if (os.environ.get(n) or "").strip()]
        missing = [n for n in names if not (os.environ.get(n) or "").strip()]
        groups[group] = {
            "expected": names,
            "present": present,
            "missing": missing,
            "status": "ok" if not missing else (
                "partial" if present else "absent"
            ),
        }
        missing_total.extend(missing)

    # JWT_SECRET special-case: even if env is missing, config.py has a
    # safe fallback chain. Surface which tier was used.
    jwt_source = "unknown"
    try:
        from config import _JWT_SECRET_SOURCE  # type: ignore
        jwt_source = _JWT_SECRET_SOURCE
    except Exception:
        pass
    groups["auth"]["jwt_source"] = jwt_source

    report = {
        "ok": len(missing_total) == 0,
        "started_at": started_at,
        "missing_count": len(missing_total),
        "missing": sorted(set(missing_total)),
        "groups": groups,
    }

    # Log once at boot.
    if missing_total:
        logger.warning(
            "[startup-validation] %d env vars missing across %d groups: %s",
            len(missing_total),
            sum(1 for g in groups.values() if g["missing"]),
            ", ".join(sorted(set(missing_total))),
        )
    else:
        logger.info("[startup-validation] all expected env vars present")
    logger.info("[startup-validation] JWT_SECRET source=%s", jwt_source)

    _LAST_REPORT = report
    return report


def get_last_report() -> Dict:
    """Return the most recent validation report (empty until first call)."""
    return dict(_LAST_REPORT) if _LAST_REPORT else {"ok": False, "note": "not-yet-run"}
