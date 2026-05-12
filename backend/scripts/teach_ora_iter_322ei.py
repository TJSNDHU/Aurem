"""
teach_ora_iter_322ei — Push the developer-engineering-protocol skill into
ORA's permanent memory across all 4 official channels:

  1. ora_training_files       — canonical learning corpus (embedding-indexed)
  2. ora_skills_library       — official AntiGravity schema
  3. ora_skills_broadcast     — live system_addendum for all 28 agents
  4. SECONDARY Atlas mirror   — DR copy of #1

Idempotent — re-runs upsert, don't duplicate. Run:
  cd /app/backend && set -a && source .env && set +a && \
  python3 scripts/teach_ora_iter_322ei.py
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


SKILL = {
    "iter":        "322ei",
    "skill_id":    "aurem-322ei-developer-engineering-protocol",
    "name":        "Developer Engineering Protocol (founder-grade coding methodology)",
    "category":    "engineering_methodology",
    "description": (
        "Complete operating manual for software engineering on AUREM. Read "
        "this BEFORE any coding task. Covers: investigation toolbox, file-"
        "editing discipline, 5-stage bug-fix workflow, DB forensics, "
        "environment invariants, mandatory 3-proof verification, regression "
        "locking, persistence to ORA memory, integration rules, escalation "
        "red flags. The same protocol the AUREM main agent follows."
    ),
    "md_path":     "/app/backend/ora_skills/dev_developer-engineering-protocol.md",
}


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    body = open(SKILL["md_path"]).read()
    body_hash = hashlib.sha256(body.encode()).hexdigest()[:16]

    print(f"=== iter 322ei — Teaching ORA the Developer Engineering Protocol ===")
    print(f"Skill body: {len(body)} chars, sha={body_hash}\n")

    # ── Channel 1: ora_training_files (canonical corpus) ─────────────
    text = f"AUREM Developer Engineering Protocol (iter 322ei)\n\n{body}"
    await db.ora_training_files.update_one(
        {"file_id": f"learning-brief-{SKILL['iter']}"},
        {"$set": {
            "file_id":      f"learning-brief-{SKILL['iter']}",
            "user_id":      "system_main_agent",
            "source_type":  "learning_brief",
            "filename":     f"learning-{SKILL['iter']}-developer-protocol.md",
            "file_ext":     ".md",
            "file_category": "document",
            "file_size":    len(text),
            "language":     "english",
            "purpose":      "ora_self_learning",
            "notes":        "Developer engineering methodology — replica of main agent's working protocol",
            "status":       "ready",
            "crawled_text": text,
            "text_chars":   len(text),
            "created_at":   now,
            "updated_at":   now,
        }},
        upsert=True,
    )
    print(f"[1/4] ora_training_files          ← {len(text)} chars")

    # ── Channel 2: ora_skills_library (official schema) ──────────────
    await db.ora_skills_library.update_one(
        {"id": SKILL["skill_id"]},
        {"$set": {
            "id":           SKILL["skill_id"],
            "name":         SKILL["name"],
            "category":     SKILL["category"],
            "description":  SKILL["description"],
            "body":         body,
            "source":       f"aurem-internal-iter-{SKILL['iter']}",
            "added_at":     now,
            "iter":         SKILL["iter"],
            "content_hash": body_hash,
        }},
        upsert=True,
    )
    print(f"[2/4] ora_skills_library          ← {SKILL['skill_id']}")

    # ── Channel 3: active broadcast (MERGE with existing) ─────────────
    existing = await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}
    existing_ids = list(existing.get("skill_ids") or [])
    # New skill goes FIRST so it lands at the top of every agent's prompt.
    if SKILL["skill_id"] in existing_ids:
        existing_ids.remove(SKILL["skill_id"])
    final_ids = [SKILL["skill_id"]] + existing_ids

    docs = await db.ora_skills_library.find(
        {"id": {"$in": final_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(final_ids))
    # Re-order to match `final_ids`
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[sid] for sid in final_ids if sid in by_id]

    bits: list[str] = []
    for d in ordered:
        head = (d.get("body") or "")[:600].strip()
        bits.append(
            f"### SKILL: {d['name']} ({d['category']})\n"
            f"{d.get('description', '')}\n{head}"
        )
    addendum = "\n\n".join(bits)

    await db.ora_skills_broadcast.update_one(
        {"_id": "active"},
        {"$set": {
            "skill_ids":       final_ids,
            "system_addendum": addendum,
            "target_agents":   "ALL",
            "broadcast_at":    now,
            "skill_count":     len(final_ids),
        }},
        upsert=True,
    )
    await db.ora_skills_broadcast_history.insert_one({
        "_id":              f"bcast_{now}_{SKILL['iter']}",
        "skill_ids":        final_ids,
        "target_agents":    "ALL",
        "broadcast_at":     now,
        "broadcast_by":     f"main_agent_iter_{SKILL['iter']}",
        "action":           "broadcast",
        "iter":             SKILL["iter"],
    })

    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    print(f"[3/4] ora_skills_broadcast active ← {len(final_ids)} skills, "
          f"{len(addendum)} chars addendum, cache invalidated")

    # ── Channel 4: SECONDARY Atlas mirror ────────────────────────────
    print(f"\n=== Mirroring to SECONDARY Atlas ===")
    sec_url = os.environ.get("SECONDARY_MONGO_URL")
    if not sec_url:
        print(f"[4/4] ⚠ SECONDARY_MONGO_URL not set — skipping mirror")
    else:
        try:
            from pymongo import MongoClient

            def _mirror() -> str:
                sec = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
                sdb = sec[os.environ.get("DB_NAME", "aurem_db")]
                existing_doc = sdb.ora_training_files.find_one(
                    {"file_id": f"learning-brief-{SKILL['iter']}"}
                )
                doc = {
                    **(existing_doc or {}),
                    "file_id":      f"learning-brief-{SKILL['iter']}",
                    "user_id":      "system_main_agent",
                    "source_type":  "learning_brief",
                    "filename":     f"learning-{SKILL['iter']}-developer-protocol.md",
                    "file_ext":     ".md",
                    "file_category": "document",
                    "file_size":    len(text),
                    "language":     "english",
                    "purpose":      "ora_self_learning",
                    "status":       "ready",
                    "crawled_text": text,
                    "text_chars":   len(text),
                    "updated_at":   now,
                }
                if not existing_doc:
                    doc["created_at"] = now
                sdb.ora_training_files.replace_one(
                    {"file_id": f"learning-brief-{SKILL['iter']}"},
                    doc, upsert=True,
                )
                sec.close()
                return "ok"

            await asyncio.to_thread(_mirror)
            print(f"[4/4] ora_training_files on secondary ← upserted")
        except Exception as e:
            print(f"[4/4] ⚠ secondary mirror failed: {e}")

    # ── Verification: re-read from both clusters ──────────────────────
    print(f"\n=== Verification — count of iter-322ei records ===")
    pri_n = await db.ora_training_files.count_documents(
        {"file_id": f"learning-brief-{SKILL['iter']}"}
    )
    pri_s = await db.ora_skills_library.count_documents(
        {"id": SKILL["skill_id"]}
    )
    bcast = await db.ora_skills_broadcast.find_one({"_id": "active"})
    has_skill = SKILL["skill_id"] in (bcast.get("skill_ids") or [])
    print(f"  PRIMARY:")
    print(f"    ora_training_files (this iter): {pri_n}")
    print(f"    ora_skills_library (this iter): {pri_s}")
    print(f"    ora_skills_broadcast (contains): {has_skill}")
    print(f"    total broadcast skills:         {bcast.get('skill_count', 0)}")
    print(f"    addendum length:                {len(bcast.get('system_addendum',''))} chars")

    if sec_url:
        try:
            from pymongo import MongoClient
            def _check_sec() -> int:
                sec = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
                n = sec[os.environ.get("DB_NAME", "aurem_db")].ora_training_files.count_documents(
                    {"file_id": f"learning-brief-{SKILL['iter']}"}
                )
                sec.close()
                return n
            sec_n = await asyncio.to_thread(_check_sec)
            print(f"  SECONDARY:")
            print(f"    ora_training_files (this iter): {sec_n}")
        except Exception as e:
            print(f"  SECONDARY: check failed — {e}")


if __name__ == "__main__":
    asyncio.run(main())
