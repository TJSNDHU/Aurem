"""
Founder Auto-Provision (idempotent)
====================================
On startup, ensures the configured founder accounts exist as LIFETIME ENTERPRISE
in `platform_users`. This is critical for production where the Atlas DB differs
from the preview pod — without this, founder accounts show as STARTER/TRIAL on
aurem.live even though they're upgraded on preview.

Configured via env (comma-separated):
  FOUNDER_EMAILS=teji.ss1986@gmail.com,admin@aurem.live

Each account is upgraded with:
  - tier=enterprise, tier_status=active
  - lifetime=True, founder=True
  - pixel_installed=True (with a `business_id` BIN)
  - usage limits set to enterprise tier
"""
import os
import logging
from datetime import datetime, timezone
from passlib.context import CryptContext

logger = logging.getLogger(__name__)
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_FOUNDERS = [
    {"email": "teji.ss1986@gmail.com", "password": "Admin123",          "business_id": "AURE-FNDR-001", "full_name": "AUREM Admin"},
    {"email": "admin@aurem.live",      "password": "AuremAdmin2024!",   "business_id": "AURE-FNDR-002", "full_name": "AUREM Founder"},
]

ENTERPRISE_LIMITS = {
    "crew_limit": 10000,
    "voice_limit": 500,
    "whatsapp_limit": 5000,
}


async def ensure_founders(db) -> dict:
    """Idempotently upsert founder accounts as LIFETIME ENTERPRISE.
    Safe to run on every startup. Returns a summary."""
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    env_emails = os.environ.get("FOUNDER_EMAILS", "").strip()
    extra = [e.strip().lower() for e in env_emails.split(",") if e.strip()]
    founders = list(DEFAULT_FOUNDERS)
    # Allow overriding existing founders via env (no password change if not provided)
    for em in extra:
        if not any(f["email"].lower() == em for f in founders):
            founders.append({"email": em, "password": None, "business_id": None, "full_name": "Founder"})

    upserts = 0
    upgrades = 0
    now = datetime.now(timezone.utc)
    for fdr in founders:
        email = fdr["email"].lower()
        existing = await db.platform_users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        user_id = (existing or {}).get("user_id") or f"plat_{os.urandom(12).hex()[:24]}"

        update_set = {
            "email": email,
            "user_id": user_id,
            "full_name": fdr.get("full_name") or "Founder",
            "tier": "enterprise",
            "tier_status": "active",
            "lifetime": True,
            "founder": True,
            "pixel_installed": True,
            "pixel_verified": True,
            "usage": ENTERPRISE_LIMITS,
            "trial_ends_at": None,
            "updated_at": now,
        }
        if fdr.get("business_id"):
            update_set["business_id"] = fdr["business_id"]
        # Only set password if (a) account is new, OR (b) seed password explicitly provided
        update_on_insert = {"created_at": now, "company_name": "AUREM Platform"}
        if not existing and fdr.get("password"):
            update_on_insert["password_hash"] = _pwd_ctx.hash(fdr["password"])
        elif existing and fdr.get("password"):
            # Reset to seed password ONLY if explicitly enabled via env (preserves user-changed passwords)
            if os.environ.get("FOUNDER_PASSWORD_RESET", "").lower() in ("1", "true", "yes"):
                update_set["password_hash"] = _pwd_ctx.hash(fdr["password"])

        await db.platform_users.update_one(
            {"email": email},
            {"$set": update_set, "$setOnInsert": update_on_insert},
            upsert=True,
        )
        if existing:
            upgrades += 1
        else:
            upserts += 1

        # Ensure pixel record exists
        if fdr.get("business_id"):
            await db.aurem_pixels.update_one(
                {"business_id": fdr["business_id"]},
                {"$set": {
                    "business_id": fdr["business_id"],
                    "owner_email": email,
                    "tenant_id": user_id,
                    "founder": True,
                    "installed": True,
                }, "$setOnInsert": {"created_at": now, "events_received": 0}},
                upsert=True,
            )
    msg = f"[FOUNDERS] Provisioned {upserts} new + {upgrades} upgraded ({len(founders)} total)"
    logger.info(msg)
    print(msg, flush=True)
    return {"ok": True, "new": upserts, "upgraded": upgrades, "total": len(founders)}
