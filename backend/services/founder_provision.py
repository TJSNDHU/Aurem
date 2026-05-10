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
    # iter 322 — final BIN names. Old AURE-FNDR-001/AURE-FNDR-002 are
    # cascade-renamed by the db_migrate iter322-cleanup endpoint.
    {"email": "teji.ss1986@gmail.com", "password": "ul4Fb*u^l^Nuazh@B%Q8", "business_id": "AURE-ADMIN", "full_name": "AUREM Admin"},
    {"email": "teji.ss1986+dogfood@gmail.com", "password": "AuremFounder2026!", "business_id": "AUR-FNDR-001", "full_name": "AUREM Founder (Dogfood)", "domain": "aurem.live", "dogfood": True},
]

# iter 322 — Founder Lifetime Free perks: bypass billing, unlock every
# service, never throttle. Applied to platform_users on every startup
# (idempotent) so `admin@aurem.live` (the AUREM dogfood account) acts as
# the operational customer used to drive every paid feature without
# touching the payment rails.
LIFETIME_FREE_PERKS = {
    "lifetime_free": True,
    "billing_exempt": True,
    "subscription_status": "lifetime_active",
    "subscription_renews_at": None,
    "services_unlocked": ["*"],  # wildcard — every gated feature passes the gate
}

ENTERPRISE_LIMITS = {
    # iter 322 — bumped 10× so dogfood usage never trips a quota gate.
    "crew_limit": 100000,
    "voice_limit": 5000,
    "whatsapp_limit": 50000,
    "sms_limit": 50000,
    "email_limit": 1000000,
    "campaigns_limit": 10000,
    "agents_limit": 1000,
    "websites_limit": 1000,
    "domains_limit": 1000,
    "leads_limit": 1000000,
    "ai_calls_limit": 1000000,
}


