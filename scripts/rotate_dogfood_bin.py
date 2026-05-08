#!/usr/bin/env python3
"""One-shot rotate dogfood BIN to AURE-RUGC for the founder admin."""
import os, sys, asyncio
sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient

NEW_BIN = "AURE-RUGC"
EMAIL = "teji.ss1986@gmail.com"


async def main():
    c = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = c[os.environ["DB_NAME"]]
    user = await db.users.find_one({"email": EMAIL})
    if not user:
        print(f"FAIL: no user {EMAIL}"); sys.exit(1)
    old = user.get("business_id")
    res = await db.users.update_one(
        {"email": EMAIL},
        {"$set": {"business_id": NEW_BIN, "business_id_active": True}},
    )
    print(f"OK: rotated BIN {old!r} -> {NEW_BIN!r} (modified={res.modified_count})")


if __name__ == "__main__":
    asyncio.run(main())
