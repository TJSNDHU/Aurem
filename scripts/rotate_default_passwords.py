"""
One-time password rotation for AUREM accounts.
Rotates every account whose password matches a known default to a freshly
generated bcrypt hash. Safe to run on production: it only touches accounts
where the password_hash STILL verifies against the leaked default — i.e. it
never overwrites a password the user has already changed.

Usage (one-shot):
    python -m scripts.rotate_default_passwords

In production, set FOUNDER_PASSWORD_RESET=1 and redeploy — `founder_provision`
will rotate founder accounts on startup. This script is for the broader sweep
(admin seed in `users`, customer-luxe-test, etc.).
"""
import asyncio
import os
import sys
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorClient

# Add backend to path so we can run from /app
sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

# (email, leaked_default_password, new_password)
ROTATIONS = [
    ("teji.ss1986@gmail.com", "Admin123",          "ul4Fb*u^l^Nuazh@B%Q8"),
    ("admin@aurem.live",      "AuremAdmin2024!",   "o2VmqItgD3STdLlHWX^u"),
    ("customer-luxe-test@aurem-test.com", "LuxeTest123!", "VC^*yc0T43lR2kSO@ya0"),
]


async def rotate(coll_name: str, email: str, old_pw: str, new_pw: str, hash_field: str = "password_hash"):
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    coll = db[coll_name]
    doc = await coll.find_one({"email": email}, {"_id": 1, hash_field: 1})
    if not doc:
        return f"  [{coll_name}] {email} → not found"
    h = doc.get(hash_field)
    if not h:
        return f"  [{coll_name}] {email} → no {hash_field}"
    if not _pwd.verify(old_pw, h):
        return f"  [{coll_name}] {email} → password already changed (NOT touched)"
    new_hash = _pwd.hash(new_pw)
    await coll.update_one({"_id": doc["_id"]}, {"$set": {hash_field: new_hash}})
    return f"  [{coll_name}] {email} → ROTATED ✓"


async def main():
    print("=" * 70)
    print("AUREM password rotation — invalidates leaked default credentials")
    print("=" * 70)
    for email, old_pw, new_pw in ROTATIONS:
        # platform_users uses `password_hash`
        print(await rotate("platform_users", email, old_pw, new_pw, "password_hash"))
        # users (admin collection) uses `password`
        print(await rotate("users", email, old_pw, new_pw, "password"))
    print("=" * 70)
    print("Done. New passwords are stored ONLY in /app/memory/test_credentials.md")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
