"""
Seed the AUREM Security Patterns playbook into the live skill broadcast.

After this script runs:
- `ora_skills_library` gets a fresh "AUREM-SEC-PATTERNS-V1" document
- `ora_skills_broadcast/_id=active` is upgraded to include the patterns
  as part of every agent's system prompt (via agent_skill_broadcast)
- `agent_skill_broadcast.invalidate_cache()` is called so the change is
  picked up on the next LLM call without restart

Run: `python3 -m scripts.seed_security_patterns_skill`
Idempotent — re-running just updates the same doc.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient

PLAYBOOK_PATH = Path("/app/memory/SECURITY_PATTERNS.md")
SKILL_ID = "AUREM-SEC-PATTERNS-V1"


async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or "aurem_db"
    if not mongo_url:
        raise RuntimeError("MONGO_URL not set")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    if not PLAYBOOK_PATH.exists():
        raise RuntimeError(f"Playbook missing: {PLAYBOOK_PATH}")
    body = PLAYBOOK_PATH.read_text(encoding="utf-8")
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    # 1) Persist the skill in the library.
    await db.ora_skills_library.update_one(
        {"id": SKILL_ID},
        {
            "$set": {
                "id": SKILL_ID,
                "name": "AUREM Security Patterns",
                "description": (
                    "32 audited vulnerability patterns (PAT-01..32) covering "
                    "auth, SSRF, secrets, event-loop, tenancy, tool dispatch, "
                    "and biometrics. Includes detect-regex + fix-templates."
                ),
                "categories": ["security", "code-review", "autonomous-repair"],
                "version": "1",
                "body": body,
                "body_sha256": body_hash,
                "byte_size": len(body.encode("utf-8")),
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    # 2) Pull existing broadcast addendum (if any), merge in this skill.
    cur = await db.ora_skills_broadcast.find_one({"_id": "active"}, {"_id": 0})
    existing_addendum = (cur or {}).get("system_addendum") or ""
    skill_ids = list((cur or {}).get("skill_ids") or [])

    marker = f"<!-- SKILL:{SKILL_ID} -->"
    end_marker = f"<!-- /SKILL:{SKILL_ID} -->"
    block = f"{marker}\n{body}\n{end_marker}"

    if marker in existing_addendum:
        # Replace existing block in-place (idempotent re-seed).
        start = existing_addendum.index(marker)
        end = existing_addendum.index(end_marker) + len(end_marker)
        new_addendum = existing_addendum[:start] + block + existing_addendum[end:]
    else:
        sep = "\n\n" if existing_addendum else ""
        new_addendum = existing_addendum + sep + block

    if SKILL_ID not in skill_ids:
        skill_ids.append(SKILL_ID)

    await db.ora_skills_broadcast.update_one(
        {"_id": "active"},
        {
            "$set": {
                "system_addendum": new_addendum,
                "skill_ids": skill_ids,
                "target_agents": "ALL",
                "updated_at": now,
                "updated_by": "seed_security_patterns_skill",
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    # 3) Bust the in-process cache so the next LLM call picks it up.
    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception as e:
        print(f"[warn] cache invalidate skipped: {e}")

    # Confirmation read-back.
    cur = await db.ora_skills_broadcast.find_one({"_id": "active"}, {"_id": 0})
    addendum_len = len((cur or {}).get("system_addendum") or "")
    ids = (cur or {}).get("skill_ids") or []
    print("✓ SECURITY_PATTERNS broadcast seeded")
    print(f"  skill_ids       : {ids}")
    print(f"  addendum bytes  : {addendum_len}")
    print(f"  body sha256     : {body_hash[:16]}…")
    print(f"  targets         : {(cur or {}).get('target_agents')}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
