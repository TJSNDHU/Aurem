"""
RERO-3DEJ Recovery Script
=========================
One-off idempotent migration: seed `platform_users` for `admin@reroots.ca`
from the legacy `users` collection (Google-OAuth tenant), then trigger the
Customer Health auto-repair pipeline to fill billing / workspace / tenant /
Stripe records and verify.

Why this exists:
  RERO-3DEJ pre-dates the 2026-05-05 funnel fix that started seeding
  `platform_users + aurem_workspaces + aurem_billing + Stripe customer`
  on register. The legacy `users.admin@reroots.ca` (Google OAuth) was
  never copied into `platform_users`, so /my dashboard was blank because
  every customer lookup is keyed on `platform_users.business_id`.

Usage:
  cd /app/backend && set -a && source .env && set +a && \\
      python3 ../scripts/reroots_recover.py

Idempotent: safe to re-run. All inserts are upserts.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

# Allow `from services.* import ...` when run from /app
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from motor.motor_asyncio import AsyncIOMotorClient

LEGACY_EMAIL = "admin@reroots.ca"
TARGET_BIN   = "RERO-3DEJ"
COMPANY_NAME = "Reroots"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def main() -> int:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not (mongo_url and db_name):
        print("ERROR: MONGO_URL / DB_NAME not set in env")
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # ─── 1. Pull legacy record ────────────────────────────────
    legacy = await db.users.find_one({"email": LEGACY_EMAIL})
    if not legacy:
        print(f"❌ legacy users.{LEGACY_EMAIL} not found — abort")
        return 3

    full_name = (
        legacy.get("google_name")
        or f"{legacy.get('first_name','')} {legacy.get('last_name','')}".strip()
        or "Reroots Admin"
    )
    print(f"✓ legacy user found: {full_name} ({LEGACY_EMAIL})")

    # ─── 2. Upsert platform_users ─────────────────────────────
    pu_existing = await db.platform_users.find_one({"business_id": TARGET_BIN})
    if pu_existing:
        print(f"✓ platform_users.{TARGET_BIN} already exists — skipping seed")
    else:
        # Also guard against email-only collision (defensive idempotency)
        pu_by_email = await db.platform_users.find_one({"email": LEGACY_EMAIL})
        if pu_by_email and not pu_by_email.get("business_id"):
            print(f"✓ patching existing platform_users.{LEGACY_EMAIL} → "
                  f"business_id={TARGET_BIN}")
            await db.platform_users.update_one(
                {"_id": pu_by_email["_id"]},
                {"$set": {
                    "business_id": TARGET_BIN,
                    "business_id_active": True,
                    "business_id_created": _utc_now().isoformat(),
                    "company_name": COMPANY_NAME,
                    "full_name": full_name,
                    "updated_at": _utc_now().isoformat(),
                }},
            )
        else:
            doc = {
                "email": LEGACY_EMAIL,
                "full_name": full_name,
                "company_name": COMPANY_NAME,
                "role": "user",
                "auth_provider": "google",
                "google_picture": legacy.get("google_picture"),
                "email_verified": True,
                "is_active": True,
                "plan": "trial",
                "terms_accepted": True,
                "terms_version": "1.0",
                "terms_accepted_at": _utc_now().isoformat(),
                "business_id": TARGET_BIN,
                "business_id_active": True,
                "business_id_created": _utc_now().isoformat(),
                "created_at": legacy.get("created_at") or _utc_now().isoformat(),
                "updated_at": _utc_now().isoformat(),
                "smart_onboarding_complete": False,
                "wizard_complete": False,
                "must_set_password": False,  # Google OAuth — no password
            }
            await db.platform_users.update_one(
                {"email": LEGACY_EMAIL},
                {"$setOnInsert": doc},
                upsert=True,
            )
            print(f"✓ seeded platform_users → business_id={TARGET_BIN}")

    # ─── 2b. Stamp the legacy `users` doc with the SAME BIN ───
    # CRITICAL: business_id_router.ensure_business_id() updates BOTH
    # `users` and `platform_users` by email when a legacy user has no
    # BIN. If we don't stamp the legacy doc here, the next API call
    # to /api/business-id/mine (or /api/onboarding/status) will
    # regenerate a fresh BIN and overwrite our seed. (Verified bug
    # observed during RERO-3DEJ recovery — TEJI-6KJ5 was minted 2 min
    # after the first seed.)
    await db.users.update_one(
        {"email": LEGACY_EMAIL},
        {"$set": {
            "business_id": TARGET_BIN,
            "business_id_active": True,
            "business_id_created": _utc_now().isoformat(),
        }},
    )
    print(f"✓ stamped legacy users.{LEGACY_EMAIL} → business_id={TARGET_BIN} "
          "(prevents BIN regeneration race)")

    # ─── 3. Trigger auto-repair pipeline ──────────────────────
    print()
    print("=== Triggering auto-repair pipeline ===")
    # Import lazily so the script can run standalone with PYTHONPATH only
    from services.customer_health_monitor import set_db as set_chm_db, check_tenant
    from services.customer_repair_pipeline import trigger_repair_pipeline
    set_chm_db(db)

    # Inject the db into server module so other services can find it
    try:
        import server  # noqa: F401
        server.db = db  # type: ignore
    except Exception:
        pass

    summary_before = await check_tenant(TARGET_BIN)
    print(f"  pre-repair status:  {summary_before.get('status')}")
    print(f"  pre-repair failed:  {summary_before.get('failed')}")

    if summary_before.get("status") == "healthy":
        print()
        print("✅ Already healthy — nothing to repair.")
        return 0

    repair_result = await trigger_repair_pipeline(
        TARGET_BIN,
        summary_before.get("checks", {}),
        summary_before.get("status", "degraded"),
    )

    print()
    print("=== Repair pipeline result ===")
    print(f"  applied:        {repair_result.get('applied')}")
    print(f"  rejected:       {repair_result.get('rejected')}")
    print(f"  post_status:    {repair_result.get('post_status')}")
    print(f"  still_failing:  {repair_result.get('still_failing')}")

    # ─── 4. Final verification ────────────────────────────────
    print()
    print("=== Final verification ===")
    final = await check_tenant(TARGET_BIN)
    print(f"  status:  {final.get('status')}")
    print(f"  failed:  {final.get('failed')}")

    if final.get("status") == "healthy":
        print()
        print(f"✅ {TARGET_BIN} fully recovered — admin can log in via Google "
              f"OAuth and /my dashboard is live.")
        return 0
    else:
        print()
        print(f"⚠️ {TARGET_BIN} still {final.get('status')} — "
              f"check Customer Health admin panel for manual fix buttons.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
