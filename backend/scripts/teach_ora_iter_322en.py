"""
teach_ora_iter_322en — Hard-save Surgical Writer + Service Supervisor skill.
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
    "iter":     "322en",
    "id":       "aurem-322en-ora-write-and-restart",
    "name":     "ORA Write & Restart — Surgical Writer + Service Supervisor (autonomous loop)",
    "category": "write_tools",
    "description": (
        "P3 write capability. Two new tools: (1) safe_edit — atomic, exact-"
        "match find/replace with auto-backup to /tmp/ora_backups/, refuses "
        "to guess when find_string is ambiguous or missing. (2) "
        "restart_service — detached supervisorctl restart for backend or "
        "frontend only. Together they unlock the autonomous loop: edit → "
        "lint → restart → curl. Hard-blocked: .env, package.json, lock "
        "files, .git/, build/, dist/, restart of mongo/postgres/redis/nginx."
    ),
    "md_path":  "/app/backend/ora_skills/dev_ora-write-and-restart.md",
}


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    import server
    server.db = db
    now = datetime.now(timezone.utc).isoformat()

    body = open(SKILL["md_path"]).read()
    body_hash = hashlib.sha256(body.encode()).hexdigest()[:16]
    print(f"=== iter 322en — Hard-saving Write & Restart skill ===")
    print(f"Body: {len(body)} chars, sha={body_hash}\n")

    # 1. ora_training_files
    text = f"AUREM Skill — {SKILL['name']} (iter {SKILL['iter']})\n\n{body}"
    await db.ora_training_files.update_one(
        {"file_id": f"learning-brief-{SKILL['iter']}"},
        {"$set": {
            "file_id":      f"learning-brief-{SKILL['iter']}",
            "user_id":      "system_main_agent",
            "source_type":  "learning_brief",
            "filename":     f"learning-{SKILL['iter']}-write-and-restart.md",
            "file_ext":     ".md",
            "file_category": "document",
            "file_size":    len(text),
            "language":     "english",
            "purpose":      "ora_self_learning",
            "notes":        SKILL["description"][:200],
            "status":       "ready",
            "crawled_text": text,
            "text_chars":   len(text),
            "created_at":   now,
            "updated_at":   now,
        }},
        upsert=True,
    )
    print(f"[1/4] ora_training_files          ← {len(text)} chars")

    # 2. ora_skills_library
    await db.ora_skills_library.update_one(
        {"id": SKILL["id"]},
        {"$set": {
            "id":           SKILL["id"],
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
    print(f"[2/4] ora_skills_library          ← {SKILL['id']}")

    # 3. broadcast — Charter stays first; this skill inserts at position 2
    # (right after Charter@0 and Execution-Layer@1)
    existing = await db.ora_skills_broadcast.find_one({"_id": "active"}) or {}
    existing_ids = [s for s in (existing.get("skill_ids") or []) if s != SKILL["id"]]
    # Find the execution-layer skill position
    try:
        exec_idx = existing_ids.index("aurem-322em-ora-execution-layer")
        # Insert RIGHT AFTER execution layer
        final_ids = existing_ids[:exec_idx + 1] + [SKILL["id"]] + existing_ids[exec_idx + 1:]
    except ValueError:
        # No execution-layer found → prepend
        final_ids = [SKILL["id"]] + existing_ids

    docs = await db.ora_skills_library.find(
        {"id": {"$in": final_ids}},
        {"_id": 0, "id": 1, "name": 1, "description": 1, "category": 1, "body": 1},
    ).to_list(length=len(final_ids))
    by_id = {d["id"]: d for d in docs}
    ordered = [by_id[sid] for sid in final_ids if sid in by_id]

    bits: list[str] = []
    for i, d in enumerate(ordered):
        head_chars = 1200 if "zero-hallucination" in d["id"] else 600
        head = (d.get("body") or "")[:head_chars].strip()
        prefix = "## ⚖️ CORE LAW (read first):\n" if i == 0 else ""
        bits.append(
            f"{prefix}### SKILL: {d['name']} ({d['category']})\n"
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
            "charter_first":   final_ids[0] == "aurem-322ek-zero-hallucination-charter",
        }},
        upsert=True,
    )
    await db.ora_skills_broadcast_history.insert_one({
        "_id":            f"bcast_{now}_322en",
        "skill_ids":      final_ids,
        "target_agents":  "ALL",
        "broadcast_at":   now,
        "broadcast_by":   "main_agent_iter_322en",
        "action":         "broadcast_with_write_tools",
    })
    try:
        from services.agent_skill_broadcast import invalidate_cache
        invalidate_cache()
    except Exception:
        pass
    print(f"[3/4] ora_skills_broadcast active ← {len(final_ids)} skills, "
          f"{len(addendum)} chars (cache invalidated)")

    # 4. SECONDARY Atlas mirror
    print(f"\n=== Mirror to SECONDARY Atlas ===")
    sec_url = os.environ.get("SECONDARY_MONGO_URL")
    if sec_url:
        try:
            from pymongo import MongoClient
            def _mirror():
                s = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
                sdb = s[os.environ.get("DB_NAME", "aurem_db")]
                existing = sdb.ora_training_files.find_one(
                    {"file_id": f"learning-brief-{SKILL['iter']}"}
                )
                doc = {
                    **(existing or {}),
                    "file_id":      f"learning-brief-{SKILL['iter']}",
                    "user_id":      "system_main_agent",
                    "source_type":  "learning_brief",
                    "filename":     f"learning-{SKILL['iter']}-write-and-restart.md",
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
                if not existing:
                    doc["created_at"] = now
                sdb.ora_training_files.replace_one(
                    {"file_id": f"learning-brief-{SKILL['iter']}"},
                    doc, upsert=True,
                )
                s.close()
                return "ok"
            await asyncio.to_thread(_mirror)
            print(f"[4/4] secondary ora_training_files ← mirrored")
        except Exception as e:
            print(f"[4/4] ⚠ secondary mirror failed: {e}")
    else:
        print(f"[4/4] ⚠ SECONDARY_MONGO_URL not set")

    # Verification
    print(f"\n=== Verification (both clusters) ===")
    pri_n = await db.ora_training_files.count_documents(
        {"file_id": f"learning-brief-{SKILL['iter']}"}
    )
    pri_s = await db.ora_skills_library.count_documents({"id": SKILL["id"]})
    bcast = await db.ora_skills_broadcast.find_one({"_id": "active"})
    print(f"  PRIMARY  training_files:  {pri_n}")
    print(f"  PRIMARY  skills_library:  {pri_s}")
    print(f"  PRIMARY  broadcast:       {bcast.get('skill_count')} total skills, "
          f"contains write skill = {SKILL['id'] in (bcast.get('skill_ids') or [])}")
    print(f"  PRIMARY  charter@0:       {bcast.get('charter_first')}")
    print(f"  PRIMARY  active addendum: {len(bcast.get('system_addendum','') or '')} chars")

    if sec_url:
        from pymongo import MongoClient
        def _check():
            s = MongoClient(sec_url, serverSelectionTimeoutMS=15000)
            n = s[os.environ.get("DB_NAME", "aurem_db")].ora_training_files.count_documents(
                {"file_id": f"learning-brief-{SKILL['iter']}"}
            )
            s.close()
            return n
        sec_n = await asyncio.to_thread(_check)
        print(f"  SECONDARY training_files: {sec_n}")


if __name__ == "__main__":
    asyncio.run(main())
