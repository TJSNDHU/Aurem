"""
Dogfood Account Setup — full 5-step E2E provisioning.

Run: python3 scripts/setup_dogfood.py

Idempotent. Safe to run multiple times.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

EMAIL = "teji.ss1986+dogfood@gmail.com"
NEW_PW = "AuremFounder2026!"
NEW_BIN = "AUR-FNDR-001"


async def main() -> int:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    pw_hash = bcrypt.hashpw(NEW_PW.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")

    # ── STEP 1 + 2 — platform_users: unlock, full access, pixel auto-install ──
    pu_set = {
        "email": EMAIL,
        "password_hash": pw_hash,
        "business_id": NEW_BIN,
        "business_id_active": True,
        "is_active": True,
        "is_locked": False,
        "failed_attempts": 0,
        "plan": "lifetime_free",
        "tier": "lifetime_free",
        "tier_status": "active",
        "subscription_status": "lifetime",
        "services_unlocked": ["*"],
        "trial_ends_at": None,
        "is_dogfood": True,
        "is_founder": True,
        "lifetime_free": True,
        "lifetime": True,
        "pixel_installed": True,
        "pixel_verified": True,
        "role": "user",  # Real customer experience — no admin shortcuts
        "company_name": "AUREM Self-Client",
        "full_name": "AUREM Founder (Dogfood)",
        "updated_at": now,
    }
    pu_unset = {
        "locked_until": "", "pin_locked_until": "", "pin_failed_count": "",
        "login_failed_count": "",
    }
    await db.platform_users.update_one(
        {"email": EMAIL}, {"$set": pu_set, "$unset": pu_unset}, upsert=True,
    )

    # ── Strip admin flags from db.users so platform_auth collision guard passes ──
    await db.users.update_one(
        {"email": EMAIL},
        {
            "$set": {
                "password": pw_hash,
                "password_hash": pw_hash,
                "is_admin": False,
                "is_super_admin": False,
                "role": "user",
                "business_id": NEW_BIN,
                "business_id_active": True,
                "plan": "lifetime_free",
                "tier": "lifetime_free",
                "tier_status": "active",
                "services_unlocked": ["*"],
                "lifetime": True,
                "is_active": True,
                "updated_at": now,
            },
            "$unset": {
                "locked_until": "", "pin_locked_until": "", "is_locked": "",
                "pin_failed_count": "", "login_failed_count": "",
            },
        },
        upsert=True,
    )

    # Mirror on legacy aurem_users (used by /api/auth/login in aurem_routes)
    await db.aurem_users.update_one(
        {"email": EMAIL},
        {
            "$set": {
                "email": EMAIL,
                "password_hash": pw_hash,
                "plan": "lifetime_free",
                "tier": "lifetime_free",
                "tier_status": "active",
                "services_unlocked": ["*"],
                "is_admin": False,
                "role": "user",
                "is_active": True,
                "lifetime_free": True,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    # ── STEP 3 — Wire BIN AUR-FNDR-001 to all catalog services ──
    await db.tenant_customers.update_one(
        {"email": EMAIL},
        {
            "$set": {
                "email": EMAIL,
                "business_id": NEW_BIN,
                "business_name": "AUREM Self-Client",
                "plan": "lifetime_free",
                "status": "active",
                "updated_at": now,
            }
        },
        upsert=True,
    )
    await db.aurem_billing.update_one(
        {"email": EMAIL},
        {
            "$set": {
                "email": EMAIL,
                "business_id": NEW_BIN,
                "plan": "lifetime_free",
                "status": "lifetime_active",
                "current_period_start": None,
                "current_period_end": None,
                "updated_at": now,
            }
        },
        upsert=True,
    )

    # Subscribe to every catalog service (live + hidden + disabled — full unlock)
    catalog = await db.service_catalog.find({}, {"_id": 0}).to_list(length=200)
    sub_count = 0
    for svc in catalog:
        sid = svc.get("service_id")
        if not sid:
            continue
        await db.customer_subscriptions.update_one(
            {"tenant_bin": NEW_BIN, "service_id": sid},
            {
                "$set": {
                    "tenant_bin": NEW_BIN,
                    "email": EMAIL,
                    "service_id": sid,
                    "service_name": svc.get("name", sid),
                    "cluster": svc.get("cluster", ""),
                    "price_monthly": 0,  # dogfood — $0/mo
                    "billed_price_monthly": 0,
                    "status": "active",
                    "source": "dogfood",
                    "started_at": now,
                    "next_renewal_at": None,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
        sub_count += 1

    # ── Pixel record ──
    await db.pixel_installations.update_one(
        {"business_id": NEW_BIN},
        {
            "$set": {
                "business_id": NEW_BIN,
                "email": EMAIL,
                "domain": "aurem.live",
                "installed": True,
                "verified": True,
                "auto_installed": True,
                "installed_at": now,
                "verified_at": now,
            }
        },
        upsert=True,
    )

    # ── Clear all lockout / attempt collections keyed by email or BIN ──
    for coll in ("login_attempts", "pin_login_attempts", "failed_logins", "auth_attempts"):
        try:
            await db[coll].delete_many(
                {"$or": [{"email": EMAIL}, {"key": {"$regex": NEW_BIN}}]}
            )
        except Exception:
            pass

    # ── PROOF DUMP ──
    pu = await db.platform_users.find_one({"email": EMAIL}, {"_id": 0, "password_hash": 0, "pin_hash": 0})
    print("\n══════ STEP 1 PROOF — platform_users ══════")
    for k in ("email", "business_id", "is_locked", "failed_attempts", "plan",
              "services_unlocked", "trial_ends_at", "subscription_status",
              "is_dogfood", "is_founder", "role"):
        print(f"  {k:<22} = {pu.get(k)!r}")

    print("\n══════ STEP 2 PROOF — Pixel auto-install ══════")
    print(f"  pixel_installed       = {pu.get('pixel_installed')!r}")
    print(f"  pixel_verified        = {pu.get('pixel_verified')!r}")
    px = await db.pixel_installations.find_one({"business_id": NEW_BIN}, {"_id": 0})
    print(f"  pixel_installations   = {px}")

    print("\n══════ STEP 3 PROOF — Wired services ══════")
    print(f"  BIN                   = {NEW_BIN}")
    print(f"  catalog total         = {len(catalog)}")
    print(f"  subscriptions written = {sub_count}")
    subs = await db.customer_subscriptions.find(
        {"tenant_bin": NEW_BIN, "status": "active"}, {"_id": 0, "service_id": 1, "status": 1}
    ).to_list(length=200)
    print(f"  active subs in DB     = {len(subs)}")
    print("  service_ids: " + ", ".join(s["service_id"] for s in subs))

    print("\nDONE. Use /api/platform/auth/login with:")
    print(f"  email = {EMAIL}")
    print(f"  password = {NEW_PW}")
    print(f"  (or BIN = {NEW_BIN})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
