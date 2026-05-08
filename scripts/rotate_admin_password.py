#!/usr/bin/env python3
"""
One-shot admin password rotation script.

Reads MONGO_URL/DB_NAME from /app/backend/.env, rotates the password for
the email passed as arg 1 to the new password passed as arg 2, using the
same bcrypt scheme as routes/auth.py (services.auth_service.hash_password).

Usage:
    python3 /app/scripts/rotate_admin_password.py teji.ss1986@gmail.com 'NewPass!'
"""
import sys
import os
import asyncio

# Make backend importable
sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient
from utils.auth import hash_password, verify_password


async def main():
    if len(sys.argv) != 3:
        print("usage: rotate_admin_password.py <email> <new_password>")
        sys.exit(2)
    email = sys.argv[1].strip().lower()
    new_pw = sys.argv[2]

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    user = await db.users.find_one({"email": email}, {"_id": 0, "email": 1, "is_admin": 1, "is_super_admin": 1})
    if not user:
        print(f"FAIL: no user with email={email!r} in db.users")
        sys.exit(1)

    new_hash = hash_password(new_pw)
    res = await db.users.update_one({"email": email}, {"$set": {"password": new_hash}})
    if res.modified_count != 1:
        print(f"FAIL: update_one matched={res.matched_count} modified={res.modified_count}")
        sys.exit(1)

    # Verify roundtrip — re-fetch and check verify_password
    fresh = await db.users.find_one({"email": email}, {"_id": 0, "password": 1})
    ok = verify_password(new_pw, fresh.get("password", ""))
    if not ok:
        print("FAIL: verify_password roundtrip failed — password was written but does not verify")
        sys.exit(1)

    print(f"OK: rotated password for {email}; bcrypt verify roundtrip PASS")
    print(f"     is_admin={user.get('is_admin')}, is_super_admin={user.get('is_super_admin')}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
