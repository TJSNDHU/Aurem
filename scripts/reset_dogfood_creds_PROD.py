#!/usr/bin/env python3
"""
One-shot: set password (Singh100123$) + PIN (7668) for the +dogfood account
AND set PIN (7668) on admin teji.ss1986@gmail.com (BIN AURE-RUGC).

USAGE (run on a machine with access to your prod Atlas cluster):

    export MONGO_URL="<your prod Atlas connection string>"
    export DB_NAME="aurem_db"      # whatever your prod db_name is
    pip install motor bcrypt python-dotenv
    python3 reset_dogfood_creds_PROD.py

Idempotent — safe to re-run.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient


PASSWORD = "Singh100123$"
PIN = "7668"


async def main() -> None:
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url or not db_name:
        sys.exit("ERROR: set MONGO_URL and DB_NAME first")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    pwd_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=12)).decode()
    pin_hash = bcrypt.hashpw(PIN.encode(), bcrypt.gensalt(rounds=12)).decode()
    now = datetime.now(timezone.utc).isoformat()

    # 1. +dogfood account in platform_users
    res = await db.platform_users.update_one(
        {"email": "teji.ss1986+dogfood@gmail.com"},
        {"$set": {
            "password": pwd_hash,
            "password_hash": pwd_hash,
            "pin_hash": pin_hash,
            "pin_set_at": now,
            "pin_failed_count": 0,
            "pin_locked_until": None,
            "updated_at": now,
        }},
    )
    print(f"[+dogfood] platform_users → matched={res.matched_count} modified={res.modified_count}")
    if res.matched_count == 0:
        print("  ⚠️  +dogfood row not found in platform_users — check the email.")

    # 2. Admin PIN rotation in users (BIN AURE-RUGC)
    res2 = await db.users.update_one(
        {"email": "teji.ss1986@gmail.com"},
        {"$set": {
            "pin_hash": pin_hash,
            "pin_set_at": now,
            "pin_failed_count": 0,
            "pin_locked_until": None,
        }},
    )
    print(f"[admin]   users           → matched={res2.matched_count} modified={res2.modified_count}")

    # 3. Clear any rate-limit lockouts for both accounts
    p1 = await db.login_attempts.delete_many(
        {"$or": [
            {"email": "teji.ss1986+dogfood@gmail.com"},
            {"email": "teji.ss1986@gmail.com"},
        ]},
    )
    print(f"[purge]   login_attempts     → deleted={p1.deleted_count}")
    p2 = await db.pin_login_attempts.delete_many(
        {"key": {"$regex": "(AURE-RUGC|AURE-3M4G)$", "$options": "i"}},
    )
    print(f"[purge]   pin_login_attempts → deleted={p2.deleted_count}")

    print("\n✅ Done. Try login again on aurem.live:")
    print("   /platform/login — Credentials tab — teji.ss1986+dogfood@gmail.com / Singh100123$")
    print("   /platform/login — BIN+PIN tab    — AURE-RUGC / 7668")


if __name__ == "__main__":
    asyncio.run(main())