async def ensure_founders(db) -> dict:
    """Idempotently upsert founder accounts as LIFETIME ENTERPRISE.
    Safe to run on every startup. Returns a summary.

    Mirrors the founder identity into BOTH `platform_users` (customer portal)
    and `users` (admin portal — `/admin/login` reads from this collection)
    so a single set of credentials authenticates everywhere.

    Password resolution priority (per email index):
      1. ENV var `ADMIN_PASSWORD_HASH_<N>` already-bcrypted hash (preferred for prod).
         Use `$$` to escape any literal `$` in the env value.
      2. ENV var `FOUNDER_PASSWORD_RESET=1` + seed password → re-hash and set.
      3. New account only (insert): hash the seed password.
      4. Existing account: leave password untouched.
    """
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    env_emails = os.environ.get("FOUNDER_EMAILS", "").strip()
    extra = [e.strip().lower() for e in env_emails.split(",") if e.strip()]
    founders = list(DEFAULT_FOUNDERS)
    # Allow overriding existing founders via env (no password change if not provided)
    for em in extra:
        if not any(f["email"].lower() == em for f in founders):
            founders.append({"email": em, "password": None, "business_id": None, "full_name": "Founder"})

    force_reset = os.environ.get("FOUNDER_PASSWORD_RESET", "").lower() in ("1", "true", "yes")
    disable_2fa = os.environ.get("FOUNDER_DISABLE_2FA", "").lower() in ("1", "true", "yes")

    upserts = 0
    upgrades = 0
    now = datetime.now(timezone.utc)
    for idx, fdr in enumerate(founders, start=1):
        email = fdr["email"].lower()
        existing = await db.platform_users.find_one({"email": email}, {"_id": 0, "user_id": 1})
        user_id = (existing or {}).get("user_id") or f"plat_{os.urandom(12).hex()[:24]}"

        # Resolve the password hash to use for THIS founder.
        env_hash_raw = os.environ.get(f"ADMIN_PASSWORD_HASH_{idx}", "")
        env_hash = env_hash_raw.replace("$$", "$") if env_hash_raw else ""
        new_hash = None
        if env_hash:
            new_hash = env_hash  # trust the env-provided bcrypt hash
        elif force_reset and fdr.get("password"):
            new_hash = _pwd_ctx.hash(fdr["password"])
        elif not existing and fdr.get("password"):
            # First-time provision — set seed password
            new_hash = _pwd_ctx.hash(fdr["password"])

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
            # iter 322 — Lifetime Free perks (bypass billing + unlock all)
            **LIFETIME_FREE_PERKS,
        }
        if fdr.get("dogfood"):
            update_set["dogfood"] = True
            # iter 322ai — Dogfood = real Enterprise customer. No admin shortcuts.
            # Force role=user + plan=lifetime_free here so platform_auth login
            # passes (admin-collision guard rejects admin role on /api/platform/auth).
            update_set["role"] = "user"
            update_set["plan"] = "lifetime_free"
            update_set["is_dogfood"] = True
            update_set["is_founder"] = True
            update_set["is_locked"] = False
            update_set["failed_attempts"] = 0
        if fdr.get("business_id"):
            update_set["business_id"] = fdr["business_id"]
        if fdr.get("domain"):
            update_set["primary_domain"] = fdr["domain"]
            update_set["allowed_domains"] = [fdr["domain"]]
        # Apply the resolved password hash (if any) to platform_users.
        update_on_insert = {"created_at": now, "company_name": "AUREM Platform"}
        if new_hash:
            update_set["password_hash"] = new_hash

        await db.platform_users.update_one(
            {"email": email},
            {"$set": update_set, "$setOnInsert": update_on_insert},
            upsert=True,
        )

        # ─── MIRROR INTO `users` (admin portal source-of-truth) ───
        # `/api/auth/admin/login` reads from db.users — without an entry
        # here, /admin/login fails with "Invalid credentials" even though
        # platform_users has the correct hash. Sync both fields.
        users_set = {
            "email": email,
            "id": user_id,  # admin login JWT uses user["id"]
            "name": fdr.get("full_name") or "AUREM Founder",
            "is_admin": True,
            "is_super_admin": True,
            "role": "super_admin",
            "tier": "enterprise",
            "tier_status": "active",
            "lifetime": True,
            "founder": True,
            "updated_at": now,
        }
        if new_hash:
            users_set["password"] = new_hash
            users_set["password_hash"] = new_hash
        # Emergency 2FA disable — set FOUNDER_DISABLE_2FA=1 in prod env if
        # founder lost access to authenticator. Re-enable via admin UI after.
        if disable_2fa:
            users_set["totp_enabled"] = False
            users_set["totp_secret"] = ""
        await db.users.update_one(
            {"email": email},
            {"$set": users_set, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

        # Also keep `aurem_users` (legacy customer-login fallback) in sync.
        aurem_set = {
            "email": email,
            "role": "user" if is_dogfood else "super_admin",
            "is_admin": False if is_dogfood else True,
        }
        if is_dogfood:
            aurem_set["plan"] = "lifetime_free"
            aurem_set["services_unlocked"] = ["*"]
        if new_hash:
            aurem_set["password_hash"] = new_hash
        await db.aurem_users.update_one(
            {"email": email},
            {"$set": aurem_set, "$setOnInsert": {"created_at": now}},
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
                    "verified": True,
                    # iter 322 — bind aurem.live domain to the dogfood pixel
                    # so events from the live site land against this account.
                    **({"domain": fdr["domain"], "allowed_domains": [fdr["domain"]]}
                       if fdr.get("domain") else {}),
                    "lifetime_free": True,
                }, "$setOnInsert": {"created_at": now, "events_received": 0}},
                upsert=True,
            )
    flags = []
    if force_reset:
        flags.append("FOUNDER_PASSWORD_RESET=1")
    if disable_2fa:
        flags.append("FOUNDER_DISABLE_2FA=1")
    if any(os.environ.get(f"ADMIN_PASSWORD_HASH_{i}") for i in range(1, 5)):
        flags.append("ADMIN_PASSWORD_HASH_*")
    flags_str = f" [flags: {', '.join(flags)}]" if flags else ""
    msg = (
        f"[FOUNDERS] Provisioned {upserts} new + {upgrades} upgraded "
        f"({len(founders)} total){flags_str}"
    )
    logger.info(msg)
    print(msg, flush=True)
    return {"ok": True, "new": upserts, "upgraded": upgrades, "total": len(founders), "flags": flags}
